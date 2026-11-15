import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, init_db
from app.models.db_models import Project, HealthTarget, Incident
from app.core.encryption import encryption_service
from app.services.health_checker import HealthCheckerService


@pytest.mark.asyncio
async def test_health_state_machine_and_incident_lifecycle():
    await init_db()
    unique_slug = f"state-machine-{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        # Create test project
        project = Project(
            name="State Machine Test Project",
            slug=unique_slug,
            repo_url="https://github.com/acme/state-test",
            provider="github",
            webhook_secret_encrypted=encryption_service.encrypt("test-secret"),
        )
        session.add(project)
        await session.flush()

        # Create target
        target = HealthTarget(
            project_id=project.id,
            environment="production",
            endpoint_url="https://api.example.com/health",
            check_interval_seconds=60,
            timeout_seconds=5,
            is_active=True,
            consecutive_failures=0,
            last_status="UP",
        )
        session.add(target)
        await session.commit()
        await session.refresh(target)
        target_id = target.id

    checker = HealthCheckerService()
    mock_500 = MagicMock(status_code=500)
    mock_200 = MagicMock(status_code=200)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_500

        # Probe 1: Failure 1 -> State becomes DEGRADED, consecutive_failures = 1 (No incident opened)
        async with AsyncSessionLocal() as s1:
            await checker.check_target(target_id, s1)
            await s1.commit()

        async with AsyncSessionLocal() as s1_check:
            t1 = (await s1_check.execute(select(HealthTarget).where(HealthTarget.id == target_id))).scalar_one()
            assert t1.consecutive_failures == 1
            assert t1.last_status == "DEGRADED"
            inc1 = (await s1_check.execute(select(Incident).where(Incident.target_id == target_id))).scalar_one_or_none()
            assert inc1 is None  # Flap prevention: no incident on 1st failure

        # Probe 2: Failure 2 -> consecutive_failures = 2 (Still no incident)
        async with AsyncSessionLocal() as s2:
            await checker.check_target(target_id, s2)
            await s2.commit()

        async with AsyncSessionLocal() as s2_check:
            t2 = (await s2_check.execute(select(HealthTarget).where(HealthTarget.id == target_id))).scalar_one()
            assert t2.consecutive_failures == 2
            inc2 = (await s2_check.execute(select(Incident).where(Incident.target_id == target_id))).scalar_one_or_none()
            assert inc2 is None

        # Probe 3: Failure 3 -> Threshold reached! Transitions to DOWN, incident opened!
        async with AsyncSessionLocal() as s3:
            await checker.check_target(target_id, s3)
            await s3.commit()

        async with AsyncSessionLocal() as s3_check:
            t3 = (await s3_check.execute(select(HealthTarget).where(HealthTarget.id == target_id))).scalar_one()
            assert t3.consecutive_failures == 3
            assert t3.last_status == "DOWN"
            inc3 = (await s3_check.execute(select(Incident).where(Incident.target_id == target_id, Incident.status == "open"))).scalar_one_or_none()
            assert inc3 is not None
            assert "500" in inc3.failure_reason

        # Now simulate recovery by changing mock response to 200 OK
        mock_get.return_value = mock_200
        async with AsyncSessionLocal() as s_rec:
            await checker.check_target(target_id, s_rec)
            await s_rec.commit()

        async with AsyncSessionLocal() as s_rec_check:
            t_rec = (await s_rec_check.execute(select(HealthTarget).where(HealthTarget.id == target_id))).scalar_one()
            assert t_rec.consecutive_failures == 0
            assert t_rec.last_status == "UP"

            inc_resolved = (await s_rec_check.execute(select(Incident).where(Incident.target_id == target_id))).scalar_one()
            assert inc_resolved.status == "resolved"
            assert inc_resolved.resolved_at is not None

    await checker.close()
