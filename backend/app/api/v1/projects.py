import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import require_admin, require_developer, require_viewer
from app.core.encryption import encryption_service
from app.core.state_machines import TargetHealthStatus, ProjectHealthReducer
from app.models.db_models import Project, Deployment, HealthTarget, HealthLog, Incident, AlertConfig
from app.models.schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectSummaryCard,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """Lists all configured projects."""
    stmt = select(Project).order_by(Project.name.asc())
    res = await db.execute(stmt)
    projects = res.scalars().all()

    base_url = str(request.base_url).rstrip("/")
    results = []
    for p in projects:
        # Determine webhook endpoint based on provider
        webhook_url = f"{base_url}/api/v1/webhooks/{p.provider}/{p.id}"
        results.append(
            ProjectResponse(
                id=p.id,
                name=p.name,
                slug=p.slug,
                repo_url=p.repo_url,
                provider=p.provider,
                webhook_url=webhook_url,
                masked_secret="••••••••••••••••",
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
        )
    return results


@router.get("/overview-cards", response_model=List[ProjectSummaryCard])
async def get_overview_cards(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """
    Single Pane of Glass: Aggregates real-time metrics across all 5-20 projects.
    Returns latest deployment, health status (UP/DOWN/DEGRADED), active incidents, and p95 latency.
    """
    stmt = (
        select(Project)
        .options(
            selectinload(Project.health_targets),
            selectinload(Project.deployments),
        )
        .order_by(Project.name.asc())
    )
    res = await db.execute(stmt)
    projects = res.scalars().all()

    cards = []
    for p in projects:
        # 1. Available environments
        envs = list(set([t.environment for t in p.health_targets]))
        if not envs:
            envs = ["production"]

        # 2. Overall health status via Monotonic Severity Lattice
        active_target_statuses = [
            TargetHealthStatus.from_string(t.last_status)
            for t in p.health_targets
            if t.is_active
        ]
        overall_health = ProjectHealthReducer.reduce_health(active_target_statuses).value

        # 3. Latest deployment
        latest_dep = None
        if p.deployments:
            sorted_deps = sorted(p.deployments, key=lambda d: d.created_at, reverse=True)
            d = sorted_deps[0]
            latest_dep = {
                "id": d.id,
                "environment": d.environment,
                "commit_sha": d.commit_sha[:7],
                "commit_message": d.commit_message,
                "status": d.status,
                "duration_seconds": d.duration_seconds,
                "created_at": d.created_at.isoformat(),
            }

        # 4. Latency p95 calculation from recent health logs across project targets
        target_ids = [t.id for t in p.health_targets]
        p95_latency = None
        if target_ids:
            log_stmt = (
                select(HealthLog.latency_ms)
                .where(HealthLog.target_id.in_(target_ids))
                .order_by(HealthLog.checked_at.desc())
                .limit(100)
            )
            log_res = await db.execute(log_stmt)
            latencies = log_res.scalars().all()
            if latencies:
                sorted_lats = sorted(latencies)
                idx = int(0.95 * len(sorted_lats))
                p95_latency = round(sorted_lats[min(idx, len(sorted_lats) - 1)], 1)

        # 5. Active incidents count
        inc_count = 0
        if target_ids:
            inc_stmt = (
                select(func.count(Incident.id))
                .where(Incident.target_id.in_(target_ids), Incident.status == "open")
            )
            inc_res = await db.execute(inc_stmt)
            inc_count = inc_res.scalar() or 0

        cards.append(
            ProjectSummaryCard(
                id=p.id,
                name=p.name,
                slug=p.slug,
                repo_url=p.repo_url,
                provider=p.provider,
                environments=envs,
                latest_deployment=latest_dep,
                overall_health=overall_health,
                p95_latency_ms=p95_latency,
                active_incidents_count=inc_count,
                updated_at=p.updated_at,
            )
        )
    return cards


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Creates a new project and generates its encrypted HMAC signing secret."""
    import re
    # Resolve slug if omitted or empty
    slug = project_in.slug
    if not slug:
        slug = re.sub(r"[^a-zA-Z0-9-]", "-", project_in.name.lower().strip())
        slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = f"project-{secrets.token_hex(4)}"

    # If slug already exists, auto-append a short unique suffix instead of failing
    slug_check = await db.execute(select(Project).where(Project.slug == slug))
    if slug_check.scalar_one_or_none():
        slug = f"{slug}-{secrets.token_hex(3)}"

    secret = project_in.webhook_secret or secrets.token_hex(24)
    encrypted_secret = encryption_service.encrypt(secret)

    project = Project(
        name=project_in.name,
        slug=slug,
        repo_url=project_in.repo_url,
        provider=project_in.provider,
        webhook_secret_encrypted=encrypted_secret,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhooks/{project.provider}/{project.id}"

    # Return plaintext secret ONLY upon creation for user to copy into GitHub/GitLab
    resp = ProjectResponse.model_validate(project)
    resp.webhook_url = webhook_url
    resp.masked_secret = secret  # One-time reveal
    return resp


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """Retrieves a single project's configuration."""
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/v1/webhooks/{project.provider}/{project.id}"

    resp = ProjectResponse.model_validate(project)
    resp.webhook_url = webhook_url
    resp.masked_secret = "••••••••••••••••"
    return resp


@router.post("/{project_id}/regenerate-secret")
async def regenerate_webhook_secret(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Regenerates HMAC secret for the project and returns new plaintext secret."""
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    new_secret = secrets.token_hex(24)
    project.webhook_secret_encrypted = encryption_service.encrypt(new_secret)
    await db.commit()

    return {
        "message": "Webhook secret regenerated successfully.",
        "project_id": project.id,
        "new_webhook_secret": new_secret,
    }


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Deletes a project and all associated deployments, targets, and logs."""
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()
    return None
