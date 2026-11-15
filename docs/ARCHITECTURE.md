# PulseOps: System Architecture & Engineering Specification

## 1. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph CI_CD["CI/CD Providers"]
        GH["GitHub Actions Pipeline"]
        GL["GitLab CI/CD Pipeline"]
    end

    subgraph Render["Render (Persistent Web Service)"]
        subgraph FastAPI["FastAPI Backend (Python 3.11+ / asyncpg)"]
            WH["Webhook Ingestion Engine\n(HMAC-SHA256 / Token Validation)"]
            REST["Authenticated REST APIs\n(JWT & RBAC Middleware)"]
            WS["WebSocket & SSE Manager\n(Real-Time Event Stream)"]
            WORKER["Background Health & Retention Worker\n(Concurrent Non-Blocking httpx Loop)"]
            ALERT["Alert Dispatcher\n(Exponential Backoff Retries)"]
            CRYPTO["AES-256-GCM Encryption\n(Secrets & Webhook URLs at Rest)"]
        end
    end

    subgraph Neon["Neon Serverless PostgreSQL 16"]
        PGB["PgBouncer Pooler (-pooler)"]
        DB[("PostgreSQL 16 Tables:\n• projects\n• deployments\n• health_targets\n• health_logs\n• alert_configs\n• incidents\n• users")]
    end

    subgraph Vercel["Vercel (Edge CDN Frontend)"]
        FE["React 18 + Vite + TypeScript\n• TanStack React Query\n• Apache ECharts Time-Series\n• Deployment Timeline Annotations\n• Single Pane of Glass Cards"]
    end

    subgraph Targets["Monitored Services (5–20 Projects)"]
        T1["Target API: Production"]
        T2["Target API: Staging"]
        T3["Target API: Testing"]
    end

    subgraph Notifications["Alerting Channels"]
        SLACK["Slack Webhook"]
        TEAMS["Microsoft Teams Card"]
        EMAIL["Email (SMTP)"]
        GEN["Generic Webhook"]
    end

    %% Communications
    GH -->|POST with X-Hub-Signature-256| WH
    GL -->|POST with X-Gitlab-Token| WH
    WH --> CRYPTO
    WH --> DB
    WH --> WS

    WORKER -->|HTTP GET Probe (30s-120s)| Targets
    WORKER -->|Write latency & status| DB
    WORKER -->|Transition event| WS
    WORKER -->|State failure or recovery| ALERT

    ALERT --> Notifications

    FE <-->|REST Requests + JWT| REST
    FE <-->|Live Events WebSocket / SSE| WS
    REST <--> PGB
    PGB <--> DB
```

---

## 2. Explicit State Machines & Invariant Architecture

To eliminate implicit state bugs, race conditions, out-of-order webhook corruption, and telemetry flapping, PulseOps centralizes its core lifecycles into formal state machines in `app/core/state_machines.py`:

### State Machine 1: Deployment Lifecycle (`DeploymentStateMachine`)
- **States:** `QUEUED`, `IN_PROGRESS`, `SUCCESS`, `FAILURE`, `CANCELLED`
- **Terminal States:** `SUCCESS`, `FAILURE`, `CANCELLED` (immutable)
- **Allowed Transitions:**
  - `QUEUED` $\to$ `IN_PROGRESS`, `SUCCESS`, `FAILURE`, `CANCELLED`
  - `IN_PROGRESS` $\to$ `SUCCESS`, `FAILURE`, `CANCELLED`
  - Terminal $\to$ Terminal only (idempotent; rejects out-of-order delayed webhooks)
- **Guarantees:** A delayed `in_progress` webhook arriving after a `success` webhook cannot regress deployment status.

### State Machine 2: Target Health & Outages (`HealthStateMachine`)
- **States:** `UNKNOWN`, `UP`, `DEGRADED`, `DOWN`
- **Guarantees:**
  - At most **one** open incident can exist per target at any time.
  - Flap prevention: Requires $N$ (default 3) consecutive probe failures before opening an incident.
  - A successful probe always resolves open incidents even if target status was desynchronized.

### State Machine 3: Incident Lifecycle (`IncidentStateMachine`)
- **States:** `OPEN`, `RESOLVED`
- **Transitions:** `OPEN` $\to$ `RESOLVED` (Terminal).
- **Guarantees:** Resolving an already-resolved incident is rejected with HTTP 400, preserving original `resolved_at` timestamps.

### State Machine 4: In-Flight Probe Concurrency (`ProbeExecutionState`)
- **Worker Lock:** `_in_flight_targets: Set[str]`
- **Guarantees:** When a probe takes longer than loop tick cadence, subsequent ticks do not spawn concurrent duplicate probes for the same target, preventing database write race conditions and metric flapping.

### State Machine 5: Overall Project Health (`ProjectHealthReducer`)
- **Severity Lattice:** $\text{DOWN} > \text{DEGRADED} > \text{UNKNOWN} > \text{UP}$
- **Guarantees:** Deterministic aggregation of multiple microservice endpoints into a single pane of glass status.

### State Machine 6: Frontend WebSocket Connection (`useWebSocket`)
- **States:** `DISCONNECTED` $\to$ `CONNECTING` $\to$ `CONNECTED` $\to$ `RECONNECTING`
- **Guarantees:** Connection attempts are guarded; duplicate socket creation on rapid disconnect/error events is prevented.

```
              ┌────────────────────────────────────────────────────────┐
              │                                                        │
              ▼                                                        │
      ┌───────────────┐        Success (2xx)                           │
      │    UNKNOWN    │─────────────────────────────┐                  │
      └───────────────┘                             │                  │
              │                                     ▼                  │
              │ Failure (non-2xx / timeout)  ┌───────────────┐         │
              ▼                              │      UP       │◄────────┘
      ┌───────────────┐                      └───────────────┘   Success (2xx)
      │   DEGRADED    │                             │            [Closes Incident]
      │ (Failure 1-2) │                             │ Failure    [Dispatches RESOLVED]
      └───────────────┘                             ▼
              │                             ┌───────────────┐
              │ Failure count reaches 3     │   DEGRADED    │
              ▼                             │ (Failure 1-2) │
      ┌───────────────┐                     └───────────────┘
      │     DOWN      │                             │
      │  (Incident)   │◄────────────────────────────┘
      │ [Dispatches   │   Failure count >= 3
      │  CRITICAL]    │
      └───────────────┘
```

### State Machine Rules:
1. **Initial State (`UNKNOWN`):** On initial target registration, `consecutive_failures = 0`.
2. **Degraded State (`DEGRADED`):** When a probe fails (timeout or non-2xx), `consecutive_failures` increments (1 or 2). Target enters `DEGRADED` state. **No alert storming occurs**.
3. **Outage State (`DOWN`):** When `consecutive_failures >= 3`:
   - State transitions to `DOWN`.
   - A new record is inserted into the `incidents` table with `status = 'open'`.
   - A `CRITICAL` alert is dispatched via `AlertDispatcher` to all configured channels (Slack, Teams, Email).
   - Subsequent failed checks while in `DOWN` do not re-trigger alerts (prevents alert spam).
4. **Recovery Transition (`UP`):**
   - When a probe returns 2xx while target was in `DOWN`:
   - Target transitions to `UP`.
   - `consecutive_failures` is reset to 0.
   - The open incident is updated with `status = 'resolved'` and `resolved_at = NOW()`.
   - A `RESOLVED` notification is immediately dispatched to alert channels.
5. **Latency Spike Detection:**
   - If response latency exceeds `LATENCY_SPIKE_THRESHOLD_MS` (default 1500ms), a warning event is broadcast.

---

## 3. Webhook Ingestion & Cryptographic Verification

### GitHub Actions Webhook Ingestion
- Endpoint: `POST /api/v1/webhooks/github/{project_id}`
- Signature Header: `X-Hub-Signature-256: sha256=<hex_digest>`
- Algorithm:
  $$\text{Signature} = \text{HMAC-SHA256}(\text{ProjectSecret}, \text{RawRequestBody})$$
- Verification: Constant-time comparison using `hmac.compare_digest` to prevent timing attacks.
- Rejection: Payloads missing the header or with mismatching digests are rejected with **HTTP 401 Unauthorized** and logged.

### GitLab CI/CD Webhook Ingestion
- Endpoint: `POST /api/v1/webhooks/gitlab/{project_id}`
- Token Header: `X-Gitlab-Token: <token>`
- Verification: Constant-time comparison against decrypted project secret.

### At-Rest Encryption (AES-256-GCM)
All webhook secrets and incoming alert webhook URLs (e.g. Slack webhook links with auth tokens) are encrypted at rest in PostgreSQL using **AES-256-GCM authenticated encryption**:
- Standard 96-bit (12-byte) cryptographically secure random nonce generated per encryption (`os.urandom(12)`).
- 128-bit (16-byte) Galois authentication tag appended to verify data authenticity.
- Tamper detection: Any modification to ciphertext or tag results in a cryptographic verification failure.

---

## 4. Neon Serverless PostgreSQL 16 & Connection Pooling

Neon uses serverless PostgreSQL architecture where compute instances can automatically suspend when idle and scale on demand. Furthermore, connection pooling is handled by PgBouncer in **transaction pooling mode** on the `-pooler` connection string.

### Essential Connection Configuration:
1. **Disable Prepared Statement Cache:**
   ```python
   connect_args = {"statement_cache_size": 0}
   ```
   *Reason:* PgBouncer in transaction mode assigns different backend PostgreSQL connections between transactions. Client-side prepared statement caches fail with `prepared statement "..." does not exist` if assigned a different backend session.
2. **Automatic Reconnection & Pre-Ping:**
   ```python
   pool_pre_ping = True
   pool_recycle = 300  # 5 minutes
   ```
   *Reason:* When Neon's serverless compute suspends during low traffic, idle socket connections are closed by the server. `pool_pre_ping=True` tests connections with `SELECT 1` before issuing queries, seamlessly re-establishing dropped sockets without request errors.
3. **Connection Footprint:**
   ```python
   pool_size = 10
   max_overflow = 20
   ```
   *Reason:* Keeps connection footprint modest, preventing connection exhaustion on Neon free tier (which allows up to 100 pooled connections).

---

## 5. Storage Retention Optimization (30-Day Auto Prune)

For 20 projects with 4 environments each (80 targets) checked every 60 seconds:
- Checks/day: $80 \times 60 \times 24 = 115,200 \text{ rows/day}$.
- Storage footprint: $\sim 10\text{--}15 \text{ MB/day}$.
- Bounded 30-day footprint: $\sim 3.45\text{M rows} \approx 350\text{ MB}$, fitting comfortably within Neon's 0.5 GiB free tier!

The background worker automatically executes `RetentionService.prune_old_health_logs()` once every 24 hours:
```sql
DELETE FROM health_logs WHERE checked_at < NOW() - INTERVAL '30 days';
```
Indexed on `checked_at` for near-instant delete operations.
