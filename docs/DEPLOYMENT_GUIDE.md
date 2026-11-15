# PulseOps: Production Deployment & Setup Guide

This guide walks through step-by-step production deployment for:
1. **Neon Serverless PostgreSQL 16** (Database)
2. **Render Persistent Web Service** (FastAPI Backend & Background Worker)
3. **Vercel** (React 18 / Vite Frontend)

---

## Part 1: Provision Neon PostgreSQL 16

1. Go to [Neon Console](https://console.neon.tech/) and sign in.
2. Click **Create Project**:
   - **Name:** `pulseops-production`
   - **Postgres version:** `16`
   - **Region:** Choose the region closest to your Render service (e.g. `US East (Ohio)` or `EU Central (Frankfurt)`).
3. Under **Connection Details**, ensure **Pooled connection** is selected.
   - The connection string will contain `-pooler` in the hostname:
     ```text
     postgres://pulseops_user:password@ep-xyz-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
4. Copy this connection string. In your backend `.env`, prefix with `postgresql+asyncpg://`:
   ```text
   DATABASE_URL=postgresql+asyncpg://pulseops_user:password@ep-xyz-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
5. Run the schema initialization:
   - In Neon SQL Editor, paste the contents of [`database/schema.sql`](file:///c:/Users/comp/Desktop/Grafana/database/schema.sql) and execute.
   - Or apply Alembic migrations:
     ```bash
     cd backend
     alembic upgrade head
     ```

---

## Part 2: Deploy Backend to Render (Persistent Web Service)

Render Web Services provide continuous background processing with automatic health check monitoring.

### Step 1: Create Web Service on Render
1. Go to [Render Dashboard](https://dashboard.render.com/) > **New +** > **Web Service**.
2. Connect your Git repository.
3. Configure settings:
   - **Name:** `pulseops-backend`
   - **Language / Runtime:** `Docker`
   - **Dockerfile Path:** `backend/Dockerfile`
   - **Docker Context:** `backend`
   - **Instance Type:** `Starter` ($7/mo) — *Crucial: Do not use Free tier, as free web services spin down after 15 minutes of inactivity, pausing the background health check worker!*
   - **Health Check Path:** `/healthz`

### Step 2: Configure Environment Variables in Render
Add the following environment variables:

| Key | Value / Instructions |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | Neon pooled URL (`postgresql+asyncpg://...@...-pooler...neon.tech/neondb?sslmode=require`) |
| `ENCRYPTION_KEY` | 32-byte hex key (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `JWT_SECRET` | 32-byte secret (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `CORS_ORIGINS` | `https://pulseops.vercel.app,https://*.vercel.app` |
| `DB_POOL_SIZE` | `10` |
| `DB_MAX_OVERFLOW` | `20` |
| `DB_POOL_RECYCLE_SECONDS` | `300` |
| `HEALTH_CHECK_DEFAULT_INTERVAL_SECONDS` | `60` |

### Step 3: Verify Deployment
Once deployed, Render checks `/healthz`. You should see `200 OK`:
```json
{
  "status": "healthy",
  "service": "pulseops-backend",
  "version": "1.0.0",
  "environment": "production"
}
```

---

## Part 3: Deploy Frontend to Vercel

### Step 1: Import Project to Vercel
1. Go to [Vercel Dashboard](https://vercel.com/new).
2. Import your Git repository.
3. Set **Root Directory** to `frontend`.
4. Vercel automatically detects **Vite**:
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
   - **Install Command:** `npm install`

### Step 2: Configure Environment Variables in Vercel
Add the following variables:

| Key | Value |
|---|---|
| `VITE_API_URL` | `https://pulseops-backend.onrender.com/api/v1` |
| `VITE_WS_URL` | `wss://pulseops-backend.onrender.com/api/v1/ws/live` |

Click **Deploy**. Vercel will build and assign your domain (e.g. `https://pulseops.vercel.app`).

---

## Part 4: Seed Demo Data & Initial Admin Setup

To seed the initial admin account (`admin@pulseops.io` / `AdminPulse123!`) and 5 sample projects:

```bash
cd backend
python seed_data.py
```

Output:
```text
Created 3 users.
Created 5 projects.
Created 10 health targets.
Created 480 simulated historical health log records.
Created 30 deployments.
Database seeding completed successfully!
```

---

## Part 5: Configuring CI/CD Webhooks

### GitHub Actions
1. Navigate to your monitored repository on GitHub.
2. Go to **Settings > Secrets and variables > Actions**.
3. Add a secret named `PULSEOPS_WEBHOOK_SECRET` with the HMAC secret generated in PulseOps.
4. Copy the workflow file [`docs/GITHUB_ACTIONS_EXAMPLE.yml`](file:///c:/Users/comp/Desktop/Grafana/docs/GITHUB_ACTIONS_EXAMPLE.yml) into `.github/workflows/deploy.yml`.

### GitLab CI/CD
1. Navigate to your GitLab repository.
2. Go to **Settings > CI/CD > Variables**.
3. Add `PULSEOPS_WEBHOOK_SECRET` as a **Masked** variable.
4. Copy the pipeline snippet from [`docs/GITLAB_CI_EXAMPLE.yml`](file:///c:/Users/comp/Desktop/Grafana/docs/GITLAB_CI_EXAMPLE.yml) into `.gitlab-ci.yml`.
