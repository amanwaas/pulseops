from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, EmailStr, HttpUrl, ConfigDict, field_validator


# ---------------------------------------------------------
# Auth & User Schemas
# ---------------------------------------------------------
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: Literal["admin", "developer", "viewer"] = "viewer"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---------------------------------------------------------
# Project Schemas
# ---------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = None
    repo_url: str = Field(..., max_length=500)
    provider: Literal["github", "gitlab"] = "github"
    webhook_secret: Optional[str] = None  # If not provided, backend generates secure secret

    @field_validator("name", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return str(v).strip() if v else ""

    @field_validator("slug", mode="before")
    @classmethod
    def sanitize_slug(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        import re
        s = re.sub(r"[^a-zA-Z0-9-]", "-", str(v).lower().strip())
        s = re.sub(r"-+", "-", s).strip("-")
        return s or None

    @field_validator("repo_url", mode="before")
    @classmethod
    def sanitize_repo_url(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
            if v and not v.startswith(("http://", "https://")):
                return f"https://{v}"
        return v or "https://github.com/placeholder"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    repo_url: Optional[str] = None
    provider: Optional[Literal["github", "gitlab"]] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    repo_url: str
    provider: str
    webhook_url: Optional[str] = None
    masked_secret: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Single Pane of Glass Overview Card
class ProjectSummaryCard(BaseModel):
    id: str
    name: str
    slug: str
    repo_url: str
    provider: str
    environments: List[str]
    latest_deployment: Optional[dict] = None
    overall_health: Literal["UP", "DOWN", "DEGRADED", "UNKNOWN"]
    p95_latency_ms: Optional[float] = None
    active_incidents_count: int = 0
    updated_at: datetime


# ---------------------------------------------------------
# Deployment Schemas
# ---------------------------------------------------------
class DeploymentCreate(BaseModel):
    environment: Literal["development", "testing", "staging", "production"]
    commit_sha: str = Field(..., min_length=7, max_length=64)
    commit_message: Optional[str] = None
    branch: str = "main"
    author: Optional[str] = "CI/CD Pipeline"
    status: Literal["queued", "in_progress", "success", "failure", "cancelled"]
    duration_seconds: int = 0
    pipeline_id: Optional[str] = None
    pipeline_url: Optional[str] = None


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    environment: str
    commit_sha: str
    short_commit_sha: str
    commit_message: Optional[str]
    branch: str
    author: Optional[str]
    status: str
    duration_seconds: int
    pipeline_id: Optional[str]
    pipeline_url: Optional[str]
    created_at: datetime


# ---------------------------------------------------------
# Health Target & Health Log Schemas
# ---------------------------------------------------------
class HealthTargetCreate(BaseModel):
    environment: Literal["development", "testing", "staging", "production"]
    endpoint_url: str
    check_interval_seconds: int = Field(default=60, ge=10, le=600)
    timeout_seconds: int = Field(default=5, ge=1, le=30)
    is_active: bool = True


class HealthTargetUpdate(BaseModel):
    endpoint_url: Optional[str] = None
    check_interval_seconds: Optional[int] = Field(None, ge=10, le=600)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=30)
    is_active: Optional[bool] = None


class HealthTargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    environment: str
    endpoint_url: str
    check_interval_seconds: int
    timeout_seconds: int
    is_active: bool
    consecutive_failures: int
    last_status: str
    last_checked_at: Optional[datetime]
    created_at: datetime


class HealthLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_id: str
    status_code: Optional[int]
    latency_ms: float
    is_up: bool
    error_message: Optional[str]
    checked_at: datetime


class LatencyTimeSeriesPoint(BaseModel):
    timestamp: str  # ISO string
    latency_ms: float
    is_up: bool
    status_code: Optional[int] = None


class DeploymentAnnotation(BaseModel):
    timestamp: str
    environment: str
    commit_sha: str
    short_sha: str
    author: Optional[str]
    status: str
    duration_seconds: int


class LatencyAndTimelineResponse(BaseModel):
    target_id: str
    environment: str
    p95_latency_ms: float
    avg_latency_ms: float
    uptime_percentage: float
    points: List[LatencyTimeSeriesPoint]
    deployments: List[DeploymentAnnotation]


# ---------------------------------------------------------
# Alert Config Schemas
# ---------------------------------------------------------
class AlertConfigCreate(BaseModel):
    channel_type: Literal["slack", "teams", "email", "webhook"]
    destination_url: str  # Plaintext in API request, encrypted at rest in DB
    notify_on_deployment_fail: bool = True
    notify_on_health_fail: bool = True


class AlertConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    channel_type: str
    masked_destination: str
    notify_on_deployment_fail: bool
    notify_on_health_fail: bool
    created_at: datetime


# ---------------------------------------------------------
# Incident Schemas
# ---------------------------------------------------------
class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    target_id: str
    project_name: Optional[str] = None
    environment: Optional[str] = None
    endpoint_url: Optional[str] = None
    started_at: datetime
    resolved_at: Optional[datetime]
    status: str
    failure_reason: str
    consecutive_failures: int
