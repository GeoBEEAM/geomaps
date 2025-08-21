from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from core.configs import settings
from datetime import datetime
from models.profile import Profile

# Associação User <-> Profile
user_profiles = Table(
    'user_profiles',
    settings.DBBaseModel.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('profile_id', Integer, ForeignKey('profiles.id'), primary_key=True)
)

class User(settings.DBBaseModel):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fullName = Column(String, nullable=False)
    cpf = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    max_apiaries = Column(Integer, default=1, nullable=False)
    max_meliponaries = Column(Integer, default=1, nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    profiles = relationship(
        'Profile',
        secondary=user_profiles,
        back_populates='users',
        lazy='joined'
    )

    apiaries = relationship(
        "Apiary",
        back_populates="owner",
        cascade="all,delete-orphan",
        uselist=True,
        lazy="joined"
    )
    meliponaries = relationship(
        "Meliponary",
        back_populates="owner",
        cascade="all,delete-orphan",
        uselist=True,
        lazy="joined"
    )
