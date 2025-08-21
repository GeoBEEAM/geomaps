from fastapi import APIRouter, Depends, status, HTTPException, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from sqlalchemy.future import select

from core.auth import authenticate, generate_token, create_access_token
from core.deps import get_session
from core.messages import MSG_USER_NOT_FOUND, MSG_PASSWORD_RESET_SENT
from models import User
from utils.log_utils import log_action

auth_router = APIRouter()


@auth_router.post('/login', status_code=status.HTTP_201_CREATED)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_session)):
    user = await authenticate(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Credenciais inválidas')
    return JSONResponse(content={'access_token': create_access_token(sub=str(user.id)), "token_type": "bearer"}, status_code=status.HTTP_200_OK)


@auth_router.post('/recuperar-senha', status_code=status.HTTP_200_OK)
async def recuperar_senha(
    email: str = Body(..., embed=True),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(User).filter(User.email == email))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
    # Aqui você integraria com serviço de email para enviar o link/token de recuperação
    # Exemplo: send_password_reset_email(user.email, token)
    async with session.begin():
        await log_action(session, user_id=user.id, action="PASSWORD_RESET_REQUEST", entity="USER", entity_id=user.id, details=f"Solicitação de recuperação de senha para {user.email}")
    return {"detail": MSG_PASSWORD_RESET_SENT}
