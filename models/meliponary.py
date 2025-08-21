from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from core.configs import settings
from datetime import datetime

class Meliponary(settings.DBBaseModel):
    __tablename__ = 'meliponaries'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    latitude = Column(String, nullable=False)
    longitude = Column(String, nullable=False)
    tipoInstalacao = Column(String, nullable=False)
    especieAbelha = Column(String, nullable=True)
    quantidadeColmeias = Column(String, nullable=False)
    outrosMeliponariosRaio1km = Column(Boolean, nullable=False)
    qtdColmeiasOutrosMeliponarios = Column(String, nullable=True)
    fontesNectarPolen = Column(Boolean, nullable=False)
    disponibilidadeAgua = Column(Boolean, nullable=False)
    sombreamentoNatural = Column(Boolean, nullable=False)
    protecaoVentosFortes = Column(Boolean, nullable=False)
    distanciaSeguraContaminacao = Column(Boolean, nullable=False)
    distanciaMinimaConstrucoes = Column(Boolean, nullable=False)
    distanciaSeguraLavouras = Column(Boolean, nullable=False)
    capacidadeDeSuporte = Column(String, nullable=True)

    userId = Column(Integer, ForeignKey('users.id'), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    owner = relationship(
        "User",
        back_populates="meliponaries",
    )