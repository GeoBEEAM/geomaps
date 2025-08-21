from typing import Optional
from pydantic import BaseModel as SCBaseModel
from datetime import datetime

class ApiaryCreateSchema(SCBaseModel):
    name: str
    latitude: str
    longitude: str
    tipoInstalacao: str
    tempoItinerante: Optional[str] = None
    quantidadeColmeias: str
    outrosApiariosRaio3km: bool
    qtdColmeiasOutrosApiarios: Optional[str] = None
    fontesNectarPolen: bool
    disponibilidadeAgua: bool
    sombreamentoNatural: bool
    protecaoVentosFortes: bool
    distanciaSeguraContaminacao: bool
    distanciaMinimaConstrucoes: bool
    distanciaSeguraLavouras: bool
    acessoVeiculos: bool

    class Config:
        from_attributes = True


class ApiarySchema(SCBaseModel):
    id: Optional[int]
    name: str
    latitude: str
    longitude: str
    tipoInstalacao: str
    tempoItinerante: Optional[str]
    quantidadeColmeias: str
    outrosApiariosRaio3km: bool
    qtdColmeiasOutrosApiarios: Optional[str]
    fontesNectarPolen: bool
    disponibilidadeAgua: bool
    sombreamentoNatural: bool
    protecaoVentosFortes: bool
    distanciaSeguraContaminacao: bool
    distanciaMinimaConstrucoes: bool
    distanciaSeguraLavouras: bool
    acessoVeiculos: bool
    capacidadeDeSuporte: Optional[str]
    userId: int
    createdAt: datetime
    updatedAt: Optional[datetime]

    class Config:
        from_attributes = True
