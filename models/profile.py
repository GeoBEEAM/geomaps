from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship
from core.configs import settings
from models.role import Role

# Associação Profile <-> Role
profile_roles = Table(
    'profile_roles',
    settings.DBBaseModel.metadata,
    Column('profile_id', Integer, ForeignKey('profiles.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)

class Profile(settings.DBBaseModel):
    __tablename__ = 'profiles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

    roles = relationship('Role', secondary=profile_roles, back_populates='profiles')
    users = relationship('User', secondary='user_profiles', back_populates='profiles')
