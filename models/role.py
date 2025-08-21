from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from core.configs import settings

class Role(settings.DBBaseModel):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    profiles = relationship('Profile', secondary='profile_roles', back_populates='roles')
