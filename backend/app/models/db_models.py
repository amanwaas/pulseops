import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    BigInteger,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'developer', 'viewer')", name="check_user_role"),
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    repo_url = Column(String(500), nullable=False)
    provider = Column(String(50), nullable=False)  # 'github' | 'gitlab'
    webhook_secret_encrypted = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("provider IN ('github', 'gitlab')", name="check_project_provider"),
    )

    # Relationships
    deployments = relationship("Deployment", back_populates="project", cascade="all, delete-orphan", lazy="selectin")
    health_targets = relationship("HealthTarget", back_populates="project", cascade="all, delete-orphan", lazy="selectin")
    alert_configs = relationship("AlertConfig", back_populates="project", cascade="all, delete-orphan", lazy="selectin")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    environment = Column(String(50), nullable=False)  # 'development', 'testing', 'staging', 'production'
    commit_sha = Column(String(64), nullable=False, index=True)
    commit_message = Column(Text, nullable=True)
    branch = Column(String(255), nullable=False)
    author = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False)  # 'queued', 'in_progress', 'success', 'failure', 'cancelled'
    duration_seconds = Column(Integer, default=0, nullable=False)
    pipeline_id = Column(String(255), nullable=True)
    pipeline_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("environment IN ('development', 'testing', 'staging', 'production')", name="check_dep_env"),
        CheckConstraint("status IN ('queued', 'in_progress', 'success', 'failure', 'cancelled')", name="check_dep_status"),
        Index("idx_deployments_project_env_created", "project_id", "environment", "created_at"),
    )

    project = relationship("Project", back_populates="deployments")


class HealthTarget(Base):
    __tablename__ = "health_targets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    environment = Column(String(50), nullable=False)
    endpoint_url = Column(String(1000), nullable=False)
    check_interval_seconds = Column(Integer, default=60, nullable=False)
    timeout_seconds = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_status = Column(String(50), default="UNKNOWN", nullable=False)  # 'UNKNOWN', 'UP', 'DOWN', 'DEGRADED'
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("environment IN ('development', 'testing', 'staging', 'production')", name="check_health_env"),
        CheckConstraint("last_status IN ('UNKNOWN', 'UP', 'DOWN', 'DEGRADED')", name="check_health_last_status"),
        UniqueConstraint("project_id", "environment", "endpoint_url", name="uq_project_env_endpoint"),
    )

    project = relationship("Project", back_populates="health_targets")
    health_logs = relationship("HealthLog", back_populates="target", cascade="all, delete-orphan", lazy="raise")
    incidents = relationship("Incident", back_populates="target", cascade="all, delete-orphan", lazy="selectin")


class HealthLog(Base):
    __tablename__ = "health_logs"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    target_id = Column(String(36), ForeignKey("health_targets.id", ondelete="CASCADE"), nullable=False, index=True)
    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=False)
    is_up = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_health_logs_target_checked", "target_id", "checked_at"),
    )

    target = relationship("HealthTarget", back_populates="health_logs")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_type = Column(String(50), nullable=False)  # 'slack', 'teams', 'email', 'webhook'
    destination_url_encrypted = Column(Text, nullable=False)
    notify_on_deployment_fail = Column(Boolean, default=True, nullable=False)
    notify_on_health_fail = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("channel_type IN ('slack', 'teams', 'email', 'webhook')", name="check_alert_channel"),
    )

    project = relationship("Project", back_populates="alert_configs")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_id = Column(String(36), ForeignKey("health_targets.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), default="open", nullable=False)  # 'open', 'resolved'
    failure_reason = Column(Text, nullable=False)
    consecutive_failures = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('open', 'resolved')", name="check_incident_status"),
        Index("idx_incidents_target_status", "target_id", "status"),
    )

    target = relationship("HealthTarget", back_populates="incidents")
