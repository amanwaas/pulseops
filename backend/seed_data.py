import asyncio
import secrets
from datetime import datetime, timezone, timedelta
import random

from app.core.database import AsyncSessionLocal, init_db
from app.core.security import get_password_hash
from app.core.encryption import encryption_service
from app.models.db_models import User, Project, HealthTarget, HealthLog, Deployment, AlertConfig, Incident


async def seed():
    print("Initializing database...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # 1. Seed Users
        users = [
            User(
                email="admin@pulseops.io",
                password_hash=get_password_hash("AdminPulse123!"),
                role="admin",
            ),
            User(
                email="dev@pulseops.io",
                password_hash=get_password_hash("DevPulse123!"),
                role="developer",
            ),
            User(
                email="viewer@pulseops.io",
                password_hash=get_password_hash("ViewerPulse123!"),
                role="viewer",
            ),
        ]
        for u in users:
            session.add(u)
        await session.flush()
        print(f"Created {len(users)} users.")

        # 2. Seed Projects (5 microservices representing 5-20 project scale)
        project_defs = [
            ("Auth Gateway Service", "auth-gateway", "https://github.com/acme/auth-gateway", "github"),
            ("Billing & Payment Engine", "billing-engine", "https://gitlab.com/acme/billing-engine", "gitlab"),
            ("Inventory Catalog API", "inventory-catalog", "https://github.com/acme/inventory-catalog", "github"),
            ("Notification Dispatcher", "notification-dispatcher", "https://github.com/acme/notification-dispatcher", "github"),
            ("Customer Analytics ETL", "customer-analytics", "https://gitlab.com/acme/customer-analytics", "gitlab"),
        ]

        projects = []
        for name, slug, repo, provider in project_defs:
            raw_secret = secrets.token_hex(24)
            p = Project(
                name=name,
                slug=slug,
                repo_url=repo,
                provider=provider,
                webhook_secret_encrypted=encryption_service.encrypt(raw_secret),
            )
            session.add(p)
            projects.append(p)
        await session.flush()
        print(f"Created {len(projects)} projects.")

        # 3. Seed Health Targets
        now = datetime.now(timezone.utc)
        targets = []
        for p in projects:
            # Add production target
            t_prod = HealthTarget(
                project_id=p.id,
                environment="production",
                endpoint_url="https://httpbin.org/status/200",
                check_interval_seconds=30,
                timeout_seconds=5,
                is_active=True,
                last_status="UP",
                last_checked_at=now,
            )
            session.add(t_prod)
            targets.append(t_prod)

            # Add staging target
            t_stage = HealthTarget(
                project_id=p.id,
                environment="staging",
                endpoint_url="https://httpbin.org/status/200",
                check_interval_seconds=60,
                timeout_seconds=5,
                is_active=True,
                last_status="UP",
                last_checked_at=now,
            )
            session.add(t_stage)
            targets.append(t_stage)

        await session.flush()
        print(f"Created {len(targets)} health targets.")

        # 4. Seed Time-Series Health Logs (past 24 hours)
        logs = []
        for t in targets:
            # Baseline latency based on project
            base_latency = random.uniform(45.0, 120.0)
            for i in range(48):  # Every 30 mins over 24h
                t_point = now - timedelta(minutes=30 * (48 - i))
                # Add natural jitter and occasional spike
                jitter = random.uniform(-10.0, 15.0)
                spike = 350.0 if i in (18, 32) else 0.0
                latency = max(20.0, base_latency + jitter + spike)

                is_up = True
                status_code = 200
                error_msg = None

                log_entry = HealthLog(
                    target_id=t.id,
                    status_code=status_code,
                    latency_ms=round(latency, 2),
                    is_up=is_up,
                    error_message=error_msg,
                    checked_at=t_point,
                )
                logs.append(log_entry)

        session.add_all(logs)
        print(f"Created {len(logs)} simulated historical health log records.")

        # 5. Seed Deployments
        deployments = []
        commits = [
            ("7a8f3b2", "feat(auth): add OAuth2 refresh token rotation", "Sarah Chen", "main", "success", 145),
            ("9c4e1d5", "fix(db): optimize connection pool settings for Neon", "Alex Rivera", "main", "success", 120),
            ("3d2b8f1", "perf(cache): implement redis caching layer for catalog", "David Kim", "main", "success", 185),
            ("1a5c9e2", "refactor(api): upgrade to FastAPI 0.110 async endpoints", "Elena Rostova", "staging", "success", 95),
            ("8f6a4b1", "feat(webhook): add HMAC-SHA256 signature verification", "Marcus Vance", "main", "success", 110),
            ("4b2c1d9", "chore(deps): bump pydantic to v2.6.4", "Bot Renovate", "testing", "failure", 62),
        ]

        for p in projects:
            for i, (sha, msg, author, branch, dep_status, duration) in enumerate(commits):
                dep_time = now - timedelta(hours=random.randint(1, 48))
                env = "production" if branch == "main" else branch
                d = Deployment(
                    project_id=p.id,
                    environment=env,
                    commit_sha=f"{sha}{random.randint(100000, 999999)}",
                    commit_message=msg,
                    branch=branch,
                    author=author,
                    status=dep_status,
                    duration_seconds=duration,
                    pipeline_id=f"pipe-{random.randint(1000, 9999)}",
                    pipeline_url=f"{p.repo_url}/actions/runs/{random.randint(100000, 999999)}",
                    created_at=dep_time,
                )
                deployments.append(d)

        session.add_all(deployments)
        print(f"Created {len(deployments)} deployments.")

        # 6. Seed Sample Alert Config
        for p in projects:
            cfg = AlertConfig(
                project_id=p.id,
                channel_type="slack",
                destination_url_encrypted=encryption_service.encrypt("https://hooks.slack.com/services/T000/B000/XXXXX"),
                notify_on_deployment_fail=True,
                notify_on_health_fail=True,
            )
            session.add(cfg)

        await session.commit()
        print("Database seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
