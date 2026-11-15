import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import api_router
from app.workers.health_worker import health_worker
from app.services.alert_dispatcher import alert_dispatcher

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pulseops.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes database schema and starts background workers on boot;
    gracefully drains connections and worker loops on shutdown.
    """
    logger.info("Initializing PulseOps Application...")
    await init_db()
    await health_worker.start()
    logger.info("PulseOps backend service fully operational.")

    yield

    logger.info("Shutting down PulseOps backend service...")
    await health_worker.stop()
    await alert_dispatcher.close()
    logger.info("PulseOps shutdown completed cleanly.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-ready lightweight Deployment & Application Health Monitoring Platform",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS explicitly for Vercel production & preview domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else ["*"],
    allow_origin_regex=r"https://.*\.vercel\.app" if "*" not in settings.CORS_ORIGINS else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["System"])
async def health_check():
    """
    Lightweight health check probe for Render Web Service orchestration.
    Render pings this endpoint to confirm service readiness and zero-downtime deploys.
    """
    return {
        "status": "healthy",
        "service": "pulseops-backend",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Welcome to PulseOps API",
        "docs": "/docs",
        "version": settings.VERSION,
    }


# Mount API V1
app.include_router(api_router, prefix=settings.API_V1_STR)
