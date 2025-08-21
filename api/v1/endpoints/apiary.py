from typing import List

from fastapi import APIRouter, Depends, status, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.deps import get_session, get_current_user
from core.messages import MSG_LIMIT_APIARY, MSG_UPGRADE_OPTIONS, MSG_APIARY_NOT_FOUND, MSG_FORBIDDEN_VIEW_APIARY, \
    MSG_FORBIDDEN_UPDATE_APIARY, MSG_FORBIDDEN_DELETE_APIARY
from models import User, Apiary
from schemas.apiary_schema import ApiaryCreateSchema, ApiarySchema
from utils import verify_user_exists, process_apicultor
from utils.log_utils import log_action

apiary_router = APIRouter()


@apiary_router.get('/', response_model=List[ApiarySchema])
async def get_apiaries(session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user), ):
    result = await session.execute(select(Apiary))
    return result.scalars().all()


@apiary_router.post('/', response_model=ApiarySchema, status_code=status.HTTP_201_CREATED)
async def create_apiary(
        apiary: ApiaryCreateSchema,
        auth_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
):
    await verify_user_exists(auth_user.id, session)
    result = await session.execute(select(Apiary))
    all_apiaries = result.scalars().all()
    user_apiaries_count = len([a for a in all_apiaries if a.userId == auth_user.id])
    print(f"User {auth_user.id} has {user_apiaries_count} apiaries e {auth_user.max_apiaries} max apiaries.")
    if user_apiaries_count >= auth_user.max_apiaries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": MSG_LIMIT_APIARY,
                "upgrade_options": MSG_UPGRADE_OPTIONS
            }
        )
    # Verifica se já existe apiário na mesma coordenada
    for a in all_apiaries:
        if float(a.latitude) == float(apiary.latitude) and float(a.longitude) == float(apiary.longitude):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Já existe um apiário cadastrado nesta coordenada."
            )

    # Monta lista de buffers existentes para passar ao process_apicultor
    from shapely.geometry import Point
    import geopandas as gpd
    crs_geo = "EPSG:4326"
    crs_metric = "EPSG:31983"
    buffers_existentes = []
    for a in all_apiaries:
        centro = Point(float(a.longitude), float(a.latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer = gdf_centro.geometry.iloc[0].buffer(1500)
        buffers_existentes.append({"buffer": buffer, "colmeias": int(a.quantidadeColmeias)})

    try:
        suporte = process_apicultor(
            latitude=str(apiary.latitude),
            longitude=str(apiary.longitude),
            buffers_existentes=buffers_existentes,
            return_area_only=False
        )
    except Exception as exc:
        if hasattr(exc, 'detail') and exc.detail == "coordenada nao mapeada no geojson":
            raise HTTPException(status_code=400, detail="coordenada nao mapeada no geojson")
        raise HTTPException(status_code=400, detail=str(exc))
    capacidade_permitida = int(suporte) if suporte is not None else 0
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
        capacidadeDeSuporte=str(capacidade_permitida),
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
    apiary = result.scalar()
    if apiary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_APIARY_NOT_FOUND)
    if apiary.userId != auth_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MSG_FORBIDDEN_VIEW_APIARY)
    return apiary


@apiary_router.put('/{id}', response_model=ApiaryCreateSchema)
async def update_apiary(id: int, apiary: ApiaryCreateSchema, session: AsyncSession = Depends(get_session),
                        auth_user: User = Depends(get_current_user), ):
    await verify_user_exists(apiary.userId, session)
    result = await session.execute(select(Apiary).filter(Apiary.id == id))
    apiary_db = result.scalar()
    if apiary_db is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_APIARY_NOT_FOUND)
    if apiary_db.userId != auth_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MSG_FORBIDDEN_UPDATE_APIARY)
    for key, value in apiary.model_dump().items():
        setattr(apiary_db, key, value)
    async with session.begin():
        await log_action(session, user_id=auth_user.id, action="UPDATE", entity="APIARY", entity_id=apiary_db.id,
                         details=f"Apiário atualizado: {apiary_db.name}")
    await session.refresh(apiary_db)
    return apiary_db


@apiary_router.delete('/{id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_apiary(id: int, session: AsyncSession = Depends(get_session),
                        auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(Apiary).filter(Apiary.id == id))
    apiary = result.scalar_one_or_none()
    if not apiary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_APIARY_NOT_FOUND)
    if apiary.userId != auth_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MSG_FORBIDDEN_DELETE_APIARY)
    async with session.begin():
        await session.delete(apiary)
        await log_action(session, user_id=auth_user.id, action="DELETE", entity="APIARY", entity_id=apiary.id,
                         details=f"Apiário deletado: {apiary.name}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@apiary_router.post('/apicultor-area', status_code=status.HTTP_200_OK)
async def apicultor_area(
        apiary: ApiaryCreateSchema
):
    try:
        resultado = process_apicultor(
            latitude=str(apiary.latitude),
            longitude=str(apiary.longitude),
            buffers_existentes=None,
            return_area_only=False
        )
        return {"capacidadeDeSuporte": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
