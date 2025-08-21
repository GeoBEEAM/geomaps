import logging
import sys
from typing import List

from fastapi import APIRouter, Depends, status, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from shapely.geometry import Point

from core.deps import get_session, get_current_user
from core.messages import MSG_LIMIT_MELIPONARY, MSG_UPGRADE_OPTIONS, MSG_MELIPONARY_NOT_FOUND, MSG_FORBIDDEN_VIEW_MELIPONARY, MSG_FORBIDDEN_UPDATE_MELIPONARY
from models import User
from models.meliponary import Meliponary
from schemas.meliponary_schema import MeliponaryCreateSchema, MeliponarySchema
from utils import verify_user_exists, calcular_capacidade_suporte_meliponicultura, area_vegetacao_dentro_buffer_meliponario, calcular_raio_voo_meliponario
from utils import identificar_bioma_por_ponto, verificar_sobreposicao_apiario
from utils.log_utils import log_action
from utils import process_meliponicultor

meliponary_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def calcular_colmeias_intersecao(longitude, latitude, raio_km, meliponaries):
    ponto_novo = Point(longitude, latitude)
    return sum(
        int(m.quantidadeColmeias)
        for m in meliponaries
        if Point(float(m.longitude), float(m.latitude)).distance(ponto_novo) <= raio_km / 111
    )


@meliponary_router.post('/', response_model=MeliponarySchema, status_code=status.HTTP_201_CREATED)
async def create_meliponary(
        meliponary: MeliponaryCreateSchema,
        auth_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session)
):
    """
    Cria um novo meliponário, calculando capacidade de suporte conforme regras técnicas e subtraindo colmeias existentes no raio.
    """
    logger.info(f"Iniciando criação de meliponário para usuário {auth_user.id}")
    await verify_user_exists(auth_user.id, session)
    # Validação básica dos dados
    if not meliponary.latitude or not meliponary.longitude:
        raise HTTPException(status_code=400, detail="Latitude e longitude são obrigatórios.")
    if not meliponary.especieAbelha:
        raise HTTPException(status_code=400, detail="Espécie de abelha é obrigatória.")
    if not isinstance(meliponary.quantidadeColmeias, (int, str)) or int(meliponary.quantidadeColmeias) < 0:
        raise HTTPException(status_code=400, detail="Quantidade de colmeias deve ser um número não negativo.")
    # Verifica limite de meliponários
    result = await session.execute(select(Meliponary))
    all_meliponaries = result.scalars().all()
    user_meliponaries_count = len([m for m in all_meliponaries if m.userId == auth_user.id])
    if user_meliponaries_count >= auth_user.max_meliponaries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": MSG_LIMIT_MELIPONARY,
                "upgrade_options": MSG_UPGRADE_OPTIONS
            }
        )
    # Identifica bioma do ponto

    geojson_biomas_path = 'geojson_files/Brasil.json'
    longitude = float(meliponary.longitude)
    latitude = float(meliponary.latitude)
    bioma = identificar_bioma_por_ponto(longitude, latitude, geojson_biomas_path)
    if not bioma:
        logger.warning(f"Bioma não identificado para coordenadas ({latitude}, {longitude})")
        raise HTTPException(status_code=400, detail="coordenada nao mapeada no geojson ou bioma não identificado")
    # Calcula raio de voo
    raio_km = calcular_raio_voo_meliponario(meliponary.especieAbelha)
    # Monta lista de buffers existentes para passar ao process_meliponicultor
    from shapely.geometry import Point
    import geopandas as gpd
    crs_geo = "EPSG:4326"
    crs_metric = "EPSG:31983"
    buffers_existentes = []
    for m in all_meliponaries:
        centro = Point(float(m.longitude), float(m.latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer = gdf_centro.geometry.iloc[0].buffer(raio_km * 1000)
        buffers_existentes.append({"buffer": buffer, "colmeias": int(m.quantidadeColmeias)})
    # Calcula capacidade de suporte e área usando a função padronizada
    capacidade_permitida = process_meliponicultor(
        latitude=str(meliponary.latitude),
        longitude=str(meliponary.longitude),
        especie=meliponary.especieAbelha,
        raio_km=raio_km,
        buffers_existentes=buffers_existentes,
        return_area_only=False
    )
    if capacidade_permitida is None:
        raise HTTPException(status_code=400, detail="Erro ao calcular capacidade de suporte do meliponário.")
    # Subtrai colmeias existentes no raio
    colmeias_intersecao = calcular_colmeias_intersecao(longitude, latitude, raio_km, all_meliponaries)
    logger.info(f"Colmeias existentes no raio: {colmeias_intersecao}")
    capacidade_permitida = max(capacidade_permitida - colmeias_intersecao, 0)
    logger.info(f"Capacidade permitida final: {capacidade_permitida}")
    # Salva meliponário com a capacidade calculada
    new_meliponary = Meliponary(
        name=meliponary.name,
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
        capacidadeDeSuporte=str(capacidade_permitida),
        userId=auth_user.id
    )
    session.add(new_meliponary)
    await session.commit()
    await session.refresh(new_meliponary)
    response = new_meliponary.__dict__.copy()
    logger.info(f"Meliponário criado com sucesso para usuário {auth_user.id}")
    return response


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_MELIPONARY_NOT_FOUND)
    if meliponary.userId != auth_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MSG_FORBIDDEN_VIEW_MELIPONARY)
    return meliponary


@meliponary_router.put('/{id}', response_model=MeliponaryCreateSchema)
async def update_meliponary(id: int, meliponary: MeliponaryCreateSchema, session: AsyncSession = Depends(get_session),
                            auth_user: User = Depends(get_current_user), ):
    await verify_user_exists(meliponary.userId, session)
    result = await session.execute(select(Meliponary).filter(Meliponary.id == id))
    meliponary_db = result.scalar()
    if meliponary_db is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_MELIPONARY_NOT_FOUND)
    # Só permite atualizar se o usuário for o dono
    if meliponary_db.userId != auth_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MSG_FORBIDDEN_UPDATE_MELIPONARY)
    # Atualiza os campos manualmente
    for key, value in meliponary.model_dump().items():
        setattr(meliponary_db, key, value)
    await session.commit()
    await session.refresh(meliponary_db)
    return meliponary_db


@meliponary_router.delete('/{id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_meliponary(id: int, session: AsyncSession = Depends(get_session),
                            auth_user: User = Depends(get_current_user), ):
    result = await session.execute(select(Meliponary).filter(Meliponary.id == id))
    meliponary = result.scalar_one_or_none()
    if meliponary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_MELIPONARY_NOT_FOUND)
    # Só permite deletar se o usuário for o dono
    if meliponary.userId != auth_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Você não tem permissão para deletar este meliponário.")
    async with session.begin():
        await session.delete(meliponary)
        await log_action(session, user_id=auth_user.id, action="DELETE", entity="MELIPONARY", entity_id=meliponary.id,
                         details=f"Meliponário deletado: {meliponary.name}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
