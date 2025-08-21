from typing import Optional
from pydantic import BaseModel as SCBaseModel, Field
from datetime import datetime

class MeliponaryCreateSchema(SCBaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="O campo nome é obrigatório")
    latitude: str = Field(..., description="O campo latitude é obrigatório")
    longitude: str = Field(..., description="O campo longitude é obrigatório")
    tipoInstalacao: str = Field(..., description="O campo Tipo instalação é obrigatório")
    especieAbelha: Optional[str]
    quantidadeColmeias: str = Field(..., description="O campo Quantidade de colmeias é obrigatório")
    outrosMeliponariosRaio1km: bool = Field(..., description="O campo Outros meliponários no raio de 1km é obrigatório")
    qtdColmeiasOutrosMeliponarios: Optional[str] = None
    fontesNectarPolen: bool = Field(..., description="O campo Fontes de néctar e pólen é obrigatório")
    disponibilidadeAgua: bool = Field(..., description="O campo Disponibilidade de água é obrigatório")
    sombreamentoNatural: bool = Field(..., description="O campo Sombreamento natural é obrigatório")
    protecaoVentosFortes: bool = Field(..., description="O campo Proteção contra ventos fortes é obrigatório")
    distanciaSeguraContaminacao: bool = Field(..., description="O campo Distância segura de contaminação é obrigatório")
    distanciaMinimaConstrucoes: bool = Field(..., description="O campo Distância mínima de construções é obrigatório")
    distanciaSeguraLavouras: bool = Field(..., description="O campo Distância segura de lavouras é obrigatório")

    class Config:
        from_attributes = True


class MeliponarySchema(SCBaseModel):
    id: int
    name: str
    latitude: str
    longitude: str
    tipoInstalacao: str
    especieAbelha: Optional[str]
    quantidadeColmeias: str
    outrosMeliponariosRaio1km: bool
    qtdColmeiasOutrosMeliponarios: Optional[str]
    fontesNectarPolen: bool
    disponibilidadeAgua: bool
    sombreamentoNatural: bool
    protecaoVentosFortes: bool
    distanciaSeguraContaminacao: bool
    distanciaMinimaConstrucoes: bool
    distanciaSeguraLavouras: bool
    capacidadeDeSuporte: Optional[str]
    userId: int
    createdAt: datetime
    updatedAt: Optional[datetime]

    class Config:
        from_attributes = True