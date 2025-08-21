from typing import Optional, List
from pydantic import BaseModel as SCBaseModel
from datetime import datetime

class CreateUserSchema(SCBaseModel):
    fullName: str
    cpf: str
    email: str
    password: str
    phone: str
    profiles: List[int]  # IDs dos perfis

    class Config:
        from_attributes = True


class UserSchema(SCBaseModel):
    id: int
    fullName: str
    cpf: str
    email: str
    phone: str
    profiles: List[int]
    perfis: List[str]  # nomes dos perfis
    createdAt: datetime
    updatedAt: Optional[datetime]

    class Config:
        from_attributes = True