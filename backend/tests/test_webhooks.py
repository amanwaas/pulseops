import uuid
import hmac
import hashlib
import json
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import AsyncSessionLocal, init_db
from app.core.encryption import encryption_service
from app.models.db_models import Project


@pytest.mark.asyncio
async def test_github_webhook_hmac_verification():
    await init_db()
    raw_secret = "test-secret-12345"
    unique_slug = f"test-webhook-{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        project = Project(
            name="Test Webhook Project",
            slug=unique_slug,
            repo_url="https://github.com/acme/test",
            provider="github",
            webhook_secret_encrypted=encryption_service.encrypt(raw_secret),
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project_id = project.id

    payload = {
        "commit_sha": "abc1234567890abcdef1234567890abcdef12",
        "commit_message": "feat: test automated deploy",
        "branch": "main",
        "author": "Alice",
        "status": "success",
        "environment": "production",
        "duration_seconds": 120,
    }
    payload_bytes = json.dumps(payload).encode("utf-8")

    # 1. Valid Signature
    valid_sig = hmac.new(raw_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/webhooks/github/{project_id}",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={valid_sig}",
                "X-GitHub-Event": "deployment",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "successfully" in data["message"]

        # 2. Out-of-order Webhook: Send in_progress payload for the same commit
        # The DeploymentStateMachine must preserve the terminal SUCCESS status!
        in_progress_payload = {
            "commit_sha": payload["commit_sha"],
            "commit_message": payload["commit_message"],
            "branch": payload["branch"],
            "status": "in_progress",
            "environment": "production",
        }
        ip_bytes = json.dumps(in_progress_payload).encode("utf-8")
        ip_sig = hmac.new(raw_secret.encode("utf-8"), ip_bytes, hashlib.sha256).hexdigest()
        resp_ip = await ac.post(
            f"/api/v1/webhooks/github/{project_id}",
            content=ip_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={ip_sig}",
                "X-GitHub-Event": "deployment",
            },
        )
        assert resp_ip.status_code == 200
        # Verify status remained 'success'
        assert resp_ip.json()["status"] == "success"

        # 3. Invalid Signature -> HTTP 401
        invalid_resp = await ac.post(
            f"/api/v1/webhooks/github/{project_id}",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalidhash00000000000000000000000000000000",
                "X-GitHub-Event": "deployment",
            },
        )
        assert invalid_resp.status_code == 401

        # 3. Missing Signature Header -> HTTP 401
        missing_resp = await ac.post(
            f"/api/v1/webhooks/github/{project_id}",
            content=payload_bytes,
            headers={"Content-Type": "application/json"},
        )
        assert missing_resp.status_code == 401
