from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean

from core.configs import settings


class Maps(settings.DBBaseModel):
    __tablename__ = 'geomaps'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_path = Column(String, nullable=False)
    name = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
