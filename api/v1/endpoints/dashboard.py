from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.deps import get_session
from models.apiary import Apiary
from models.meliponary import Meliponary
from schemas.apiary_schema import ApiarySchema
from schemas.meliponary_schema import MeliponarySchema

router = APIRouter()

@router.get("/dashboard", status_code=200)
async def dashboard(session: AsyncSession = Depends(get_session)):
    apiaries_result = await session.execute(select(Apiary))
    meliponaries_result = await session.execute(select(Meliponary))
    apiaries = apiaries_result.scalars().all()
    meliponaries = meliponaries_result.scalars().all()
    return {
        "apiarios": [ApiarySchema.model_validate(a).model_dump() for a in apiaries],
        "meliponarios": [MeliponarySchema.model_validate(m).model_dump() for m in meliponaries]
    }
