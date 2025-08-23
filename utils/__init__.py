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
from models.apiary import Apiary

# MinIO configuration
MINIO_URL = os.getenv('MINIO_URL')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME')

MINIO_SECURE = os.getenv('MINIO_SECURE', 'false').strip().lower() in ('true', '1', 'yes')

minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY or '',
    secret_key=MINIO_SECRET_KEY or '',
    secure=MINIO_SECURE
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
GEOJSON_CACHE_DIR = os.path.join(PROJECT_ROOT, 'geojson_files_cache')
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
    if not MINIO_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="MinIO bucket não configurado.")
    try:
        objects = minio_client.list_objects(MINIO_BUCKET_NAME, prefix='', recursive=True)
        return [obj.object_name for obj in objects if obj.object_name.endswith('.geojson')]
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


def get_geojson_file_cached(filename):
    local_path = os.path.join(GEOJSON_CACHE_DIR, os.path.basename(filename))
    if not os.path.exists(local_path):
        response = None
        try:
            response = minio_client.get_object(MINIO_BUCKET_NAME, filename)
            data = response.read()
            with open(local_path, 'wb') as f:
                f.write(data)
        except S3Error as e:
            raise HTTPException(status_code=500, detail=f"MinIO error ao obter {filename}: {str(e)}")
        finally:
            try:
                if response is not None:
                    response.close()
                    if hasattr(response, 'release_conn'):
                        response.release_conn()
            except Exception:
                # Evita propagar erro de limpeza de recurso
                pass
    return local_path


async def verify_user_exists(user_id: int, session: AsyncSession):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Usuário não existe no sistema')


def calcular_area_buffer(longitude: float, latitude: float, raio_km: float = 1.5, geojson_files: list = None):
    """
    Se geojson_files não for fornecido, retorna o polígono do buffer reprojetado de volta para EPSG:4326.
    Caso contrário, retorna a soma das áreas (ha) das classes de vegetação dentro do buffer.
    """
    crs_metric = "EPSG:31983"
    crs_geo = "EPSG:4326"
    centro = Point(float(longitude), float(latitude))
    # Constrói buffer em CRS métrico
    gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
    buffer_m = gdf_centro.geometry.iloc[0].buffer(raio_km * 1000)
    if not geojson_files:
        # Reprojeta o buffer de volta para GEO para compatibilidade com usos existentes
        buffer_geo = gpd.GeoSeries([buffer_m], crs=crs_metric).to_crs(crs_geo).iloc[0]
        return buffer_geo
    # Quando arquivos são fornecidos, calcula a área de interseção (ha)
    soma_areas = 0.0
    for filename in geojson_files:
        with open(filename, 'r') as f:
            geojson_data = json.load(f)
        for layer in geojson_data['features']:
            geom = shape(layer['geometry'])
            if not geom.is_valid:
                geom = geom.buffer(0)
            # Reprojeta geometria para métrico antes de intersectar com buffer_m
            try:
                gdf_geom = gpd.GeoSeries([geom], crs=crs_geo).to_crs(crs_metric).iloc[0]
            except Exception:
                # Se houver falha de CRS no layer específico, ignora este feature
                continue
            if gdf_geom.is_valid and gdf_geom.intersects(buffer_m):
                intersecao = gdf_geom.intersection(buffer_m)
                if not intersecao.is_empty:
                    nome_camada = layer.get('properties', {}).get('CLASSE')
                    if nome_camada in VEGETACAO_APICULTOR:
                        soma_areas += intersecao.area / 10000.0
    return round(float(soma_areas), 2)


def area_vegetacao_dentro_buffer(longitude: float, latitude: float, raio_km: float = 1.5, geojson_files: list = None):
    crs_metric = "EPSG:31983"
    crs_geo = "EPSG:4326"
    if not geojson_files:
        return 0.0
    try:
        centro = Point(float(longitude), float(latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer_m = gdf_centro.geometry.iloc[0].buffer(raio_km * 1000)
        gdf_todas = concat_geojsons([get_geojson_file_cached(f) for f in geojson_files], crs_geo, crs_metric)
        gdf_vegetacao = gdf_todas[gdf_todas['CLASSE'].isin(VEGETACAO_APICULTOR)].copy()
        gdf_vegetacao = gdf_vegetacao[gdf_vegetacao.intersects(buffer_m)].copy()
        if gdf_vegetacao.empty:
            return 0.0
        gdf_vegetacao['intersecao'] = gdf_vegetacao.geometry.intersection(buffer_m)
        gdf_vegetacao = gdf_vegetacao[~gdf_vegetacao['intersecao'].is_empty]
        if gdf_vegetacao.empty:
            return 0.0
        gdf_vegetacao['area_intersecao_ha'] = gdf_vegetacao['intersecao'].area / 10000.0
        return round(float(gdf_vegetacao['area_intersecao_ha'].sum()), 2)
    except Exception:
        return 0.0


def area_vegetacao_dentro_buffer_apiario(longitude: float, latitude: float, raio_km: float = 1.5, geojson_files: list = None):
    crs_metric = "EPSG:31983"
    crs_geo = "EPSG:4326"
    if not geojson_files:
        return 0.0
    try:
        centro = Point(float(longitude), float(latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer_m = gdf_centro.geometry.iloc[0].buffer(raio_km * 1000)
        gdf_todas = concat_geojsons([get_geojson_file_cached(f) for f in geojson_files], crs_geo, crs_metric)
        gdf_vegetacao = gdf_todas[gdf_todas['CLASSE'].isin(VEGETACAO_APICULTOR)].copy()
        gdf_vegetacao = gdf_vegetacao[gdf_vegetacao.intersects(buffer_m)].copy()
        if gdf_vegetacao.empty:
            return 0.0
        gdf_vegetacao['intersecao'] = gdf_vegetacao.geometry.intersection(buffer_m)
        gdf_vegetacao = gdf_vegetacao[~gdf_vegetacao['intersecao'].is_empty]
        if gdf_vegetacao.empty:
            return 0.0
        gdf_vegetacao['area_intersecao_ha'] = gdf_vegetacao['intersecao'].area / 10000.0
        return round(float(gdf_vegetacao['area_intersecao_ha'].sum()), 2)
    except Exception:
        return 0.0


def area_vegetacao_dentro_buffer_meliponario(longitude: float, latitude: float, raio_km: float = 1.2, geojson_files: list = None):
    """
    Calcula a área de vegetação adequada para meliponário dentro do buffer circular (raio em km) ao redor do ponto.
    Considera apenas as classes de vegetação específicas para meliponário.
    """
    import logging
    logger = logging.getLogger(__name__)
    crs_metric = "EPSG:31983"
    crs_geo = "EPSG:4326"
    if not geojson_files:
        logger.warning("Nenhum arquivo geojson fornecido para cálculo de área de vegetação.")
        return 0.0
    try:
        logger.info(f"Iniciando cálculo de área de vegetação para meliponário em ({latitude}, {longitude}) com raio {raio_km} km.")
        centro = Point(float(longitude), float(latitude))
        gdf_centro = gpd.GeoDataFrame(geometry=[centro], crs=crs_geo).to_crs(crs_metric)
        buffer_m = gdf_centro.geometry.iloc[0].buffer(raio_km * 1000)
        gdf_todas = concat_geojsons([get_geojson_file_cached(f) for f in geojson_files], crs_geo, crs_metric)
        gdf_vegetacao = gdf_todas[gdf_todas['CLASSE'].isin(VEGETACAO_MELIPONARIO)].copy()
        gdf_vegetacao = gdf_vegetacao[gdf_vegetacao.intersects(buffer_m)].copy()
        if gdf_vegetacao.empty:
            logger.info("Nenhuma classe de vegetação adequada encontrada dentro do buffer.")
            return 0.0
        gdf_vegetacao['intersecao'] = gdf_vegetacao.geometry.intersection(buffer_m)
        gdf_vegetacao = gdf_vegetacao[~gdf_vegetacao['intersecao'].is_empty]
        if gdf_vegetacao.empty:
            logger.info("Nenhuma interseção de vegetação adequada encontrada após recorte do buffer.")
            return 0.0
        gdf_vegetacao['area_intersecao_ha'] = gdf_vegetacao['intersecao'].area / 10000.0
        soma_areas = float(gdf_vegetacao['area_intersecao_ha'].sum())
        for _, row in gdf_vegetacao.iterrows():
            logger.debug(f"Classe: {row.get('CLASSE')}, Área adicionada: {row['area_intersecao_ha']:.4f} ha")
        logger.info(f"Área total de vegetação adequada encontrada: {soma_areas:.2f} ha")
        return round(soma_areas, 2)
    except Exception as e:
        logger.error(f"Erro ao processar arquivos GeoJSON: {e}")
        return 0.0


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

        # Colmeias existentes no raio: usar buffers_existentes, se fornecido; caso contrário, fallback mock
        colmeias_intersecao = 0
        if buffers_existentes:
            for buf in buffers_existentes:
                if buf['buffer'].intersects(buffer_novo):
                    try:
                        colmeias_intersecao += int(buf['colmeias'])
                    except Exception:
                        continue
        else:
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
    Verifica se já existe apiário/meliponário na mesma coordenada ou dentro do raio (em km).
    Retorna True se houver sobreposição, False caso contrário.
    """
    import math
    try:
        def haversine_km(lat1, lon1, lat2, lon2):
            R = 6371.0088  # Raio médio da Terra em km
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        result = await session.execute(select(Apiary))
        apiarios = result.scalars().all()
        for apiario in apiarios:
            lon_api, lat_api = float(apiario.longitude), float(apiario.latitude)
            # Mesma coordenada exata
            if float(longitude) == lon_api and float(latitude) == lat_api:
                return True
            # Distância geodésica
            if haversine_km(float(latitude), float(longitude), lat_api, lon_api) <= float(raio_km):
                return True
        return False
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao verificar sobreposição de apiário: {e}")
        return False


async def calcular_capacidade_suporte_com_interseccao(area_ha: float, bioma: str, tipo_cultura: str, longitude: float, latitude: float, raio_km: float, session: AsyncSession) -> int:
    """
    Calcula capacidade de suporte conforme bioma/cultura e subtrai colmeias existentes no raio.
    """
    import math
    if tipo_cultura == 'MELIPONICULTOR':
        capacidade = calcular_capacidade_suporte_meliponicultura(area_ha)
    else:
        capacidade = calcular_capacidade_suporte_apicultura(area_ha, bioma, tipo_cultura)

    def haversine_km(lat1, lon1, lat2, lon2):
        R = 6371.0088
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # Busca apiários/meliponários no raio
    result = await session.execute(select(Apiary))
    apiarios = result.scalars().all()
    colmeias_intersecao = 0
    for apiario in apiarios:
        lon_api, lat_api = float(apiario.longitude), float(apiario.latitude)
        if haversine_km(float(latitude), float(longitude), lat_api, lon_api) <= float(raio_km):
            colmeias_intersecao += apiario.quantidadeColmeias
    return max(capacidade - colmeias_intersecao, 0)


def process_meliponicultor(latitude: str, longitude: str, especie: str, buffers_existentes: Optional[list] = None, return_area_only: bool = False, raio_km: float = None):
    """
    Processa o cálculo de área de vegetação e capacidade de suporte para meliponário, usando buffer dinâmico conforme espécie e classes específicas.
    Retorna um dicionário detalhado com áreas, capacidade calculada e capacidade final.
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
        return {
            "capacidade_final": capacidade_final,
            "capacidade_calculada": capacidade,
            "area_total": soma_areas,
            "areas_por_vegetacao": areas,
            "raio_buffer": raio_buffer,
            "colmeias_existentes": colmeias_intersecao
        }
    except Exception as e:
        logger.error(f"[MELIPONARIO] Erro no processamento: {e}")
        return None
