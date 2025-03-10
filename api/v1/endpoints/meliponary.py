import logging
from typing import List

from fastapi import APIRouter, Depends, status, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.deps import get_session, get_current_user
from models import User
from models.meliponary import Meliponary
from schemas.meliponary_schema import MeliponaryCreateSchema, MeliponarySchema
from utils import verify_user_exists, process_geojson

meliponary_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@meliponary_router.post('/', response_model=MeliponarySchema, status_code=status.HTTP_201_CREATED)
async def create_meliponary(
        meliponary: MeliponaryCreateSchema,
        auth_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
):
    await verify_user_exists(auth_user.id, session)
    suporte = await process_geojson(meliponary.latitude, meliponary.longitude, auth_user.role, meliponary.especieAbelha)
    if suporte is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to calculate support capacity")
    capacidade_de_suporte = int(suporte) - int(
        meliponary.qtdColmeiasOutrosMeliponarios) if meliponary.qtdColmeiasOutrosMeliponarios else int(suporte)
    new_meliponary = Meliponary(name=meliponary.name,
                                latitude=meliponary.latitude,
                                longitude=meliponary.longitude,
                                tipoInstalacao=meliponary.tipoInstalacao,
                                especieAbelha=meliponary.especieAbelha,
                                quantidadeColmeias=meliponary.quantidadeColmeias,
                                outrosMeliponariosRaio1km=meliponary.outrosMeliponariosRaio1km,
                                qtdColmeiasOutrosMeliponarios=meliponary.qtdColmeiasOutrosMeliponarios,
                                fontesNectarPolen=meliponary.fontesNectarPolen,
                                disponibilidadeAgua=meliponary.disponibilidadeAgua,
                                sombreamentoNatural=meliponary.sombreamentoNatural,
                                protecaoVentosFortes=meliponary.protecaoVentosFortes,
                                distanciaSeguraContaminacao=meliponary.distanciaSeguraContaminacao,
                                distanciaMinimaConstrucoes=meliponary.distanciaMinimaConstrucoes,
                                distanciaSeguraLavouras=meliponary.distanciaSeguraLavouras,
                                capacidadeDeSuporte=str(capacidade_de_suporte),
                                userId=auth_user.id
                                )
    session.add(new_meliponary)
    await session.commit()
    await session.refresh(new_meliponary)
    return new_meliponary


@meliponary_router.get('/all', response_model=List[MeliponarySchema])
async def get_all_meliponaries(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Meliponary))
    return result.scalars().all()

@meliponary_router.get('/', response_model=List[MeliponarySchema])
async def get_meliponaries(session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(Meliponary).filter(Meliponary.userId == auth_user.id))
    return result.scalars().all()


@meliponary_router.get('/{id}', response_model=MeliponarySchema)
async def get_meliponary(id: int, session: AsyncSession = Depends(get_session),
                         auth_user: User = Depends(get_current_user), ):
    result = await session.execute(select(Meliponary).filter(Meliponary.id == id))
    meliponary = result.scalar()
    if meliponary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Meliponary not found')
    return meliponary


@meliponary_router.put('/{id}', response_model=MeliponaryCreateSchema)
async def update_meliponary(id: int, meliponary: MeliponaryCreateSchema, session: AsyncSession = Depends(get_session),
                            auth_user: User = Depends(get_current_user), ):
    await verify_user_exists(meliponary.userId, session)
    result = await session.execute(select(Meliponary).filter(Meliponary.id == id))
    meliponary_db = result.scalar()
    if meliponary_db is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Meliponary not found')
    meliponary_db.update(**meliponary.model_dump())
    await session.commit()
    await session.refresh(meliponary_db)
    return meliponary_db


@meliponary_router.delete('/{id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_meliponary(id: int, session: AsyncSession = Depends(get_session),
                            auth_user: User = Depends(get_current_user), ):
    result = await session.execute(select(Meliponary).filter(Meliponary.id == id))
    meliponary = result.scalar_one_or_none()
    if meliponary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Meliponary not found')
    await session.delete(meliponary)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
