from pydantic import BaseModel as SCBaseModel


class AuthSchema(SCBaseModel):
    email: str
    password: str

    class Config:
        from_attributes = True
