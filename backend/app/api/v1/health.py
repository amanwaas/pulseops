from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_admin, require_developer, require_viewer
from app.models.db_models import HealthTarget, HealthLog, Deployment, Project
from app.models.schemas import (
    HealthTargetCreate,
    HealthTargetUpdate,
    HealthTargetResponse,
    HealthLogResponse,
    LatencyAndTimelineResponse,
    LatencyTimeSeriesPoint,
    DeploymentAnnotation,
)
from app.services.health_checker import health_checker

router = APIRouter(prefix="/health", tags=["Health Targets"])


@router.get("/targets", response_model=List[HealthTargetResponse])
async def list_health_targets(
    project_id: Optional[str] = None,
    environment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """Lists health check targets, optionally filtered by project or environment."""
    stmt = select(HealthTarget).order_by(HealthTarget.environment.asc())
    if project_id:
        stmt = stmt.where(HealthTarget.project_id == project_id)
    if environment:
        stmt = stmt.where(HealthTarget.environment == environment)

    res = await db.execute(stmt)
    targets = res.scalars().all()
    return targets


@router.post("/targets", response_model=HealthTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_health_target(
    project_id: str,
    target_in: HealthTargetCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Registers a new health monitoring target endpoint."""
    proj_stmt = select(Project).where(Project.id == project_id)
    proj_res = await db.execute(proj_stmt)
    if not proj_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    target = HealthTarget(
        project_id=project_id,
        environment=target_in.environment,
        endpoint_url=target_in.endpoint_url,
        check_interval_seconds=target_in.check_interval_seconds,
        timeout_seconds=target_in.timeout_seconds,
        is_active=target_in.is_active,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target


@router.put("/targets/{target_id}", response_model=HealthTargetResponse)
async def update_health_target(
    target_id: str,
    target_in: HealthTargetUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Updates target configuration (URL, interval, timeout, active status)."""
    stmt = select(HealthTarget).where(HealthTarget.id == target_id)
    res = await db.execute(stmt)
    target = res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Health target not found")

    if target_in.endpoint_url is not None:
        target.endpoint_url = target_in.endpoint_url
    if target_in.check_interval_seconds is not None:
        target.check_interval_seconds = target_in.check_interval_seconds
    if target_in.timeout_seconds is not None:
        target.timeout_seconds = target_in.timeout_seconds
    if target_in.is_active is not None:
        target.is_active = target_in.is_active

    await db.commit()
    await db.refresh(target)
    return target


@router.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_health_target(
    target_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Deletes a health monitoring target."""
    stmt = select(HealthTarget).where(HealthTarget.id == target_id)
    res = await db.execute(stmt)
    target = res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Health target not found")

    await db.delete(target)
    await db.commit()
    return None


@router.post("/targets/{target_id}/probe", response_model=HealthLogResponse)
async def trigger_manual_probe(
    target_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_developer),
):
    """Triggers an immediate on-demand health probe for this target."""
    log_entry = await health_checker.check_target(target_id, db)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Target not found or inactive")
    await db.commit()
    return log_entry


@router.get("/targets/{target_id}/timeline", response_model=LatencyAndTimelineResponse)
async def get_target_timeline(
    target_id: str,
    range_window: str = Query("24h", pattern="^(1h|24h|7d)$"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """
    Returns time-series latency data points combined with deployment annotations
    for the exact same project & environment within the chosen time window (1h, 24h, 7d).
    Enables instant visual correlation between deployments and latency spikes/downtime.
    """
    stmt = select(HealthTarget).where(HealthTarget.id == target_id)
    res = await db.execute(stmt)
    target = res.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Health target not found")

    now = datetime.now(timezone.utc)
    delta_map = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
    }
    cutoff = now - delta_map.get(range_window, timedelta(hours=24))

    # 1. Fetch health logs
    log_stmt = (
        select(HealthLog)
        .where(
            and_(
                HealthLog.target_id == target_id,
                HealthLog.checked_at >= cutoff,
            )
        )
        .order_by(HealthLog.checked_at.asc())
    )
    log_res = await db.execute(log_stmt)
    logs = log_res.scalars().all()

    # 2. Fetch deployments in this project & environment during the same timeframe
    dep_stmt = (
        select(Deployment)
        .where(
            and_(
                Deployment.project_id == target.project_id,
                Deployment.environment == target.environment,
                Deployment.created_at >= cutoff,
            )
        )
        .order_by(Deployment.created_at.asc())
    )
    dep_res = await db.execute(dep_stmt)
    deployments = dep_res.scalars().all()

    points = []
    latencies = []
    up_count = 0

    for l in logs:
        points.append(
            LatencyTimeSeriesPoint(
                timestamp=l.checked_at.isoformat(),
                latency_ms=l.latency_ms,
                is_up=l.is_up,
                status_code=l.status_code,
            )
        )
        latencies.append(l.latency_ms)
        if l.is_up:
            up_count += 1

    total_logs = len(logs)
    if total_logs > 0:
        uptime_pct = round((up_count / total_logs) * 100.0, 2)
        avg_lat = round(sum(latencies) / total_logs, 1)
        sorted_lats = sorted(latencies)
        idx_p95 = int(0.95 * total_logs)
        p95_lat = round(sorted_lats[min(idx_p95, total_logs - 1)], 1)
    else:
        uptime_pct = 100.0
        avg_lat = 0.0
        p95_lat = 0.0

    annotations = [
        DeploymentAnnotation(
            timestamp=d.created_at.isoformat(),
            environment=d.environment,
            commit_sha=d.commit_sha,
            short_sha=d.commit_sha[:7],
            author=d.author,
            status=d.status,
            duration_seconds=d.duration_seconds,
        )
        for d in deployments
    ]

    return LatencyAndTimelineResponse(
        target_id=target.id,
        environment=target.environment,
        p95_latency_ms=p95_lat,
        avg_latency_ms=avg_lat,
        uptime_percentage=uptime_pct,
        points=points,
        deployments=annotations,
    )
