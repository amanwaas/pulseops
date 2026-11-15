import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.db_models import HealthLog

logger = logging.getLogger("pulseops.retention")


class RetentionService:
    """
    Automated retention cleanup service.
    Prunes health records older than 30 days to strictly bound Neon serverless storage.
    """

    @staticmethod
    async def prune_old_health_logs(session: AsyncSession, retention_days: int = settings.RETENTION_DAYS) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        logger.info(f"Running automated retention pruning for health logs prior to {cutoff.isoformat()}")

        stmt = delete(HealthLog).where(HealthLog.checked_at < cutoff)
        result = await session.execute(stmt)
        await session.commit()

        pruned_count = result.rowcount or 0
        logger.info(f"Retention pruning complete. Pruned {pruned_count} old health log records.")
        return pruned_count


retention_service = RetentionService()
