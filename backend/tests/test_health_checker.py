import uuid
import pytest
from datetime import datetime, timezone
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

        # Create target pointing to an endpoint that fails (HTTP 500)
        target = HealthTarget(
            project_id=project.id,
            environment="production",
            endpoint_url="https://httpbin.org/status/500",
            check_interval_seconds=10,
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

    # Now simulate recovery by changing target URL to a 200 OK endpoint
    async with AsyncSessionLocal() as s_rec_prep:
        t_prep = (await s_rec_prep.execute(select(HealthTarget).where(HealthTarget.id == target_id))).scalar_one()
        t_prep.endpoint_url = "https://httpbin.org/status/200"
        await s_rec_prep.commit()

    # Recovery Probe: Returns 200 OK -> State transitions to UP, consecutive_failures reset to 0, incident resolved!
    async with AsyncSessionLocal() as s4:
        await checker.check_target(target_id, s4)
        await s4.commit()

    async with AsyncSessionLocal() as s4_check:
        t4 = (await s4_check.execute(select(HealthTarget).where(HealthTarget.id == target_id))).scalar_one()
        assert t4.last_status == "UP"
        assert t4.consecutive_failures == 0

        # Verify open incident was resolved
        open_inc = (await s4_check.execute(select(Incident).where(Incident.target_id == target_id, Incident.status == "open"))).scalar_one_or_none()
        assert open_inc is None

        resolved_inc = (await s4_check.execute(select(Incident).where(Incident.target_id == target_id, Incident.status == "resolved"))).scalar_one_or_none()
        assert resolved_inc is not None
        assert resolved_inc.resolved_at is not None

    await checker.close()
