from models.log import Log
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

async def log_action(session: AsyncSession, user_id: int, action: str, entity: str, entity_id: int = None, details: str = None):
    log = Log(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
        timestamp=datetime.utcnow()
    )
    session.add(log)
    # Não faz commit aqui, pois será feito na transaction do endpoint

