from pytz import timezone
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt

from models.user import User
from core.configs import settings
from core.security import verify_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def authenticate(email: str, password: str, db: AsyncSession) -> Optional[User]:
    async with db as session:
        query = select(User).filter(User.email == email)
        result = await session.execute(query)
        user: User = result.scalars().unique().one_or_none()

        if not user:
            return None
        if not verify_password(password, user.password):
            return None
        return user

def generate_token(token_type: str, token_lifetime: timedelta, sub: str) -> str:
    payload = {}
    sp = timezone('America/Sao_Paulo')
    expiration = datetime.now(tz=sp) + token_lifetime

    payload["type"] = token_type
    payload["exp"] = expiration
    payload["iat"] = datetime.now(tz=sp)
    payload["sub"] = str(sub)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

def create_access_token(sub: str) -> str:
    return generate_token("access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), sub)