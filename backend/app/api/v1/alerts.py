from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_admin, require_viewer
from app.core.encryption import encryption_service
from app.models.db_models import AlertConfig, Project
from app.models.schemas import AlertConfigCreate, AlertConfigResponse
from app.services.alert_dispatcher import alert_dispatcher

router = APIRouter(prefix="/alerts", tags=["Alert Configurations"])


def mask_url_or_email(s: str) -> str:
    """Masks secret webhook tokens or email addresses for safe dashboard display."""
    if "@" in s:
        parts = s.split("@")
        name = parts[0]
        masked_name = name[:2] + "****" if len(name) > 2 else "****"
        return f"{masked_name}@{parts[1]}"
    if len(s) > 16:
        return s[:12] + "••••••••" + s[-4:]
    return "••••••••"


@router.get("", response_model=List[AlertConfigResponse])
async def list_alert_configs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_viewer),
):
    """Lists configured alert channels for a project with masked destinations."""
    stmt = select(AlertConfig).where(AlertConfig.project_id == project_id)
    res = await db.execute(stmt)
    configs = res.scalars().all()

    results = []
    for c in configs:
        plain_dest = encryption_service.decrypt(c.destination_url_encrypted)
        results.append(
            AlertConfigResponse(
                id=c.id,
                project_id=c.project_id,
                channel_type=c.channel_type,
                masked_destination=mask_url_or_email(plain_dest),
                notify_on_deployment_fail=c.notify_on_deployment_fail,
                notify_on_health_fail=c.notify_on_health_fail,
                created_at=c.created_at,
            )
        )
    return results


@router.post("", response_model=AlertConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_config(
    project_id: str,
    config_in: AlertConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Configures a new notification channel (Slack, Teams, Email, Webhook)."""
    proj_stmt = select(Project).where(Project.id == project_id)
    proj_res = await db.execute(proj_stmt)
    if not proj_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    encrypted_dest = encryption_service.encrypt(config_in.destination_url)

    config = AlertConfig(
        project_id=project_id,
        channel_type=config_in.channel_type,
        destination_url_encrypted=encrypted_dest,
        notify_on_deployment_fail=config_in.notify_on_deployment_fail,
        notify_on_health_fail=config_in.notify_on_health_fail,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)

    return AlertConfigResponse(
        id=config.id,
        project_id=config.project_id,
        channel_type=config.channel_type,
        masked_destination=mask_url_or_email(config_in.destination_url),
        notify_on_deployment_fail=config.notify_on_deployment_fail,
        notify_on_health_fail=config.notify_on_health_fail,
        created_at=config.created_at,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Removes an alert channel configuration."""
    stmt = select(AlertConfig).where(AlertConfig.id == config_id)
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Alert config not found")

    await db.delete(config)
    await db.commit()
    return None


@router.post("/{config_id}/test")
async def test_alert_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """Sends a sample test alert to verify webhook / email delivery."""
    stmt = select(AlertConfig).where(AlertConfig.id == config_id)
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Alert config not found")

    dest = encryption_service.decrypt(config.destination_url_encrypted)
    await alert_dispatcher.dispatch_alert(
        channel_type=config.channel_type,
        destination_url_or_email=dest,
        title="PulseOps Alert Test",
        message="This is a test notification confirming your webhook integration is working properly.",
        severity="INFO",
        metadata={
            "channel": config.channel_type,
            "status": "Operational",
            "test_user": user["email"],
        },
    )
    return {"message": f"Test alert dispatched to {config.channel_type}."}
