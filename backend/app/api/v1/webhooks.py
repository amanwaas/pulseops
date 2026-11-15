import hmac
import hashlib
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.encryption import encryption_service
from app.core.ws_manager import ws_manager
from app.core.state_machines import DeploymentStatus, DeploymentStateMachine
from app.models.db_models import Project, Deployment, AlertConfig
from app.services.alert_dispatcher import alert_dispatcher

logger = logging.getLogger("pulseops.webhooks")

router = APIRouter(prefix="/webhooks", tags=["Webhooks Ingestion"])


def normalize_environment(env_str: Optional[str], branch: Optional[str] = None) -> str:
    """Normalizes arbitrary environment names to one of the 4 standard environments."""
    if not env_str:
        if branch in ("main", "master", "prod"):
            return "production"
        elif branch in ("staging", "stage"):
            return "staging"
        elif branch in ("test", "testing", "qa"):
            return "testing"
        return "development"

    env_lower = env_str.lower().strip()
    if any(k in env_lower for k in ["prod", "production"]):
        return "production"
    if any(k in env_lower for k in ["stage", "staging"]):
        return "staging"
    if any(k in env_lower for k in ["test", "testing", "qa", "uat"]):
        return "testing"
    return "development"


async def _process_deployment_lifecycle(
    project: Project,
    environment: str,
    commit_sha: str,
    commit_msg: Optional[str],
    branch: str,
    author: Optional[str],
    incoming_status: DeploymentStatus,
    duration: int,
    pipeline_id: Optional[str],
    pipeline_url: Optional[str],
    db: AsyncSession,
) -> Deployment:
    """
    Explicit Deployment Lifecycle State Machine Processor.
    1. Looks up existing deployment for this pipeline/commit.
    2. Enforces forward-only transitions and terminal state immutability.
    3. Handles out-of-order webhook delivery cleanly.
    """
    if not commit_sha:
        commit_sha = "0000000000000000000000000000000000000000"

    existing_deployment: Optional[Deployment] = None
    if pipeline_id:
        stmt = select(Deployment).where(
            Deployment.project_id == project.id,
            Deployment.environment == environment,
            Deployment.pipeline_id == pipeline_id,
        )
        res = await db.execute(stmt)
        existing_deployment = res.scalar_one_or_none()

    if not existing_deployment and commit_sha and commit_sha != "0000000000000000000000000000000000000000":
        # Check by commit SHA and branch in the same environment
        stmt = (
            select(Deployment)
            .where(
                Deployment.project_id == project.id,
                Deployment.environment == environment,
                Deployment.commit_sha == commit_sha,
                Deployment.branch == branch,
            )
            .order_by(Deployment.created_at.desc())
        )
        res = await db.execute(stmt)
        existing_deployment = res.scalars().first()

    if existing_deployment:
        current_status = DeploymentStatus(existing_deployment.status)
        new_status, did_transition = DeploymentStateMachine.transition(current_status, incoming_status)

        if did_transition:
            existing_deployment.status = new_status.value
            if duration > 0:
                existing_deployment.duration_seconds = max(existing_deployment.duration_seconds, duration)
            if commit_msg:
                existing_deployment.commit_message = commit_msg[:500]
            if pipeline_url:
                existing_deployment.pipeline_url = pipeline_url
            if pipeline_id and not existing_deployment.pipeline_id:
                existing_deployment.pipeline_id = pipeline_id

            await db.commit()
            await db.refresh(existing_deployment)

            # Trigger failure alert if state transitioned to failure
            if new_status == DeploymentStatus.FAILURE:
                await _dispatch_deployment_failure_alert(project, existing_deployment, db)

            await ws_manager.broadcast("deployment_updated", {
                "id": existing_deployment.id,
                "project_id": project.id,
                "project_name": project.name,
                "environment": existing_deployment.environment,
                "commit_sha": existing_deployment.commit_sha[:7],
                "commit_message": existing_deployment.commit_message,
                "branch": existing_deployment.branch,
                "author": existing_deployment.author,
                "status": existing_deployment.status,
                "duration_seconds": existing_deployment.duration_seconds,
                "created_at": existing_deployment.created_at.isoformat(),
            })
        else:
            logger.info(
                f"Deployment {existing_deployment.id} kept at status {existing_deployment.status} "
                f"(incoming {incoming_status.value} did not cause valid state advance)"
            )

        return existing_deployment

    # No existing record: Create initial deployment
    deployment = Deployment(
        project_id=project.id,
        environment=environment,
        commit_sha=commit_sha,
        commit_message=commit_msg[:500] if commit_msg else None,
        branch=branch,
        author=author,
        status=incoming_status.value,
        duration_seconds=duration,
        pipeline_id=pipeline_id,
        pipeline_url=pipeline_url,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    logger.info(
        f"Created deployment record: project={project.slug}, env={environment}, "
        f"status={deployment.status}, sha={commit_sha[:7]}"
    )

    if incoming_status == DeploymentStatus.FAILURE:
        await _dispatch_deployment_failure_alert(project, deployment, db)

    await ws_manager.broadcast("deployment_created", {
        "id": deployment.id,
        "project_id": project.id,
        "project_name": project.name,
        "environment": deployment.environment,
        "commit_sha": deployment.commit_sha[:7],
        "commit_message": deployment.commit_message,
        "branch": deployment.branch,
        "author": deployment.author,
        "status": deployment.status,
        "duration_seconds": deployment.duration_seconds,
        "created_at": deployment.created_at.isoformat(),
    })

    return deployment


@router.post("/github/{project_id}", status_code=status.HTTP_200_OK)
async def ingest_github_webhook(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingests & validates GitHub Actions webhooks using HMAC-SHA256 signature verification.
    Enforces deterministic forward-only deployment lifecycle state machine.
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    # 1. Verify project exists
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        logger.warning(f"GitHub webhook rejected: Project ID {project_id} not found.")
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Verify HMAC-SHA256 signature
    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning(f"GitHub webhook rejected: Missing or invalid signature header for project {project.slug}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed X-Hub-Signature-256 header",
        )

    provided_signature = signature_header[len("sha256="):]
    secret = encryption_service.decrypt(project.webhook_secret_encrypted)
    computed_signature = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(provided_signature, computed_signature):
        logger.warning(f"GitHub webhook HMAC mismatch for project {project.slug}. Unauthorized.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HMAC signature verification failed",
        )

    # 3. Parse JSON Payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    commit_sha = ""
    commit_msg = ""
    branch = "main"
    author = "GitHub Actions"
    raw_status = "success"
    environment = "production"
    pipeline_id = None
    pipeline_url = None
    duration = 0

    if "deployment_status" in payload:
        dep_obj = payload.get("deployment", {})
        stat_obj = payload.get("deployment_status", {})
        environment = dep_obj.get("environment", "production")
        commit_sha = dep_obj.get("sha", "")
        commit_msg = dep_obj.get("description") or f"Deploy to {environment}"
        branch = dep_obj.get("ref", "main").replace("refs/heads/", "")
        author = payload.get("sender", {}).get("login", "GitHub Actions")
        raw_status = stat_obj.get("state")
        pipeline_url = stat_obj.get("target_url") or stat_obj.get("log_url")
        pipeline_id = str(dep_obj.get("id", ""))
    elif "workflow_run" in payload:
        wf = payload.get("workflow_run", {})
        branch = wf.get("head_branch", "main")
        commit_sha = wf.get("head_sha", "")
        commit_msg = wf.get("head_commit", {}).get("message", "CI Workflow Run")
        author = wf.get("actor", {}).get("login", "GitHub Actions")
        raw_status = wf.get("conclusion") or wf.get("status")
        environment = normalize_environment(wf.get("name", ""), branch)
        pipeline_id = str(wf.get("id", ""))
        pipeline_url = wf.get("html_url")
    else:
        commit_sha = payload.get("commit_sha", payload.get("sha", ""))
        commit_msg = payload.get("commit_message", payload.get("message", ""))
        branch = payload.get("branch", payload.get("ref", "main")).replace("refs/heads/", "")
        author = payload.get("author", "GitHub Actions")
        raw_status = payload.get("status", "success")
        environment = normalize_environment(payload.get("environment", "production"), branch)
        pipeline_id = str(payload.get("pipeline_id", payload.get("run_id", "")))
        pipeline_url = payload.get("pipeline_url", payload.get("run_url", ""))
        duration = int(payload.get("duration_seconds", payload.get("duration", 0)))

    incoming_status = DeploymentStatus.from_string(raw_status)

    deployment = await _process_deployment_lifecycle(
        project=project,
        environment=environment,
        commit_sha=commit_sha,
        commit_msg=commit_msg,
        branch=branch,
        author=author,
        incoming_status=incoming_status,
        duration=duration,
        pipeline_id=pipeline_id,
        pipeline_url=pipeline_url,
        db=db,
    )

    return {
        "message": "GitHub webhook processed successfully",
        "deployment_id": deployment.id,
        "status": deployment.status,
    }


@router.post("/gitlab/{project_id}", status_code=status.HTTP_200_OK)
async def ingest_gitlab_webhook(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingests & validates GitLab CI/CD webhooks using secret token verification.
    Enforces deterministic forward-only deployment lifecycle state machine.
    """
    raw_body = await request.body()
    gitlab_token = request.headers.get("X-Gitlab-Token")

    # 1. Verify project exists
    stmt = select(Project).where(Project.id == project_id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        logger.warning(f"GitLab webhook rejected: Project ID {project_id} not found.")
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Verify token
    if not gitlab_token:
        logger.warning(f"GitLab webhook rejected: Missing X-Gitlab-Token header for project {project.slug}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Gitlab-Token header",
        )

    secret = encryption_service.decrypt(project.webhook_secret_encrypted)
    if not hmac.compare_digest(gitlab_token.strip(), secret.strip()):
        logger.warning(f"GitLab webhook token mismatch for project {project.slug}. Unauthorized.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitLab token verification failed",
        )

    # 3. Parse JSON Payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    object_kind = payload.get("object_kind", "pipeline")
    commit_sha = ""
    commit_msg = ""
    branch = "main"
    author = "GitLab CI"
    raw_status = "success"
    environment = "production"
    pipeline_id = None
    pipeline_url = None
    duration = 0

    if object_kind == "deployment":
        environment = normalize_environment(payload.get("environment"))
        raw_status = payload.get("status")
        commit_sha = payload.get("commit_url", "").split("/")[-1] or payload.get("short_sha", "")
        commit_msg = payload.get("commit_title", "Deployment run")
        author = payload.get("user", {}).get("name", "GitLab CI")
        duration = int(payload.get("deployable_duration", 0) or 0)
        pipeline_url = payload.get("commit_url")
    elif object_kind == "pipeline":
        pipe_attrs = payload.get("object_attributes", {})
        branch = pipe_attrs.get("ref", "main")
        commit_obj = payload.get("commit", {})
        commit_sha = commit_obj.get("id", "")
        commit_msg = commit_obj.get("message", "Pipeline Run")
        author = payload.get("user", {}).get("name", "GitLab CI")
        raw_status = pipe_attrs.get("status", "success")
        environment = normalize_environment(None, branch)
        pipeline_id = str(pipe_attrs.get("id", ""))
        pipeline_url = payload.get("project", {}).get("web_url", "") + f"/-/pipelines/{pipeline_id}"
        duration = int(pipe_attrs.get("duration", 0) or 0)
    else:
        commit_sha = payload.get("commit_sha", payload.get("sha", ""))
        commit_msg = payload.get("commit_message", payload.get("message", ""))
        branch = payload.get("branch", payload.get("ref", "main")).replace("refs/heads/", "")
        author = payload.get("author", "GitLab CI")
        raw_status = payload.get("status", "success")
        environment = normalize_environment(payload.get("environment", "production"), branch)
        pipeline_id = str(payload.get("pipeline_id", payload.get("run_id", "")))
        pipeline_url = payload.get("pipeline_url", "")
        duration = int(payload.get("duration_seconds", payload.get("duration", 0)))

    incoming_status = DeploymentStatus.from_string(raw_status)

    deployment = await _process_deployment_lifecycle(
        project=project,
        environment=environment,
        commit_sha=commit_sha,
        commit_msg=commit_msg,
        branch=branch,
        author=author,
        incoming_status=incoming_status,
        duration=duration,
        pipeline_id=pipeline_id,
        pipeline_url=pipeline_url,
        db=db,
    )

    return {
        "message": "GitLab webhook processed successfully",
        "deployment_id": deployment.id,
        "status": deployment.status,
    }


async def _dispatch_deployment_failure_alert(project: Project, deployment: Deployment, db: AsyncSession):
    """Dispatches deployment failure notifications across project's alert channels."""
    alert_stmt = select(AlertConfig).where(
        AlertConfig.project_id == project.id,
        AlertConfig.notify_on_deployment_fail == True,
    )
    alerts_res = await db.execute(alert_stmt)
    configs = alerts_res.scalars().all()

    metadata = {
        "project": project.name,
        "environment": deployment.environment,
        "commit_sha": deployment.commit_sha[:7],
        "branch": deployment.branch,
        "author": deployment.author or "N/A",
        "commit_message": deployment.commit_message or "N/A",
        "pipeline_url": deployment.pipeline_url or "N/A",
    }

    for cfg in configs:
        try:
            dest = encryption_service.decrypt(cfg.destination_url_encrypted)
            asyncio.create_task(
                alert_dispatcher.dispatch_alert(
                    channel_type=cfg.channel_type,
                    destination_url_or_email=dest,
                    title=f"Deployment FAILED: {project.name} [{deployment.environment.upper()}]",
                    message=f"Pipeline run failed on branch '{deployment.branch}'. Commit {deployment.commit_sha[:7]}: {deployment.commit_message}",
                    severity="CRITICAL",
                    metadata=metadata,
                )
            )
        except Exception as e:
            logger.error(f"Failed to dispatch deployment failure alert: {e}")
