import json
import os
import traceback
from typing import Optional, List

from fastapi import status, HTTPException
from minio import Minio
from minio.error import S3Error
from shapely.geometry import Point, shape
from shapely.validation import explain_validity
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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


def calcular_raio_voo(tipo, especie=None):
    if tipo == 'MELIPONICULTOR':
        if especie in ['Frieseomelitta silvestrii', 'Frieseomelitta longipes', 'Frieseomelitta doederleini',
                       'Tetragonisca angustula']:
            return 0.5
        elif especie in ['Scaptotrigona polysticta', 'Melipona subnitida', 'Melipona seminigra',
                         'Melipona flavolineata', 'Melipona fasciculata']:
            return 2.5
        else:
            return 1.2
    else:
        return 1.5


def calcular_capacidade_suporte_apicultura(area_total):
    capacidade_suporte = area_total / 7.07
    return round(capacidade_suporte)


def calcular_capacidade_suporte_meliponicultura(hectares):
    arvores_por_hectare = 570
    quantidade_arvores = hectares * arvores_por_hectare
    arvores_pasto = quantidade_arvores * 0.45
    colmeias_por_hectare = arvores_pasto / 100
    return round(colmeias_por_hectare)


def list_geojson_files_from_minio() -> List[str]:
    try:
        objects = minio_client.list_objects(MINIO_BUCKET_NAME, prefix='', recursive=True)
        geojson_files = [obj.object_name for obj in objects if obj.object_name.endswith('.geojson')]
        return geojson_files
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")


async def process_geojson(latitude: str, longitude: str, tipo: str, especie: Optional[str] = None):
    try:
        centro = Point(float(longitude), float(latitude))
        raio_voo_dec = calcular_raio_voo(tipo, especie)
        buffer = centro.buffer(raio_voo_dec * 1000)  # Convert to meters

        areas = {}
        geojson_files = list_geojson_files_from_minio()

        for filename in geojson_files:
            response = minio_client.get_object(MINIO_BUCKET_NAME, filename)
            geojson_data = json.load(response)
            layers = geojson_data['features']

            for layer in layers:
                geom = shape(layer['geometry'])
                if not geom.is_valid:
                    print(f"Invalid geometry in {filename}: {explain_validity(geom)}")
                    continue

                if geom.intersects(buffer):
                    # print(f"Intersects {layer}")
                    nome_camada = layer['properties']['CLASSE']
                    area = float(layer['properties']['AREA_HA'])
                    if nome_camada not in areas:
                        areas[nome_camada] = 0
                    areas[nome_camada] += area

        area_total = (areas.get('URBANO', 0) + areas.get('ARBUSTIVO', 0) + areas.get('HERBACEO', 0))
        suporte_apicultura = calcular_capacidade_suporte_apicultura(area_total)
        pasto = calcular_capacidade_suporte_meliponicultura(areas.get('ARBOREO', 0))

        if tipo == 'APICULTOR':
            return str(suporte_apicultura)
        elif tipo == 'MELIPONICULTOR':
            return str(pasto)
    except Exception as e:
        print('Erro:', str(e))
        traceback.print_exc()


async def verify_user_exists(user_id: int, session: AsyncSession):
    result = await session.execute(select(User).filter(User.id == user_id))
    user = result.scalar()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Usuário não existe no sistema')


def read_files_from_directory(directory):
    files_data = {}
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            with open(file_path, 'r') as file:
                files_data[filename] = file.read()
    return files_data
