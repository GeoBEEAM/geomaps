from fastapi import APIRouter, Depends, status, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.deps import get_session, get_current_user
from core.messages import (
    MSG_USER_NOT_FOUND, MSG_USER_ALREADY_ACTIVE, MSG_USER_ALREADY_INACTIVE,
    MSG_USER_ACTIVATED, MSG_USER_DEACTIVATED, MSG_LIMITS_UPDATED, MSG_ROLE_ADDED, MSG_ROLE_REMOVED
)
from models.user import User
from schemas.user_schema import UserSchema
from utils.log_utils import log_action
from datetime import datetime, timedelta

management_router = APIRouter()

# --- Gestão de Usuários ---
@management_router.patch('/users/{user_id}/activate', status_code=status.HTTP_200_OK)
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

@management_router.patch('/users/{user_id}/deactivate', status_code=status.HTTP_200_OK)
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

@management_router.patch('/users/{user_id}/limits', status_code=status.HTTP_200_OK)
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

@management_router.get('/users/{user_id}/config', status_code=status.HTTP_200_OK)
async def get_user_config(user_id: int, session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
    return {
        "is_active": user.is_active,
        "max_apiaries": user.max_apiaries,
        "max_meliponaries": user.max_meliponaries,
    }

# --- Gestão de Pagamentos ---
@management_router.post('/payments/initiate', status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    user_id: int = Body(...),
    amount: float = Body(...),
    provider: str = Body(..., examples=[{"value": "efi"}, {"value": "stripe"}]),
    session: AsyncSession = Depends(get_session),
    auth_user: User = Depends(get_current_user)
):
    """
    Inicia um pagamento para o usuário informado.
    provider: 'efi' ou 'stripe'.
    """
    # Aqui você pode adicionar lógica para registrar o pagamento no banco, se necessário
    # Integração com provedores será implementada abaixo
    if provider == "efi":
        # Preparar integração com Efi Pagamentos (ex-Gerencianet)
        return {"status": "pending", "provider": "efi", "message": "Integração Efi Pagamentos a implementar."}
    elif provider == "stripe":
        # Preparar integração com Stripe
        return {"status": "pending", "provider": "stripe", "message": "Integração Stripe a implementar."}
    else:
        raise HTTPException(status_code=400, detail="Provedor de pagamento não suportado.")

@management_router.get('/payments/status/{payment_id}', status_code=status.HTTP_200_OK)
async def get_payment_status(payment_id: str, provider: str, auth_user: User = Depends(get_current_user)):
    """
    Consulta o status de um pagamento em um provedor externo.
    """
    if provider == "efi":
        # Exemplo: status = efi_get_payment_status(payment_id)
        return {"payment_id": payment_id, "provider": "efi", "status": "A implementar"}
    elif provider == "stripe":
        # Exemplo: status = stripe_get_payment_status(payment_id)
        return {"payment_id": payment_id, "provider": "stripe", "status": "A implementar"}
    else:
        raise HTTPException(status_code=400, detail="Provedor de pagamento não suportado.")

@management_router.get('/users/{user_id}/is_paid', status_code=status.HTTP_200_OK)
async def is_user_paid(user_id: int, session: AsyncSession = Depends(get_session)):
    """
    Verifica se o usuário está em dia com o pagamento.
    Aqui você pode integrar com Efi ou Stripe para checar status real.
    """
    # Exemplo fictício: buscar último pagamento e checar validade
    # Aqui você integraria com o provedor real e/ou sua tabela de pagamentos
    # Exemplo: buscar último pagamento do usuário
    # pagamento = await buscar_ultimo_pagamento(user_id)
    # if pagamento and pagamento.status == 'paid' and pagamento.data_validade > datetime.utcnow():
    #     return {"is_paid": True}
    # else:
    #     return {"is_paid": False}
    return {"is_paid": "A implementar integração com Efi/Stripe"}

@management_router.post('/users/{user_id}/block_if_unpaid', status_code=status.HTTP_200_OK)
async def block_user_if_unpaid(user_id: int, dias_graca: int = 7, session: AsyncSession = Depends(get_session)):
    """
    Bloqueia o usuário se não estiver pago após o período de carência (dias_graca).
    """
    # Exemplo fictício: buscar último pagamento e checar validade
    # pagamento = await buscar_ultimo_pagamento(user_id)
    # if not pagamento or pagamento.status != 'paid':
    #     # Supondo que o usuário foi criado há mais de dias_graca dias
    #     result = await session.execute(select(User).filter(User.id == user_id))
    #     user = result.scalar()
    #     if user and user.createdAt < datetime.utcnow() - timedelta(days=dias_graca):
    #         user.is_active = False
    #         await session.commit()
    #         return {"blocked": True, "reason": "Usuário bloqueado por falta de pagamento."}
    # return {"blocked": False}
    return {"blocked": "A implementar integração com Efi/Stripe e lógica de bloqueio"}
