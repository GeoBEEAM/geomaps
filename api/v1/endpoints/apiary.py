from typing import List

from fastapi import APIRouter, Depends, status, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.deps import get_session, get_current_user
from models import User, Apiary
from schemas.apiary_schema import ApiaryCreateSchema, ApiarySchema
from utils import verify_user_exists, process_geojson

apiary_router = APIRouter()


@apiary_router.get('/all', response_model=List[ApiarySchema])
async def get_all_apiaries(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Apiary))
    return result.scalars().all()


@apiary_router.get('/', response_model=List[ApiarySchema])
async def get_apiaries(session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user), ):
    result = await session.execute(select(Apiary))
    return result.scalars().all()


@apiary_router.post('/', response_model=ApiarySchema, status_code=status.HTTP_201_CREATED)
async def create_meliponary(
        apiary: ApiaryCreateSchema,
        auth_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
):
    await verify_user_exists(auth_user.id, session)
    suporte = await process_geojson(apiary.latitude, apiary.longitude, auth_user.role, )
    capacidade_de_suporte = suporte - apiary.qtdColmeiasOutrosApiarios if apiary.qtdColmeiasOutrosApiarios else suporte
    new_apiary = Apiary(
        name=apiary.name,
        latitude=apiary.latitude,
        longitude=apiary.longitude,
        tipoInstalacao=apiary.tipoInstalacao,
        tempoItinerante=apiary.tempoItinerante,
        quantidadeColmeias=apiary.quantidadeColmeias,
        outrosApiariosRaio3km=apiary.outrosApiariosRaio3km,
        qtdColmeiasOutrosApiarios=apiary.qtdColmeiasOutrosApiarios,
        fontesNectarPolen=apiary.fontesNectarPolen,
        disponibilidadeAgua=apiary.disponibilidadeAgua,
        sombreamentoNatural=apiary.sombreamentoNatural,
        protecaoVentosFortes=apiary.protecaoVentosFortes,
        distanciaSeguraContaminacao=apiary.distanciaSeguraContaminacao,
        distanciaMinimaConstrucoes=apiary.distanciaMinimaConstrucoes,
        distanciaSeguraLavouras=apiary.distanciaSeguraLavouras,
        acessoVeiculos=apiary.acessoVeiculos,
        capacidadeDeSuporte=str(capacidade_de_suporte),
        userId=auth_user.id
    )
    session.add(new_apiary)
    await session.commit()
    await session.refresh(new_apiary)
    return new_apiary


@apiary_router.get('/{id}', response_model=ApiarySchema)
async def get_apiary(id: int, session: AsyncSession = Depends(get_session),
                     auth_user: User = Depends(get_current_user), ):
    result = await session.execute(select(Apiary).filter(Apiary.id == id))
    meliponary = result.scalar()
    if meliponary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Apiary not found')
    return meliponary


@apiary_router.put('/{id}', response_model=ApiaryCreateSchema)
async def update_apiary(id: int, apiary: ApiaryCreateSchema, session: AsyncSession = Depends(get_session),
                        auth_user: User = Depends(get_current_user), ):
    await verify_user_exists(apiary.userId, session)
    result = await session.execute(select(Apiary).filter(Apiary.id == id))
    apiary_db = result.scalar()
    if apiary_db is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Apiary not found')
    apiary_db.update(**apiary.model_dump())
    await session.commit()
    await session.refresh(apiary_db)
    return apiary_db


@apiary_router.delete('/{id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_meliponary(id: int, session: AsyncSession = Depends(get_session),
                            auth_user: User = Depends(get_current_user), ):
    result = await session.execute(select(Apiary).filter(Apiary.id == id))
    apiary = result.scalar_one_or_none()
    if apiary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Apiary not found')
    await session.delete(apiary)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
