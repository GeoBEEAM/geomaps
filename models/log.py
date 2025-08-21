from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.configs import settings

class Log(settings.DBBaseModel):
    __tablename__ = 'logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    action = Column(String, nullable=False)  # ex: CREATE, UPDATE, DELETE
    entity = Column(String, nullable=False)  # ex: MELIPONARY, APIARY
    entity_id = Column(Integer, nullable=True)  # id do registro afetado
    details = Column(Text, nullable=True)  # detalhes extras (json, msg, etc)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship('User')

