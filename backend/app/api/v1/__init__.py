from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.projects import router as projects_router
from app.api.v1.deployments import router as deployments_router
from app.api.v1.health import router as health_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.websocket import router as ws_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(deployments_router)
api_router.include_router(health_router)
api_router.include_router(webhooks_router)
api_router.include_router(alerts_router)
api_router.include_router(incidents_router)
api_router.include_router(ws_router)
