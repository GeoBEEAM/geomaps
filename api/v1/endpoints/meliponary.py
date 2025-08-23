import logging
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from shapely.geometry import Point
from core.deps import get_session, get_current_user
from core.messages import MSG_LIMIT_MELIPONARY, MSG_UPGRADE_OPTIONS, MSG_MELIPONARY_NOT_FOUND, MSG_FORBIDDEN_VIEW_MELIPONARY, MSG_FORBIDDEN_UPDATE_MELIPONARY
from models import User
from models.meliponary import Meliponary
from schemas.meliponary_schema import MeliponaryCreateSchema, MeliponarySchema
from utils import verify_user_exists, calcular_raio_voo_meliponario, identificar_bioma_por_ponto, process_meliponicultor
from utils.log_utils import log_action

meliponary_router = APIRouter()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@meliponary_router.post('', response_model=MeliponarySchema, status_code=status.HTTP_201_CREATED)
async def create_meliponary(
        meliponary: MeliponaryCreateSchema,
        auth_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
        allow_same_point: bool = Query(False, description="Permitir cadastro no mesmo ponto se já existir")
):
    """
    Cria um novo meliponário, calculando capacidade de suporte conforme regras técnicas e subtraindo colmeias existentes no raio.
    Retorna também os detalhes do cálculo na resposta.
    """
    logger.info(f"Iniciando criação de meliponário para usuário {auth_user.id}")
    await verify_user_exists(auth_user.id, session)
    # Validação básica dos dados com checagem de tipo e faixas geográficas
    if meliponary.latitude is None or meliponary.longitude is None:
        raise HTTPException(status_code=400, detail="Latitude e longitude são obrigatórios.")
    if not meliponary.especieAbelha or not str(meliponary.especieAbelha).strip():
        raise HTTPException(status_code=400, detail="Espécie de abelha é obrigatória.")
    try:
        _lat = float(meliponary.latitude)
        _lon = float(meliponary.longitude)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Latitude e longitude devem ser numéricos.")
    if not (-90.0 <= _lat <= 90.0) or not (-180.0 <= _lon <= 180.0):
        raise HTTPException(status_code=400, detail="Latitude deve estar entre -90 e 90 e longitude entre -180 e 180.")
    try:
        _qtd_colmeias = int(meliponary.quantidadeColmeias)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Quantidade de colmeias deve ser um número inteiro.")
    if _qtd_colmeias < 0:
        raise HTTPException(status_code=400, detail="Quantidade de colmeias deve ser um número não negativo.")
    # Verifica limite de meliponários (consulta eficiente)
    count_result = await session.execute(
        select(func.count()).select_from(Meliponary).filter(Meliponary.userId == auth_user.id)
    )
    user_meliponaries_count = int(count_result.scalar() or 0)
    if user_meliponaries_count >= auth_user.max_meliponaries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": MSG_LIMIT_MELIPONARY,
                "upgrade_options": MSG_UPGRADE_OPTIONS
            }
        )
    # Carrega todos os meliponários após a validação de limite (usados para buffers de interseção)
    result_all = await session.execute(select(Meliponary))
    all_meliponaries = result_all.scalars().all()
    # Verificação de coordenada duplicada (opcional)
    if not allow_same_point:
        for m in all_meliponaries:
            if float(m.latitude) == float(meliponary.latitude) and float(m.longitude) == float(meliponary.longitude):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um meliponário cadastrado nesta coordenada.")
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
    import geopandas as gpd
    crs_geo = "EPSG:4326"
    crs_metric = "EPSG:31983"
    buffers_existentes = []
    for m in all_meliponaries:
        try:
            r_km_existente = calcular_raio_voo_meliponario(m.especieAbelha) or raio_km
        except Exception:
            r_km_existente = raio_km
        centro = Point(float(m.longitude), float(m.latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer = gdf_centro.geometry.iloc[0].buffer(r_km_existente * 1000)
        buffers_existentes.append({"buffer": buffer, "colmeias": int(m.quantidadeColmeias)})
    # Calcula capacidade de suporte e área usando a função padronizada
    resultado = process_meliponicultor(
        latitude=str(meliponary.latitude),
        longitude=str(meliponary.longitude),
        especie=meliponary.especieAbelha,
        raio_km=raio_km,
        buffers_existentes=buffers_existentes,
        return_area_only=False
    )
    if resultado is None:
        raise HTTPException(status_code=400, detail="Erro ao calcular capacidade de suporte do meliponário.")
    logger.info(f"Capacidade permitida final: {resultado['capacidade_final']}")
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
        capacidadeDeSuporte=str(resultado['capacidade_final']),
        userId=auth_user.id
    )
    session.add(new_meliponary)
    await session.commit()
    await session.refresh(new_meliponary)
    response = new_meliponary.__dict__.copy()
    # Adiciona os detalhes do cálculo na resposta
    response["calculo_meliponario"] = {
        "capacidade_final": resultado["capacidade_final"],
        "capacidade_calculada": resultado["capacidade_calculada"],
        "area_total": resultado["area_total"],
        "areas_por_vegetacao": resultado["areas_por_vegetacao"],
        "raio_buffer": resultado["raio_buffer"],
        "colmeias_existentes": resultado["colmeias_existentes"]
    }
    logger.info(f"Meliponário criado com sucesso para usuário {auth_user.id}")
    return response


@meliponary_router.get('', response_model=List[MeliponarySchema])
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


@meliponary_router.put('/{id}', response_model=MeliponarySchema)
async def update_meliponary(id: int, meliponary: MeliponaryCreateSchema, session: AsyncSession = Depends(get_session),
                            auth_user: User = Depends(get_current_user), ):
    await verify_user_exists(auth_user.id, session)
    result = await session.execute(select(Meliponary).filter(Meliponary.id == id))
    meliponary_db = result.scalar()
    if meliponary_db is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MSG_MELIPONARY_NOT_FOUND)
    # Só permite atualizar se o usuário for o dono
    if meliponary_db.userId != auth_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MSG_FORBIDDEN_UPDATE_MELIPONARY)
    # Atualiza os campos manualmente, protegendo campos imutáveis
    for key, value in meliponary.model_dump().items():
        if key in {"id", "userId"}:
            continue
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
    # Executa a exclusão e o log na mesma transação implícita e confirma
    await session.delete(meliponary)
    await log_action(session, user_id=auth_user.id, action="DELETE", entity="MELIPONARY", entity_id=meliponary.id,
                     details=f"Meliponário deletado: {meliponary.name}")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
