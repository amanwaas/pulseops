from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import require_developer, require_viewer
from app.core.ws_manager import ws_manager
from app.core.state_machines import IncidentStatus, IncidentStateMachine
from app.models.db_models import Incident, HealthTarget, Project
from app.models.schemas import IncidentResponse

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=List[IncidentResponse])
async def list_incidents(
    project_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """Lists incidents with target and project context."""
    stmt = (
        select(Incident)
        .join(HealthTarget, Incident.target_id == HealthTarget.id)
        .join(Project, HealthTarget.project_id == Project.id)
        .options(
            selectinload(Incident.target).selectinload(HealthTarget.project)
        )
        .order_by(Incident.started_at.desc())
    )

    if project_id:
        stmt = stmt.where(HealthTarget.project_id == project_id)
    if status_filter:
        stmt = stmt.where(Incident.status == status_filter)

    res = await db.execute(stmt)
    incidents = res.scalars().all()

    results = []
    for inc in incidents:
        proj_name = inc.target.project.name if inc.target and inc.target.project else "Unknown"
        env = inc.target.environment if inc.target else "unknown"
        endpoint = inc.target.endpoint_url if inc.target else ""

        results.append(
            IncidentResponse(
                id=inc.id,
                target_id=inc.target_id,
                project_name=proj_name,
                environment=env,
                endpoint_url=endpoint,
                started_at=inc.started_at,
                resolved_at=inc.resolved_at,
                status=inc.status,
                failure_reason=inc.failure_reason,
                consecutive_failures=inc.consecutive_failures,
            )
        )
    return results


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_developer),
):
    """Manually marks an incident as resolved."""
    stmt = (
        select(Incident)
        .options(selectinload(Incident.target).selectinload(HealthTarget.project))
        .where(Incident.id == incident_id)
    )
    res = await db.execute(stmt)
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    current_status = IncidentStatus(incident.status)
    if not IncidentStateMachine.can_resolve(current_status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incident is already resolved and cannot transition state.",
        )

    new_status, did_transition = IncidentStateMachine.resolve(current_status)
    incident.status = new_status.value
    incident.resolved_at = datetime.now(timezone.utc)

    # Also reset target's consecutive failures if associated
    if incident.target:
        incident.target.consecutive_failures = 0
        incident.target.last_status = "UP"

    await db.commit()
    await db.refresh(incident)

    await ws_manager.broadcast("incident_resolved", {
        "incident_id": incident.id,
        "target_id": incident.target_id,
        "resolved_at": incident.resolved_at.isoformat(),
        "resolved_by": user["email"],
    })

    proj_name = incident.target.project.name if incident.target and incident.target.project else "Unknown"
    env = incident.target.environment if incident.target else "unknown"
    endpoint = incident.target.endpoint_url if incident.target else ""

    return IncidentResponse(
        id=incident.id,
        target_id=incident.target_id,
        project_name=proj_name,
        environment=env,
        endpoint_url=endpoint,
        started_at=incident.started_at,
        resolved_at=incident.resolved_at,
        status=incident.status,
        failure_reason=incident.failure_reason,
        consecutive_failures=incident.consecutive_failures,
    )
