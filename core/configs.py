import os
from typing import ClassVar

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from sqlalchemy.ext.declarative import declarative_base

load_dotenv()
class Settings(BaseSettings):
    """
    Configuracoes gerais usadas na aplicaco
    """
    API_V1_STR: str = "/api/v1"
    DB_URL: str = os.getenv("DB_URL")
    DBBaseModel: ClassVar = declarative_base()


    JWT_SECRET: str = 'HoGF2ucrNRiAH7VmxQ3Lo-08Dk2P8OITMNVDL9CWDio'
    """
    import secrets
    token = secrets.token_urlsafe(32)
    """
    ALGORITHM: str = "HS256"
    # 60 minutos * 24 horas * 7 dias => 1 semana
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    class Config:
        case_sensitive = True


settings: Settings = Settings()