from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_developer, require_viewer
from app.core.ws_manager import ws_manager
from app.models.db_models import Deployment, Project
from app.models.schemas import DeploymentCreate, DeploymentResponse

router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.get("", response_model=List[DeploymentResponse])
async def list_deployments(
    project_id: Optional[str] = None,
    environment: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """Lists deployments with comprehensive filtering, search, and pagination."""
    stmt = select(Deployment).order_by(Deployment.created_at.desc())

    if project_id:
        stmt = stmt.where(Deployment.project_id == project_id)
    if environment:
        stmt = stmt.where(Deployment.environment == environment)
    if status_filter:
        stmt = stmt.where(Deployment.status == status_filter)
    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            or_(
                Deployment.commit_sha.ilike(search_term),
                Deployment.commit_message.ilike(search_term),
                Deployment.branch.ilike(search_term),
                Deployment.author.ilike(search_term),
            )
        )

    stmt = stmt.limit(limit).offset(offset)
    res = await db.execute(stmt)
    deployments = res.scalars().all()

    results = []
    for d in deployments:
        results.append(
            DeploymentResponse(
                id=d.id,
                project_id=d.project_id,
                environment=d.environment,
                commit_sha=d.commit_sha,
                short_commit_sha=d.commit_sha[:7],
                commit_message=d.commit_message,
                branch=d.branch,
                author=d.author,
                status=d.status,
                duration_seconds=d.duration_seconds,
                pipeline_id=d.pipeline_id,
                pipeline_url=d.pipeline_url,
                created_at=d.created_at,
            )
        )
    return results


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment_record(
    project_id: str,
    deployment_in: DeploymentCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_developer),
):
    """Manually registers a deployment run (e.g. from custom automated scripts)."""
    proj_stmt = select(Project).where(Project.id == project_id)
    proj_res = await db.execute(proj_stmt)
    project = proj_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    deployment = Deployment(
        project_id=project_id,
        environment=deployment_in.environment,
        commit_sha=deployment_in.commit_sha,
        commit_message=deployment_in.commit_message,
        branch=deployment_in.branch,
        author=deployment_in.author,
        status=deployment_in.status,
        duration_seconds=deployment_in.duration_seconds,
        pipeline_id=deployment_in.pipeline_id,
        pipeline_url=deployment_in.pipeline_url,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    # Broadcast event
    await ws_manager.broadcast("deployment_created", {
        "id": deployment.id,
        "project_id": deployment.project_id,
        "project_name": project.name,
        "environment": deployment.environment,
        "commit_sha": deployment.commit_sha[:7],
        "status": deployment.status,
        "created_at": deployment.created_at.isoformat(),
    })

    return DeploymentResponse(
        id=deployment.id,
        project_id=deployment.project_id,
        environment=deployment.environment,
        commit_sha=deployment.commit_sha,
        short_commit_sha=deployment.commit_sha[:7],
        commit_message=deployment.commit_message,
        branch=deployment.branch,
        author=deployment.author,
        status=deployment.status,
        duration_seconds=deployment.duration_seconds,
        pipeline_id=deployment.pipeline_id,
        pipeline_url=deployment.pipeline_url,
        created_at=deployment.created_at,
    )


@router.get("/stats")
async def get_deployment_stats(
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """Aggregates deployment frequency, success rate, and duration metrics."""
    stmt = select(Deployment)
    if project_id:
        stmt = stmt.where(Deployment.project_id == project_id)
    res = await db.execute(stmt)
    deps = res.scalars().all()

    total = len(deps)
    if total == 0:
        return {
            "total_deployments": 0,
            "success_rate": 0.0,
            "avg_duration_seconds": 0,
            "status_breakdown": {},
            "environment_breakdown": {},
        }

    status_counts = {}
    env_counts = {}
    total_duration = 0

    for d in deps:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1
        env_counts[d.environment] = env_counts.get(d.environment, 0) + 1
        total_duration += d.duration_seconds

    success_count = status_counts.get("success", 0)
    return {
        "total_deployments": total,
        "success_rate": round((success_count / total) * 100.0, 1),
        "avg_duration_seconds": round(total_duration / total, 1),
        "status_breakdown": status_counts,
        "environment_breakdown": env_counts,
    }
