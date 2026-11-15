import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Set
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.db_models import HealthTarget
from app.services.health_checker import health_checker
from app.services.retention_service import retention_service

logger = logging.getLogger("pulseops.worker")


class HealthWorker:
    """
    Continuous, non-blocking asynchronous health check worker.
    Maintains an explicit in-flight state machine to prevent concurrent overlapping
    probes on the same target, eliminating race conditions and state flapping.
    """

    def __init__(self, concurrency_limit: int = 25):
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(concurrency_limit)
        self._last_prune_time: Optional[datetime] = None
        # Explicit In-Flight State Tracking (Target ID -> Probing)
        self._in_flight_targets: Set[str] = set()

    async def start(self):
        if self._is_running:
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("PulseOps background Health & Retention worker started.")

    async def stop(self):
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await health_checker.close()
        logger.info("PulseOps background Health worker stopped.")

    async def _run_loop(self):
        while self._is_running:
            try:
                now = datetime.now(timezone.utc)
                await self._check_due_targets(now)
                await self._check_retention_prune(now)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check worker loop: {e}", exc_info=True)

            # Polling cadence: tick every 5 seconds to schedule targets on time
            await asyncio.sleep(5)

    async def _check_due_targets(self, now: datetime):
        async with AsyncSessionLocal() as session:
            stmt = select(HealthTarget).where(HealthTarget.is_active == True)
            res = await session.execute(stmt)
            targets = res.scalars().all()

            due_targets = []
            for t in targets:
                # Explicit Guard: If a probe is currently in-flight for this target, skip
                if t.id in self._in_flight_targets:
                    continue

                if t.last_checked_at is None:
                    due_targets.append(t.id)
                else:
                    elapsed = (now - t.last_checked_at).total_seconds()
                    if elapsed >= t.check_interval_seconds:
                        due_targets.append(t.id)

            if not due_targets:
                return

            logger.debug(f"Dispatching health probes for {len(due_targets)} due targets.")

            async def _probe(target_id: str):
                self._in_flight_targets.add(target_id)
                try:
                    async with self._semaphore:
                        async with AsyncSessionLocal() as probe_session:
                            try:
                                await health_checker.check_target(target_id, probe_session)
                                await probe_session.commit()
                            except Exception as exc:
                                logger.error(f"Probe failure for target {target_id}: {exc}")
                                await probe_session.rollback()
                finally:
                    self._in_flight_targets.discard(target_id)

            tasks = [_probe(tid) for tid in due_targets]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_retention_prune(self, now: datetime):
        """Runs daily database retention prune once every 24 hours."""
        if self._last_prune_time is None or (now - self._last_prune_time) > timedelta(hours=24):
            async with AsyncSessionLocal() as session:
                try:
                    await retention_service.prune_old_health_logs(session)
                    self._last_prune_time = now
                except Exception as e:
                    logger.error(f"Failed to execute daily retention pruning: {e}")


health_worker = HealthWorker()
