# CareerConnect Production Deployment Runbook & Architecture

This document provides complete instructions for provisioning, running, scaling, and maintaining the CareerConnect platform in production environments.

---

## 1. System Architecture

```mermaid
graph TB
    subgraph Client Tier
        Browser["User Browser (Desktop / Mobile)"]
    end

    subgraph Ingress & Routing
        Ingress["Kubernetes Ingress (TLS via cert-manager)"]
    end

    subgraph Service Layer
        FE["Frontend (Nginx + Vite React 18)"]
        API["Backend API (Gunicorn + Django 6)"]
        Worker["Celery Worker (Heavy ML & LangGraph)"]
        Beat["Celery Beat (Periodic Scheduler, replicas=1)"]
    end

    subgraph Data & Storage Tier
        PG[("PostgreSQL 16 (Primary DB + Connection Pool)")]
        Redis[("Redis 7 (Broker: DB0, Results: DB1, Cache: DB2, Guardrails: DB3)")]
        S3[("S3 / MinIO Object Storage (Resumes & Snapshots)")]
        FAISS[("Persistent Volume (FAISS Vector Index Cache)")]
    end

    subgraph Observability
        Prom["Prometheus Metrics (/metrics)"]
        Graf["Grafana Dashboard"]
        Sentry["Sentry Error Tracking"]
    end

    Browser -->|HTTPS :443| Ingress
    Ingress -->|/| FE
    Ingress -->|/api, /jobs, /applications, /healthz| API

    API -->|ORM & Pooling| PG
    API -->|Read/Write Cache & Locks| Redis
    API -->|Uploads / Presigned URLs| S3
    API -->|Enqueue Tasks| Redis

    Worker -->|Consume Tasks| Redis
    Worker -->|Read / Write Status & Actions| PG
    Worker -->|Load / Save Vector Store| FAISS
    Worker -->|Presigned Media Fetch| S3

    Beat -->|Schedule Periodic Tasks| Redis

    API -->|Metrics| Prom
    Worker -->|Metrics| Prom
    API -->|Exception Tracking| Sentry
    Prom --> Graf
```

---

## 2. Environment Variables Reference

All configurations must be supplied via environment variables or Kubernetes Secrets. Never hardcode sensitive credentials.

| Variable Name | Default / Sample | Required | Description |
| :--- | :--- | :---: | :--- |
| `SECRET_KEY` | *(Random 50+ char string)* | **Yes** | Django cryptographic secret key. |
| `DEBUG` | `False` | No | Enables debug tracebacks. **Always False in Production**. |
| `ALLOWED_HOSTS` | `careerconnect.example.com,api.careerconnect.com` | **Yes** | Comma-separated list of valid host headers. |
| `DATABASE_URL` | `postgresql://user:pass@postgres-service:5432/careerconnect` | **Yes** | PostgreSQL connection URI parsed by `dj-database-url`. |
| `CONN_MAX_AGE` | `600` | No | Connection age fallback when pooling is disabled. |
| `USE_DB_POOL` | `True` | No | Activates psycopg 3 connection pooling (`psycopg_pool`). |
| `DB_POOL_MIN_SIZE` | `2` | No | Minimum idle database connections maintained by the pool. |
| `DB_POOL_MAX_SIZE` | `10` | No | Maximum concurrent database connections allowed per worker/process. |
| `DB_POOL_TIMEOUT` | `10.0` | No | Seconds to wait for an available connection before timing out. |
| `REDIS_URL` | `redis://redis-service:6379` | **Yes** | Base Redis URL; database indices are appended by settings. |
| `CELERY_RESULT_BACKEND`| `redis://redis-service:6379/1` | No | Celery task result backend (DB 1); derived from `REDIS_URL` by default. |
| `CACHE_REDIS_URL` | `redis://redis-service:6379/2` | No | Django application cache backend (`django-redis`); derived from `REDIS_URL` by default. |
| `USE_REDIS_CACHE` | `True` | No | Activates Redis cache backend (`False` uses `LocMemCache`). |
| `USE_S3_STORAGE` | `True` | No | Routes resume files and media uploads to S3/MinIO. |
| `PILOT_INVITE_ONLY` | `False` | No | Restricts new registrations and logins to the pilot email allowlist when enabled. |
| `PILOT_INVITED_EMAILS` | *(Comma-separated addresses)* | Conditional | Set through a secret manager; required when `PILOT_INVITE_ONLY=True`. |
| `AWS_STORAGE_BUCKET_NAME`| `careerconnect-resumes` | Conditional | S3/MinIO bucket name for candidate resumes. |
| `AWS_S3_ENDPOINT_URL` | `http://minio:9000` (Local) / `None` (AWS) | Conditional | Custom S3 endpoint (required for MinIO/LocalStack). |
| `AWS_ACCESS_KEY_ID` | `minioadmin` / `[AWS Key]` | Conditional | S3 authentication access key. |
| `AWS_SECRET_ACCESS_KEY`| `minioadmin` / `[AWS Secret]` | Conditional | S3 authentication secret key. |
| `FAISS_INDEX_DIR` | `/app/data/faiss_index` | No | Volume mount path storing serialized FAISS indexes. |
| `SENTRY_DSN` | `https://[key]@sentry.io/[project]` | No | DSN for remote error monitoring and alerting. |
| `AUTO_APPLY_AGENT_ENABLED`| `True` | No | Platform kill switch for Auto-Apply agent jobs. |
| `SCREENING_AGENT_ENABLED`| `True` | No | Platform kill switch for Recruiter Screening agent. |
| `DIGEST_AGENT_ENABLED`| `True` | No | Platform kill switch for Candidate Job Digest agent. |
| `SCHEDULING_AGENT_ENABLED`| `True` | No | Platform kill switch for Interview Scheduling agent. |

---

## 3. Production Architecture & Infrastructure Hardening

### 3.1 Database Connection Pooling: `psycopg_pool` vs `CONN_MAX_AGE`
In high-throughput multi-threaded web servers (such as Gunicorn with threads or Celery concurrency), `CONN_MAX_AGE` only provides thread-local connection reuse, meaning each thread opens and maintains its own private TCP connection. Under traffic spikes across multiple pods, this quickly exhausts PostgreSQL's `max_connections`.

CareerConnect integrates **`psycopg_pool` (ConnectionPool from psycopg 3.2.0)** configured natively in `backend/job/settings.py`:
- `DATABASES['default']['OPTIONS']['pool']`:
  - `min_size`: 2 warm connections per process.
  - `max_size`: 10 connections per process with backpressure queuing.
  - `timeout`: 10.0 seconds connection acquisition timeout.
- This manages a true pooled multiplexing layer across request threads, preventing connection refusal errors without requiring an external PgBouncer sidecar for modest cluster sizes. When scaling to >20 API pods, an external PgBouncer deployment can be inserted transparently by updating `DATABASE_URL`.

The API invokes the matching pipeline directly for resume summaries and autofill. It therefore uses the CPU-only ML dependencies from `backend/requirements-ml.txt`, as does the Celery worker; moving those packages to the worker alone would change API matching behavior.

### 3.2 Zero-Lock Index Migrations: `AddIndexConcurrently`
Standard Django `AddIndex` operations execute `CREATE INDEX`, which acquires an `ACCESS EXCLUSIVE` table lock in PostgreSQL. This blocks all read and write traffic on critical tables (`jobs_job`, `application_application`, `agents_agentaction`) during production migrations.

All production index migrations ([`jobs/0002`](file:///c:/Users/Smeet/job1/backend/jobs/migrations/0002_alter_job_options_job_job_active_expires_idx_and_more.py), [`application/0005`](file:///c:/Users/Smeet/job1/backend/application/migrations/0005_alter_application_options_and_more.py), [`agents/0002`](file:///c:/Users/Smeet/job1/backend/agents/migrations/0002_rename_agents_agen_user_id_e73b80_idx_act_user_status_idx_and_more.py)) are configured with:
- `atomic = False` (disables the wrapping transaction block required by PostgreSQL for concurrent indexing).
- `AddIndexConcurrently`: Builds B-tree indexes concurrently in the background without acquiring write locks.
- A vendor check shim ensures that when unit tests run on SQLite, it safely falls back to standard indexing.

### 3.3 Celery Beat Single-Instance Guarantee: `strategy.type: Recreate`
Celery Beat is a stateful scheduler that evaluates cron intervals. If a standard `RollingUpdate` strategy is used, Kubernetes brings up a new pod before terminating the old one, resulting in a window where **two Celery Beat instances run simultaneously**. This causes severe duplicate task dispatch (e.g., duplicate auto-apply jobs and duplicate email notifications).

To prevent this:
- [`k8s/base/celery-beat-deployment.yaml`](file:///c:/Users/Smeet/job1/k8s/base/celery-beat-deployment.yaml) strictly sets:
  ```yaml
  spec:
    replicas: 1
    strategy:
      type: Recreate
  ```
- This ensures the active scheduler is completely stopped before any new pod is spawned.

### 3.4 Vector Index Distribution with `readOnlyRootFilesystem: true`
All production containers in CareerConnect are locked down with root filesystem immutability:
```yaml
securityContext:
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
```
Because the container root filesystem is read-only, FAISS vector index files cannot be written to or read from root directory locations.

The architecture solves this via:
1. **Persistent Volume Mount**:
   - Both API and Celery Worker pods mount a shared volume (`careerconnect-faiss-pvc`) to `/app/data`.
   - The environment variable `FAISS_INDEX_DIR=/app/data/faiss_index` instructs the application where to persist and read `index.faiss` and `index.pkl`.
2. **Ephemeral `/tmp` Mount**:
   - An `emptyDir: {}` volume is mounted at `/tmp` across all pods (`api`, `worker`, `beat`) to accommodate Python, Celery, and Hugging Face temporary lock files and sockets.
3. **Hot Mtime Cache Invalidation**:
   - `FAISSIndexManager.get_index()` monitors `index.faiss` filesystem modification time (`index_file.stat().st_mtime`).
   - When the Celery worker task (`application.ai.tasks.rebuild_faiss_index_task`) persists a rebuilt vector index to `/app/data/faiss_index`, API pods immediately detect the updated mtime on disk and reload the FAISS index into memory **without requiring a container restart or deployment rollout**.
4. **Multi-AZ / Cloud-Native S3 Sync Option**:
   - In cloud environments without multi-zone shared ReadWriteMany block storage, an `initContainer` or S3 event task downloads the index bundle from the MinIO/S3 bucket (`s3://careerconnect-media/faiss_index.tar.gz`) directly into a local pod `emptyDir` mount at container startup.

---

## 4. Local Development & Smoke Testing

### Running the Full Development Stack
```bash
# Starts Postgres, Redis, MinIO, API, Worker, Beat, and Frontend
docker compose up -d

# Verify all containers are healthy
docker compose ps
```

---

## 5. Kubernetes Operations Runbook

### Deploying to Environments via Kustomize

```bash
# Build & preview manifests for staging or prod
kubectl kustomize k8s/overlays/staging
kubectl kustomize k8s/overlays/prod

# Apply to cluster
kubectl apply -k k8s/overlays/staging
kubectl apply -k k8s/overlays/prod
```

### Pre-Deployment Database Migrations
Migrations are managed via a pre-rollout Kubernetes Job (`k8s/base/migrate-job.yaml`):
```bash
kubectl apply -f k8s/base/migrate-job.yaml
kubectl wait --for=condition=complete --timeout=120s job/django-migrate -n careerconnect
```

### Rolling Updates and Rollback Strategy
All Deployments (`api`, `worker`, `frontend`) are configured with rolling update strategies:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```
If an issue is detected during or after deployment:
```bash
# Check rollout status
kubectl rollout status deployment/careerconnect-api -n careerconnect

# Instant rollback to previous stable revision
kubectl rollout undo deployment/careerconnect-api -n careerconnect
kubectl rollout undo deployment/careerconnect-worker -n careerconnect
kubectl rollout undo deployment/careerconnect-frontend -n careerconnect
```

---

## 6. Database Backup and Recovery Runbook

CareerConnect includes automated backup utilities in `scripts/`:
- Cross-platform CLI: [`scripts/backup_restore.py`](../scripts/backup_restore.py)

### Creating a Manual Backup
```bash
# Creates a compressed, timestamped pg_dump archive in backups/
python scripts/backup_restore.py backup --dir backups/ --format dump
```

### Restoring from Backup
```bash
# Restores database state from a specified dump file after confirmation
python scripts/backup_restore.py restore backups/careerconnect_pg_<timestamp>.dump
```

Restore overwrites the database selected by `DATABASE_URL`; test recovery only against an isolated database. Restoration has not been verified for this staging environment.

---

## 7. Horizontal Pod Autoscaling (HPA)

Autoscalers are configured for traffic-sensitive components:
- **API Deployment**: Scales from 2 to 10 replicas when average CPU utilization exceeds 70% or memory exceeds 80%.
- **Worker Deployment**: Scales from 2 to 8 replicas based on CPU demand and Celery backlog.
- **Beat Deployment**: **Strictly pinned to `replicas: 1`** with no HPA to eliminate duplicate task dispatch.

---

## 8. Incident Response Checklist

When responding to an alert or service degradation:

1. **Verify Health Probes**:
   ```bash
   curl -I https://careerconnect.example.com/healthz
   curl -I https://careerconnect.example.com/readyz
   ```
2. **Inspect Container Logs**:
   ```bash
   kubectl logs -n careerconnect -l app=careerconnect-api --tail=100 -f
   kubectl logs -n careerconnect -l app=careerconnect-worker --tail=100 -f
   ```
3. **Emergency Kill Switches**:
   If an agent malfunctions or causes high upstream load, disable it instantly without rebuilding images:
   ```bash
   kubectl set env deployment/careerconnect-api AUTO_APPLY_AGENT_ENABLED=False -n careerconnect
   kubectl set env deployment/careerconnect-worker AUTO_APPLY_AGENT_ENABLED=False -n careerconnect
   ```
4. **Redis Cache Eviction**:
   If cached recommendations or embeddings become stale, flush DB 2 safely:
   ```bash
   kubectl exec -it redis-0 -n careerconnect -- redis-cli -n 2 FLUSHDB
   ```
5. **Rebuilding Vector Indices**:
   Trigger an immediate on-demand reindex of all active jobs:
   ```bash
   kubectl create job --from=cronjob/faiss-reindex-cron faiss-manual-reindex -n careerconnect
   ```
