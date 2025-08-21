from fastapi import APIRouter, Depends, status, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.deps import get_session, get_current_user
from core.messages import (
    MSG_USER_NOT_FOUND, MSG_USER_ALREADY_ACTIVE, MSG_USER_ALREADY_INACTIVE,
    MSG_USER_ACTIVATED, MSG_USER_DEACTIVATED, MSG_LIMITS_UPDATED, MSG_ROLE_ADDED, MSG_ROLE_REMOVED
)
from core.security import generate_password_hash
from models import User
from models.apiary import Apiary
from models.meliponary import Meliponary
from schemas.apiary_schema import ApiarySchema
from schemas.meliponary_schema import MeliponarySchema
from schemas.user_schema import UserSchema, CreateUserSchema
from utils.log_utils import log_action

user_router = APIRouter()

async def verify_cpf_exists(cpf: str, session: AsyncSession):
    result = await session.execute(select(User).filter(User.cpf == cpf))
    user = result.scalar()
    if user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Já existe um usuário com esse cpf!')


async def verify_email_exists(email: str, session: AsyncSession):
    result = await session.execute(select(User).filter(User.email == email))
    user = result.scalar()
    if user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Já existe um usuário com esse email!')



@user_router.post('/', response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
        user: CreateUserSchema,
        session: AsyncSession = Depends(get_session)
):
    await verify_cpf_exists(user.cpf, session)
    await verify_email_exists(user.email, session)
    new_user = User(
        fullName=user.fullName,
        email=user.email,
        cpf=user.cpf,
        phone=user.phone,
        password=generate_password_hash(user.password),
    )
    # Adiciona perfis ao usuário
    if hasattr(user, 'profile_ids') and user.profile_ids:
        profiles = await session.execute(select(Profile).filter(Profile.id.in_(user.profile_ids)))
        new_user.profiles = profiles.scalars().all()
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user

@user_router.get('/me', response_model=UserSchema)
async def get_logged_in_user(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "fullName": current_user.fullName,
        "cpf": current_user.cpf,
        "email": current_user.email,
        "phone": current_user.phone,
        "profiles": [p.id for p in current_user.profiles],
        "perfis": [p.name for p in current_user.profiles],
        "createdAt": current_user.createdAt,
        "updatedAt": current_user.updatedAt
    }

@user_router.patch('/{user_id}/activate', status_code=status.HTTP_200_OK)
async def activate_user(user_id: int, session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
    if user.is_active:
        raise HTTPException(status_code=400, detail=MSG_USER_ALREADY_ACTIVE)
    user.is_active = True
    async with session.begin():
        await log_action(session, user_id=auth_user.id, action="ACTIVATE", entity="USER", entity_id=user.id, details=MSG_USER_ACTIVATED)
    await session.refresh(user)
    return {"detail": MSG_USER_ACTIVATED}

@user_router.patch('/{user_id}/deactivate', status_code=status.HTTP_200_OK)
async def deactivate_user(user_id: int, session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
    if not user.is_active:
        raise HTTPException(status_code=400, detail=MSG_USER_ALREADY_INACTIVE)
    user.is_active = False
    async with session.begin():
        await log_action(session, user_id=auth_user.id, action="DEACTIVATE", entity="USER", entity_id=user.id, details=MSG_USER_DEACTIVATED)
    await session.refresh(user)
    return {"detail": MSG_USER_DEACTIVATED}

@user_router.patch('/{user_id}/limits', status_code=status.HTTP_200_OK)
async def update_limits(user_id: int, max_apiaries: int, max_meliponaries: int, session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
    user.max_apiaries = max_apiaries
    user.max_meliponaries = max_meliponaries
    async with session.begin():
        await log_action(session, user_id=auth_user.id, action="UPDATE_LIMITS", entity="USER", entity_id=user.id, details=MSG_LIMITS_UPDATED)
    await session.refresh(user)
    return {"detail": MSG_LIMITS_UPDATED}

@user_router.patch('/{user_id}/roles/add', status_code=status.HTTP_200_OK)
async def add_role(user_id: int, roles: dict = Body(...), session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
    from models.user import UserRole
    added = []
    for role in roles.get("roles", []):
        if role not in [r.role for r in user.roles]:
            user.roles.append(UserRole(user_id=user.id, role=role))
            added.append(role)
    async with session.begin():
        await log_action(session, user_id=auth_user.id, action="ADD_ROLE", entity="USER", entity_id=user.id, details=f"{MSG_ROLE_ADDED} {', '.join(added)}")
    await session.refresh(user)
    return {"detail": f"{MSG_ROLE_ADDED} {', '.join(added)}"}

@user_router.patch('/{user_id}/roles/remove', status_code=status.HTTP_200_OK)
async def remove_role(user_id: int, roles: dict = Body(...), session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
    to_remove = set(roles.get("roles", []))
    user.roles = [r for r in user.roles if r.role not in to_remove]
    async with session.begin():
        await log_action(session, user_id=auth_user.id, action="REMOVE_ROLE", entity="USER", entity_id=user.id, details=f"{MSG_ROLE_REMOVED} {', '.join(to_remove)}")
    await session.refresh(user)
    return {"detail": f"{MSG_ROLE_REMOVED} {', '.join(to_remove)}"}

@user_router.get('/{user_id}/config', status_code=status.HTTP_200_OK)
async def get_user_config(user_id: int, session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
    return {
        "is_active": user.is_active,
        "max_apiaries": user.max_apiaries,
        "max_meliponaries": user.max_meliponaries,
        "profiles": [p.id for p in user.profiles],
        "perfis": [p.name for p in user.profiles]
    }

@user_router.get('/dashboard', status_code=200)
async def dashboard(session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    apiaries_result = await session.execute(select(Apiary).filter(Apiary.userId == auth_user.id))
    meliponaries_result = await session.execute(select(Meliponary).filter(Meliponary.userId == auth_user.id))
    apiaries = apiaries_result.scalars().all()
    meliponaries = meliponaries_result.scalars().all()
    return {
        "apiarios": [ApiarySchema.model_validate(a).model_dump() for a in apiaries],
        "meliponarios": [MeliponarySchema.model_validate(m).model_dump() for m in meliponaries]
    }
