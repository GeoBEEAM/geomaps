import logging
from typing import List

from fastapi import APIRouter, Depends, status, HTTPException, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from core.deps import get_session, get_current_user
from core.messages import MSG_LIMIT_APIARY, MSG_UPGRADE_OPTIONS, MSG_APIARY_NOT_FOUND, MSG_FORBIDDEN_VIEW_APIARY, \
    MSG_FORBIDDEN_UPDATE_APIARY, MSG_FORBIDDEN_DELETE_APIARY
from models import User, Apiary
from schemas.apiary_schema import ApiaryCreateSchema, ApiarySchema
from utils import verify_user_exists, process_apicultor, identificar_bioma_por_ponto
from utils.log_utils import log_action
from shapely.geometry import Point
import geopandas as gpd

apiary_router = APIRouter()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@apiary_router.get('/', response_model=List[ApiarySchema])
async def get_apiaries(session: AsyncSession = Depends(get_session), auth_user: User = Depends(get_current_user)):
    result = await session.execute(select(Apiary).filter(Apiary.userId == auth_user.id))
    return result.scalars().all()


@apiary_router.post('/', response_model=ApiarySchema, status_code=status.HTTP_201_CREATED)
async def create_apiary(
        apiary: ApiaryCreateSchema,
        auth_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
        allow_same_point: bool = Query(False, description="Permitir cadastro no mesmo ponto se já existir")
):
    await verify_user_exists(auth_user.id, session)
    # Validações de entrada
    if apiary.latitude is None or apiary.longitude is None:
        raise HTTPException(status_code=400, detail="Latitude e longitude são obrigatórios.")
    try:
        _lat = float(apiary.latitude)
        _lon = float(apiary.longitude)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Latitude e longitude devem ser numéricos.")
    if not (-90.0 <= _lat <= 90.0) or not (-180.0 <= _lon <= 180.0):
        raise HTTPException(status_code=400, detail="Latitude deve estar entre -90 e 90 e longitude entre -180 e 180.")
    try:
        _qtd_colmeias = int(apiary.quantidadeColmeias)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Quantidade de colmeias deve ser um número inteiro.")
    if _qtd_colmeias < 0:
        raise HTTPException(status_code=400, detail="Quantidade de colmeias deve ser um número não negativo.")
    # Verifica limite de apiários do usuário de forma eficiente
    count_result = await session.execute(
        select(func.count()).select_from(Apiary).filter(Apiary.userId == auth_user.id)
    )
    user_apiaries_count = int(count_result.scalar() or 0)
    logger.info(f"Usuário {auth_user.id} possui {user_apiaries_count} apiários (máximo: {auth_user.max_apiaries})")
    if user_apiaries_count >= auth_user.max_apiaries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": MSG_LIMIT_APIARY,
                "upgrade_options": MSG_UPGRADE_OPTIONS
            }
        )
    # Carrega todos os apiários para construção de buffers e verificação de duplicidade de coordenadas
    result = await session.execute(select(Apiary))
    all_apiaries = result.scalars().all()
    # Verifica se já existe apiário na mesma coordenada (condicional)
    if not allow_same_point:
        for a in all_apiaries:
            if float(a.latitude) == float(apiary.latitude) and float(a.longitude) == float(apiary.longitude):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Já existe um apiário cadastrado nesta coordenada."
                )
    # Monta lista de buffers existentes para passar ao process_apicultor
    crs_geo = "EPSG:4326"
    crs_metric = "EPSG:31983"
    buffers_existentes = []
    for a in all_apiaries:
        centro = Point(float(a.longitude), float(a.latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer = gdf_centro.geometry.iloc[0].buffer(1500)
        buffers_existentes.append({"buffer": buffer, "colmeias": int(a.quantidadeColmeias)})

    # Identifica bioma do ponto e garante aplicação das regras por bioma/cultura
    geojson_biomas_path = 'geojson_files/Brasil.json'
    bioma = identificar_bioma_por_ponto(_lon, _lat, geojson_biomas_path)
    if not bioma:
        logger.warning(f"Bioma não identificado para coordenadas ({_lat}, {_lon})")
        raise HTTPException(status_code=400, detail="coordenada nao mapeada no geojson ou bioma não identificado")

    try:
        suporte = process_apicultor(
            latitude=str(apiary.latitude),
            longitude=str(apiary.longitude),
            buffers_existentes=buffers_existentes,
            return_area_only=False,
            bioma=bioma
        )
    except Exception as exc:
        logger.error(f"Erro ao calcular capacidade de suporte: {exc}")
        if hasattr(exc, 'detail') and exc.detail == "coordenada nao mapeada no geojson":
            raise HTTPException(status_code=400, detail="coordenada nao mapeada no geojson")
        raise HTTPException(status_code=400, detail=str(exc))

    # Subtrai colmeias informadas no questionário (quando aplicável)
    extra_questionario = 0
    if getattr(apiary, "outrosApiariosRaio3km", False):
        try:
            extra_questionario = int(apiary.qtdColmeiasOutrosApiarios or 0)
        except (TypeError, ValueError):
            extra_questionario = 0

    capacidade_permitida = int(suporte) if suporte is not None else 0
    capacidade_permitida = max(capacidade_permitida - extra_questionario, 0)
    logger.info(f"Capacidade permitida final: {capacidade_permitida}")
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
    response = new_apiary.__dict__.copy()
    logger.info(f"Apiário criado com sucesso para usuário {auth_user.id}")
    return response


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


@apiary_router.put('/{id}', response_model=ApiarySchema)
async def update_apiary(id: int, apiary: ApiaryCreateSchema, session: AsyncSession = Depends(get_session),
                        auth_user: User = Depends(get_current_user), ):
    await verify_user_exists(auth_user.id, session)
    result = await session.execute(select(Apiary).filter(Apiary.id == id))
    apiary_db = result.scalar()
    if apiary_db is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_APIARY_NOT_FOUND)
    if apiary_db.userId != auth_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MSG_FORBIDDEN_UPDATE_APIARY)
    # Protege campos imutáveis
    for key, value in apiary.model_dump().items():
        if key in {"id", "userId"}:
            continue
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
