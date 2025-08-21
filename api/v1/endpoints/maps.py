from typing import List
from fastapi import APIRouter, Depends, status, HTTPException, Response, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from minio import Minio
from minio.error import S3Error
import os
import json

from core.deps import get_session
from models import Maps

maps_router = APIRouter()

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

# Ensure the bucket exists
if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
    minio_client.make_bucket(MINIO_BUCKET_NAME)


@maps_router.post("/upload/")
async def upload_geojson(files: List[UploadFile] = File(...), session: AsyncSession = Depends(get_session)):
    file_urls = []
    for file in files:
        file_path = f"{file.filename.lower()}"
        try:
            minio_client.put_object(
                MINIO_BUCKET_NAME,
                file_path,
                file.file,
                length=-1,
                part_size=10*1024*1024,
                content_type=file.content_type
            )
            file_url = f"https://{MINIO_URL}/{MINIO_BUCKET_NAME}/{file_path}"
            file_urls.append(file_url)

            # Save file data to the database
            new_map = Maps(file_path=file_url, name=file.filename)
            session.add(new_map)
        except S3Error as e:
            raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")

    await session.commit()
    return JSONResponse(content={"file_urls": file_urls})

@maps_router.get("/")
async def list_geojson(session: AsyncSession = Depends(get_session)):
    async with session.begin():
        result = await session.execute(select(Maps))
        maps = result.scalars().all()

    file_urls = [{"id": map.id, "name": map.name, "url": map.file_path} for map in maps]
    return JSONResponse(content=file_urls)

@maps_router.get("/content/{filename}")
async def geojson_content(filename: str):
    try:
        response = minio_client.get_object(MINIO_BUCKET_NAME, filename)
        content = json.load(response)
        return JSONResponse(content=content)
    except S3Error as e:
        return JSONResponse(content={"error": f"MinIO error: {str(e)}"}, status_code=404)

@maps_router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geojson(map_id: int, session: AsyncSession = Depends(get_session)):
    async with session.begin():
        result = await session.execute(select(Maps).filter(Maps.id == map_id))
        map_entry = result.scalar()

        if not map_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map not found")

        # Delete the file from MinIO
        file_path = map_entry.file_path.split(f"https://{MINIO_URL}/{MINIO_BUCKET_NAME}/")[1]
        try:
            minio_client.remove_object(MINIO_BUCKET_NAME, file_path)
        except S3Error as e:
            raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")

        # Delete the map entry from the database
        await session.delete(map_entry)
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)