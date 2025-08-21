import json
import os
from typing import Optional, List
from fastapi import status, HTTPException
from minio import Minio
from minio.error import S3Error
from shapely.geometry import Point, shape
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import geopandas as gpd
import pandas as pd
from models import User

# MinIO configuration
MINIO_URL = os.getenv('MINIO_URL')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME')

minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

GEOJSON_CACHE_DIR = os.path.join(os.path.dirname(__file__), '../../geojson_files_cache')
os.makedirs(GEOJSON_CACHE_DIR, exist_ok=True)

VEGETACAO_APICULTOR = ['ARBOREO', 'ARBUSTIVO', 'HERBACEO']
VEGETACAO_MELIPONARIO = ['ARBOREO', 'ARBUSTIVO']  # Ajuste conforme regra do negócio


def calcular_raio_voo_meliponario(especie=None):
    if especie in ['Frieseomelitta silvestrii', 'Frieseomelitta longipes', 'Frieseomelitta doederleini', 'Tetragonisca angustula']:
        return 0.5
    elif especie in ['Scaptotrigona polysticta', 'Melipona subnitida', 'Melipona seminigra', 'Melipona flavolineata', 'Melipona fasciculata']:
        return 2.5
    else:
        return 1.2


def calcular_raio_voo_apiario():
    return 1.5


def calcular_capacidade_suporte_apicultura(area_ha: float, bioma: str, tipo_cultura: str = None) -> int:
    print(f"[LOG] Calculando capacidade de suporte para área: {area_ha} ha, bioma: {bioma}, tipo de cultura: {tipo_cultura}")
    if bioma in ['Amazônia', 'Mata Atlântica']:
        return int(area_ha / 7.07)
    elif bioma in ['Cerrado', 'Pantanal']:
        return int((area_ha / 7.07) * 2)
    elif bioma in ['Agreste', 'Semiárido']:
        return int((area_ha / 7.07) * 4)
    elif tipo_cultura in ['Eucalipto', 'Girassol', 'Canola', 'Floríferas']:
        return int((area_ha / 7.07) * 4)
    elif tipo_cultura == 'Acácia Mangium':
        return int((area_ha / 7.07) * 8)
    else:
        return int(area_ha / 7.07)


def calcular_capacidade_suporte_meliponicultura(area_ha: float) -> int:
    # 256 árvores = 2,5 colmeias/hectare
    return int(area_ha * 2.5)


def list_geojson_files_from_minio() -> List[str]:
    try:
        objects = minio_client.list_objects(MINIO_BUCKET_NAME, prefix='', recursive=True)
        return [obj.object_name for obj in objects if obj.object_name.endswith('.geojson')]
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


def get_geojson_file_cached(filename):
    local_path = os.path.join(GEOJSON_CACHE_DIR, os.path.basename(filename))
    if not os.path.exists(local_path):
        response = minio_client.get_object(MINIO_BUCKET_NAME, filename)
        with open(local_path, 'wb') as f:
            f.write(response.read())
    return local_path


async def verify_user_exists(user_id: int, session: AsyncSession):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Usuário não existe no sistema')


def calcular_area_buffer(longitude: float, latitude: float, raio_km: float = 1.5, geojson_files: list = None):
    ponto = Point(float(longitude), float(latitude))
    buffer = ponto.buffer(raio_km * 1000)
    if not geojson_files:
        return buffer
    soma_areas = 0
    for filename in geojson_files:
        with open(filename, 'r') as f:
            geojson_data = json.load(f)
        for layer in geojson_data['features']:
            geom = shape(layer['geometry'])
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_valid and geom.intersects(buffer):
                intersecao = geom.intersection(buffer)
                if not intersecao.is_empty:
                    nome_camada = layer['properties'].get('CLASSE')
                    if nome_camada in VEGETACAO_APICULTOR:
                        soma_areas += intersecao.area / 10000.0
    return round(soma_areas, 2)


def area_vegetacao_dentro_buffer(longitude: float, latitude: float, raio_km: float = 1.5, geojson_files: list = None):
    ponto = Point(float(longitude), float(latitude))
    buffer = ponto.buffer(raio_km * 1000)
    soma_areas = 0
    if not geojson_files:
        return 0.0
    for filename in geojson_files:
        with open(filename, 'r') as f:
            geojson_data = json.load(f)
        for layer in geojson_data['features']:
            geom = shape(layer['geometry'])
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_valid and geom.intersects(buffer):
                intersecao = geom.intersection(buffer)
                if not intersecao.is_empty:
                    nome_camada = layer['properties'].get('CLASSE')
                    if nome_camada in VEGETACAO_APICULTOR:
                        soma_areas += intersecao.area / 10000.0
    return round(soma_areas, 2)


def area_vegetacao_dentro_buffer_apiario(longitude: float, latitude: float, raio_km: float = 1.5, geojson_files: list = None):
    ponto = Point(float(longitude), float(latitude))
    buffer = ponto.buffer(raio_km * 1000)
    soma_areas = 0
    if not geojson_files:
        return 0.0
    for filename in geojson_files:
        with open(filename, 'r') as f:
            geojson_data = json.load(f)
        for layer in geojson_data['features']:
            geom = shape(layer['geometry'])
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_valid and geom.intersects(buffer):
                intersecao = geom.intersection(buffer)
                if not intersecao.is_empty:
                    nome_camada = layer['properties'].get('CLASSE')
                    if nome_camada in VEGETACAO_APICULTOR:
                        soma_areas += intersecao.area / 10000.0
    return round(soma_areas, 2)


def area_vegetacao_dentro_buffer_meliponario(longitude: float, latitude: float, raio_km: float = 1.2, geojson_files: list = None):
    """
    Calcula a área de vegetação adequada para meliponário dentro do buffer circular (raio em km) ao redor do ponto.
    Considera apenas as classes de vegetação específicas para meliponário.
    """
    import logging
    logger = logging.getLogger(__name__)
    ponto = Point(float(longitude), float(latitude))
    buffer = ponto.buffer(raio_km * 1000)
    soma_areas = 0.0
    if not geojson_files:
        logger.warning("Nenhum arquivo geojson fornecido para cálculo de área de vegetação.")
        return 0.0
    logger.info(f"Iniciando cálculo de área de vegetação para meliponário em ({latitude}, {longitude}) com raio {raio_km} km.")
    for filename in geojson_files:
        try:
            with open(filename, 'r') as f:
                geojson_data = json.load(f)
            for layer in geojson_data['features']:
                geom = shape(layer['geometry'])
                if not geom.is_valid:
                    geom = geom.buffer(0)
                if geom.is_valid and geom.intersects(buffer):
                    intersecao = geom.intersection(buffer)
                    if not intersecao.is_empty:
                        nome_camada = layer['properties'].get('CLASSE')
                        if nome_camada in VEGETACAO_MELIPONARIO:
                            area_intersecao = intersecao.area / 10000.0
                            soma_areas += area_intersecao
                            logger.debug(f"Arquivo: {filename}, Classe: {nome_camada}, Área adicionada: {area_intersecao:.4f} ha")
        except Exception as e:
            logger.error(f"Erro ao processar arquivo {filename}: {e}")
    logger.info(f"Área total de vegetação adequada encontrada: {soma_areas:.2f} ha")
    return round(soma_areas, 2)


def read_files_from_directory(directory):
    files_data = {}
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            with open(file_path, 'r') as file:
                files_data[filename] = file.read()
    return files_data


def calcular_capacidade_apiario_novo(geom_novo, apiarios_existentes, calcular_capacidade_func):

    capacidade_total_novo = calcular_capacidade_func(geom_novo)
    capacidade_intersecoes = 0
    for apiario in apiarios_existentes:
        intersecao = geom_novo.intersection(apiario['geometry'])
        if not intersecao.is_empty:
            capacidade_intersecoes += calcular_capacidade_func(intersecao)
    # A capacidade permitida é só da área exclusiva (total - interseções)
    capacidade_permitida = capacidade_total_novo - capacidade_intersecoes
    # Não pode ser negativa
    return max(0, int(round(capacidade_permitida)))


def concat_geojsons(geojson_files, crs_geo="EPSG:4326", crs_metric="EPSG:31983"):
    """
    Recebe uma lista de caminhos de arquivos geojson e retorna um único GeoDataFrame concatenado, já reprojetado.
    """
    gdfs = []
    for filename in geojson_files:
        gdf = gpd.read_file(filename)
        # Garante que o CRS está correto
        if gdf.crs is None or gdf.crs.to_string() != crs_geo:
            gdf = gdf.set_crs(crs_geo)
        gdf = gdf.to_crs(crs_metric)
        gdfs.append(gdf)
    # Concatena todos
    gdf_todas = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=crs_metric)
    return gdf_todas



def existe_apiario_mesma_coordenada(latitude, longitude):
    # Função mock, implementar consulta real
    return False


def buscar_apiarios_no_raio(latitude, longitude, raio=1.5):
    # Função mock, implementar consulta real
    return []


def process_apicultor(latitude: str, longitude: str, buffers_existentes: Optional[list] = None, return_area_only: bool = False, bioma: str = None, tipo_cultura: str = None, tipo_producao: str = 'apicultura'):
    try:
        crs_metric = "EPSG:31983"
        crs_geo = "EPSG:4326"

        centro = Point(float(longitude), float(latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer_novo = gdf_centro.geometry.iloc[0].buffer(1500)  # 1.5km em metros

        # Verifica se já existe apiário na mesma coordenada
        if existe_apiario_mesma_coordenada(latitude, longitude):
            raise Exception('Já existe um apiário cadastrado nesta coordenada!')

        # Busca apiários no raio de 1.5km
        apiarios_intersecao = buscar_apiarios_no_raio(latitude, longitude, raio=1.5)
        colmeias_intersecao = sum([a.quantidadeColmeias for a in apiarios_intersecao])

        geojson_files = list_geojson_files_from_minio()
        gdf_todas = concat_geojsons([get_geojson_file_cached(f) for f in geojson_files], crs_geo, crs_metric)

        # Filtra vegetações e interseções
        gdf_vegetacao = gdf_todas[gdf_todas['CLASSE'].isin(VEGETACAO_APICULTOR)].copy()
        gdf_vegetacao = gdf_vegetacao[gdf_vegetacao.intersects(buffer_novo)].copy()
        gdf_vegetacao['intersecao'] = gdf_vegetacao.geometry.intersection(buffer_novo)
        gdf_vegetacao = gdf_vegetacao[~gdf_vegetacao['intersecao'].is_empty]
        gdf_vegetacao['area_intersecao_ha'] = gdf_vegetacao['intersecao'].area / 10000.0
        areas = gdf_vegetacao.groupby('CLASSE')['area_intersecao_ha'].sum().to_dict()
        soma_areas = sum([areas.get(tipo, 0) for tipo in VEGETACAO_APICULTOR])
        print(f"[LOG] Soma total das áreas dentro do buffer: {soma_areas:.2f} ha")
        print(f"[LOG] Áreas por vegetação no recorte de 1.5km: ARBOREO={areas.get('ARBOREO', 0):.2f} ha, ARBUSTIVO={areas.get('ARBUSTIVO', 0):.2f} ha, HERBACEO={areas.get('HERBACEO', 0):.2f} ha")
        area_total = soma_areas

        # Cálculo de capacidade de suporte
        if tipo_producao == 'apicultura':
            capacidade = calcular_capacidade_suporte_apicultura(area_total, bioma, tipo_cultura)
        else:
            capacidade = calcular_capacidade_suporte_meliponicultura(area_total)

        # Subtrai colmeias existentes no raio
        capacidade_final = capacidade - colmeias_intersecao
        if capacidade_final < 0:
            capacidade_final = 0
        print(f"[LOG] Capacidade de suporte final: {capacidade_final}")
        return capacidade_final if not return_area_only else area_total
    except Exception as e:
        print(f"[ERRO] {e}")
        return None


def identificar_bioma_por_ponto(longitude: float, latitude: float, geojson_biomas_path: str) -> Optional[str]:
    """
    Identifica o bioma de um ponto usando o GeoJSON de biomas do Brasil.
    Retorna o nome do bioma ou None se não encontrar.
    """
    try:
        import geopandas as gpd
        from shapely.geometry import Point, shape
        gdf = gpd.read_file(geojson_biomas_path)
        ponto = Point(longitude, latitude)
        for _, row in gdf.iterrows():
            if shape(row['geometry']).contains(ponto):
                nom_bioma = row.get('nom_bioma') or row.get('NOM_BIOMA') or row.get('name')
                return nom_bioma
        print("Bioma não encontrado para as coordenadas fornecidas.")
        return None
    except Exception as e:
        print(f"Erro ao identificar bioma: {e}")
        return None


async def verificar_sobreposicao_apiario(longitude: float, latitude: float, raio_km: float, session: AsyncSession) -> bool:
    """
    Verifica se já existe apiário/meliponário na mesma coordenada ou dentro do raio.
    Retorna True se houver sobreposição, False caso contrário.
    """
    from models.apiary import Apiary
    ponto = Point(longitude, latitude)
    result = await session.execute(select(Apiary))
    apiarios = result.scalars().all()
    for apiario in apiarios:
        ponto_apiario = Point(float(apiario.longitude), float(apiario.latitude))
        if ponto.equals(ponto_apiario):
            return True
        if ponto.distance(ponto_apiario) <= raio_km / 111:  # Aproximação: 1 grau ~ 111km
            return True
    return False


async def calcular_capacidade_suporte_com_interseccao(area_ha: float, bioma: str, tipo_cultura: str, longitude: float, latitude: float, raio_km: float, session: AsyncSession) -> int:
    """
    Calcula capacidade de suporte conforme bioma/cultura e subtrai colmeias existentes no raio.
    """
    if tipo_cultura == 'MELIPONICULTOR':
        capacidade = calcular_capacidade_suporte_meliponicultura(area_ha)
    else:
        capacidade = calcular_capacidade_suporte_apicultura(area_ha, bioma, tipo_cultura)
    # Busca apiários/meliponários no raio
    from models.apiary import Apiary
    ponto = Point(longitude, latitude)
    result = await session.execute(select(Apiary))
    apiarios = result.scalars().all()
    colmeias_intersecao = 0
    for apiario in apiarios:
        ponto_apiario = Point(float(apiario.longitude), float(apiario.latitude))
        if ponto.distance(ponto_apiario) <= raio_km / 111:
            colmeias_intersecao += apiario.quantidadeColmeias
    return max(capacidade - colmeias_intersecao, 0)


def process_meliponicultor(latitude: str, longitude: str, especie: str, buffers_existentes: Optional[list] = None, return_area_only: bool = False, raio_km: float = None):
    """
    Processa o cálculo de área de vegetação e capacidade de suporte para meliponário, usando buffer dinâmico conforme espécie e classes específicas.
    Permite sobrescrever o raio do buffer via parâmetro opcional raio_km.
    """
    import logging
    logger = logging.getLogger(__name__)
    crs_metric = "EPSG:31983"
    crs_geo = "EPSG:4326"
    try:
        if raio_km is not None:
            raio_buffer = raio_km
        else:
            raio_buffer = calcular_raio_voo_meliponario(especie)
        centro = Point(float(longitude), float(latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer_novo = gdf_centro.geometry.iloc[0].buffer(raio_buffer * 1000)
        geojson_files = list_geojson_files_from_minio()
        gdf_todas = concat_geojsons([get_geojson_file_cached(f) for f in geojson_files], crs_geo, crs_metric)
        # Filtra vegetações e interseções
        gdf_vegetacao = gdf_todas[gdf_todas['CLASSE'].isin(VEGETACAO_MELIPONARIO)].copy()
        gdf_vegetacao = gdf_vegetacao[gdf_vegetacao.intersects(buffer_novo)].copy()
        gdf_vegetacao['intersecao'] = gdf_vegetacao.geometry.intersection(buffer_novo)
        gdf_vegetacao = gdf_vegetacao[~gdf_vegetacao['intersecao'].is_empty]
        gdf_vegetacao['area_intersecao_ha'] = gdf_vegetacao['intersecao'].area / 10000.0
        areas = gdf_vegetacao.groupby('CLASSE')['area_intersecao_ha'].sum().to_dict()
        soma_areas = sum([areas.get(tipo, 0) for tipo in VEGETACAO_MELIPONARIO])
        logger.info(f"[MELIPONARIO] Soma total das áreas dentro do buffer: {soma_areas:.2f} ha")
        logger.info(f"[MELIPONARIO] Áreas por vegetação no recorte de {raio_buffer}km: ARBOREO={areas.get('ARBOREO', 0):.2f} ha, ARBUSTIVO={areas.get('ARBUSTIVO', 0):.2f} ha")
        area_total = soma_areas
        # Cálculo de capacidade de suporte
        capacidade = calcular_capacidade_suporte_meliponicultura(area_total)
        logger.info(f"[MELIPONARIO] Capacidade de suporte calculada: {capacidade}")
        # Subtrai colmeias existentes no raio (se buffers_existentes fornecido)
        colmeias_intersecao = 0
        if buffers_existentes:
            for buf in buffers_existentes:
                if buf['buffer'].intersects(buffer_novo):
                    colmeias_intersecao += buf['colmeias']
        capacidade_final = capacidade - colmeias_intersecao
        if capacidade_final < 0:
            capacidade_final = 0
        logger.info(f"[MELIPONARIO] Capacidade de suporte final: {capacidade_final}")
        return capacidade_final if not return_area_only else area_total
    except Exception as e:
        logger.error(f"[MELIPONARIO] Erro no processamento: {e}")
        return None
