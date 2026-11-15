import asyncio
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import encryption_service
from app.core.ws_manager import ws_manager
from app.core.state_machines import TargetHealthStatus, HealthStateMachine, IncidentStatus
from app.models.db_models import HealthTarget, HealthLog, Incident, AlertConfig, Project
from app.services.alert_dispatcher import alert_dispatcher

logger = logging.getLogger("pulseops.health_checker")


class HealthCheckerService:
    """
    Robust, non-blocking Health Checking Engine with deterministic state-machine semantics.
    Enforces consecutive failure thresholds to eliminate false positives and handles
    recovery transitions cleanly.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": "PulseOps-HealthCheck/1.0 (+https://pulseops.io)"},
                follow_redirects=True,
                verify=False,  # Allow self-signed in internal testing environments
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def check_target(self, target_id: str, session: AsyncSession) -> Optional[HealthLog]:
        """
        Executes a single health check probe, applies formal state machine transition,
        handles incident lifecycle, dispatches alerts, and writes to log.
        """
        stmt = select(HealthTarget).where(HealthTarget.id == target_id)
        res = await session.execute(stmt)
        target = res.scalar_one_or_none()
        if not target or not target.is_active:
            return None

        client = await self.get_client()
        timeout = float(target.timeout_seconds or settings.HEALTH_CHECK_DEFAULT_TIMEOUT_SECONDS)
        url = target.endpoint_url

        t_start = time.perf_counter()
        status_code = None
        error_message = None
        is_up = False

        try:
            resp = await client.get(url, timeout=timeout)
            t_end = time.perf_counter()
            latency_ms = round((t_end - t_start) * 1000.0, 2)
            status_code = resp.status_code
            is_up = 200 <= status_code < 400
            if not is_up:
                error_message = f"HTTP status {status_code} returned"
        except httpx.TimeoutException:
            t_end = time.perf_counter()
            latency_ms = round((t_end - t_start) * 1000.0, 2)
            error_message = f"Connection timed out after {timeout}s"
        except httpx.RequestError as exc:
            t_end = time.perf_counter()
            latency_ms = round((t_end - t_start) * 1000.0, 2)
            error_message = f"Network request error: {str(exc)}"
        except Exception as exc:
            t_end = time.perf_counter()
            latency_ms = round((t_end - t_start) * 1000.0, 2)
            error_message = f"Unexpected probe error: {str(exc)}"

        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # Invariant & State Machine Transition
        # -------------------------------------------------------------
        # Check if an open incident currently exists for this target
        stmt_inc = (
            select(Incident)
            .where(
                Incident.target_id == target.id,
                Incident.status == IncidentStatus.OPEN.value,
            )
            .order_by(Incident.started_at.desc())
        )
        res_inc = await session.execute(stmt_inc)
        open_incident = res_inc.scalars().first()
        has_open_incident = open_incident is not None

        current_status = TargetHealthStatus.from_string(target.last_status)

        new_status, new_failures, should_open_incident, should_resolve_incident = (
            HealthStateMachine.evaluate_probe(
                current_status=current_status,
                current_consecutive_failures=target.consecutive_failures,
                is_probe_successful=is_up,
                has_open_incident=has_open_incident,
                threshold=settings.CONSECUTIVE_FAILURES_THRESHOLD,
            )
        )

        target.last_status = new_status.value
        target.consecutive_failures = new_failures
        target.last_checked_at = now

        if should_open_incident:
            logger.warning(
                f"Target {target.endpoint_url} failed {new_failures} consecutive checks. "
                f"Transitioning to DOWN & opening incident: {error_message}"
            )
            await self._handle_failure(target, session, error_message, latency_ms, status_code)
        elif should_resolve_incident:
            logger.info(f"Target {target.endpoint_url} recovered to UP. Resolving open incident.")
            await self._handle_recovery(target, session, latency_ms)

        # Create health log entry
        log_entry = HealthLog(
            target_id=target.id,
            status_code=status_code,
            latency_ms=latency_ms,
            is_up=is_up,
            error_message=error_message,
            checked_at=now,
        )
        session.add(log_entry)
        await session.flush()

        # Broadcast real-time ping to WebSocket / SSE subscribers
        await ws_manager.broadcast("health_ping", {
            "target_id": target.id,
            "project_id": target.project_id,
            "environment": target.environment,
            "endpoint_url": target.endpoint_url,
            "status": target.last_status,
            "is_up": is_up,
            "latency_ms": latency_ms,
            "status_code": status_code,
            "error_message": error_message,
            "consecutive_failures": target.consecutive_failures,
            "checked_at": now.isoformat(),
        })

        return log_entry

    async def _handle_failure(
        self,
        target: HealthTarget,
        session: AsyncSession,
        error_message: Optional[str],
        latency_ms: float,
        status_code: Optional[int],
    ):
        """Creates an incident and triggers alerts across configured channels."""
        now = datetime.now(timezone.utc)
        incident = Incident(
            target_id=target.id,
            started_at=now,
            status=IncidentStatus.OPEN.value,
            failure_reason=error_message or "Health check failed",
            consecutive_failures=target.consecutive_failures,
        )
        session.add(incident)
        await session.flush()

        proj_stmt = select(Project).where(Project.id == target.project_id)
        proj_res = await session.execute(proj_stmt)
        project = proj_res.scalar_one_or_none()

        alert_stmt = select(AlertConfig).where(
            AlertConfig.project_id == target.project_id,
            AlertConfig.notify_on_health_fail == True,
        )
        alerts_res = await session.execute(alert_stmt)
        configs = alerts_res.scalars().all()

        metadata = {
            "project": project.name if project else target.project_id,
            "environment": target.environment,
            "endpoint": target.endpoint_url,
            "status_code": status_code or "N/A",
            "latency": f"{latency_ms} ms",
            "consecutive_failures": target.consecutive_failures,
            "error": error_message,
        }

        for cfg in configs:
            try:
                dest = encryption_service.decrypt(cfg.destination_url_encrypted)
                asyncio.create_task(
                    alert_dispatcher.dispatch_alert(
                        channel_type=cfg.channel_type,
                        destination_url_or_email=dest,
                        title=f"Health Check Failure: {metadata['project']} [{target.environment.upper()}]",
                        message=f"Endpoint {target.endpoint_url} is DOWN after {target.consecutive_failures} failed checks: {error_message}",
                        severity="CRITICAL",
                        metadata=metadata,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to decrypt or dispatch alert for config {cfg.id}: {e}")

        await ws_manager.broadcast("incident_opened", {
            "incident_id": incident.id,
            "target_id": target.id,
            "project_id": target.project_id,
            "environment": target.environment,
            "endpoint_url": target.endpoint_url,
            "reason": incident.failure_reason,
            "started_at": now.isoformat(),
        })

    async def _handle_recovery(self, target: HealthTarget, session: AsyncSession, latency_ms: float):
        """Resolves open incident and dispatches RESOLVED notification."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(Incident)
            .where(Incident.target_id == target.id, Incident.status == IncidentStatus.OPEN.value)
            .order_by(Incident.started_at.desc())
        )
        res = await session.execute(stmt)
        open_incidents = res.scalars().all()

        for inc in open_incidents:
            inc.status = IncidentStatus.RESOLVED.value
            inc.resolved_at = now

        proj_stmt = select(Project).where(Project.id == target.project_id)
        proj_res = await session.execute(proj_stmt)
        project = proj_res.scalar_one_or_none()

        alert_stmt = select(AlertConfig).where(
            AlertConfig.project_id == target.project_id,
            AlertConfig.notify_on_health_fail == True,
        )
        alerts_res = await session.execute(alert_stmt)
        configs = alerts_res.scalars().all()

        metadata = {
            "project": project.name if project else target.project_id,
            "environment": target.environment,
            "endpoint": target.endpoint_url,
            "status": "HEALTHY (UP)",
            "latency": f"{latency_ms} ms",
            "resolved_at": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

        for cfg in configs:
            try:
                dest = encryption_service.decrypt(cfg.destination_url_encrypted)
                asyncio.create_task(
                    alert_dispatcher.dispatch_alert(
                        channel_type=cfg.channel_type,
                        destination_url_or_email=dest,
                        title=f"Service Recovered: {metadata['project']} [{target.environment.upper()}]",
                        message=f"Endpoint {target.endpoint_url} has recovered and is now responding normally.",
                        severity="RESOLVED",
                        metadata=metadata,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to dispatch recovery alert for config {cfg.id}: {e}")

        await ws_manager.broadcast("incident_resolved", {
            "target_id": target.id,
            "project_id": target.project_id,
            "environment": target.environment,
            "endpoint_url": target.endpoint_url,
            "resolved_at": now.isoformat(),
        })


health_checker = HealthCheckerService()
