from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from datetime import datetime

from core.configs import settings


class Apiary(settings.DBBaseModel):
    __tablename__ = 'apiaries'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    latitude = Column(String, nullable=False)
    longitude = Column(String, nullable=False)
    tipoInstalacao = Column(String, nullable=False)
    tempoItinerante = Column(String, nullable=True)
    quantidadeColmeias = Column(String, nullable=False)
    outrosApiariosRaio3km = Column(Boolean, nullable=False)
    qtdColmeiasOutrosApiarios = Column(String, nullable=True)
    fontesNectarPolen = Column(Boolean, nullable=False)
    disponibilidadeAgua = Column(Boolean, nullable=False)
    sombreamentoNatural = Column(Boolean, nullable=False)
    protecaoVentosFortes = Column(Boolean, nullable=False)
    distanciaSeguraContaminacao = Column(Boolean, nullable=False)
    distanciaMinimaConstrucoes = Column(Boolean, nullable=False)
    distanciaSeguraLavouras = Column(Boolean, nullable=False)
    acessoVeiculos = Column(Boolean, nullable=False)
    capacidadeDeSuporte = Column(String, nullable=True)

    userId = Column(Integer, ForeignKey('users.id'), nullable=False)
    createdAt = Column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    owner = relationship("User", back_populates="apiaries")