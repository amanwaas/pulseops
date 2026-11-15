"""initial_schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-11-15 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='viewer'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.CheckConstraint("role IN ('admin', 'developer', 'viewer')", name="check_user_role"),
    )
    op.create_index('idx_users_email', 'users', ['email'])

    # 2. projects
    op.create_table(
        'projects',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('repo_url', sa.String(length=500), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('webhook_secret_encrypted', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.CheckConstraint("provider IN ('github', 'gitlab')", name="check_project_provider"),
    )
    op.create_index('idx_projects_slug', 'projects', ['slug'])

    # 3. deployments
    op.create_table(
        'deployments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('environment', sa.String(length=50), nullable=False),
        sa.Column('commit_sha', sa.String(length=64), nullable=False),
        sa.Column('commit_message', sa.Text(), nullable=True),
        sa.Column('branch', sa.String(length=255), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pipeline_id', sa.String(length=255), nullable=True),
        sa.Column('pipeline_url', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("environment IN ('development', 'testing', 'staging', 'production')", name="check_dep_env"),
        sa.CheckConstraint("status IN ('queued', 'in_progress', 'success', 'failure', 'cancelled')", name="check_dep_status"),
    )
    op.create_index('idx_deployments_project_env_created', 'deployments', ['project_id', 'environment', 'created_at'])
    op.create_index('idx_deployments_commit_sha', 'deployments', ['commit_sha'])

    # 4. health_targets
    op.create_table(
        'health_targets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('environment', sa.String(length=50), nullable=False),
        sa.Column('endpoint_url', sa.String(length=1000), nullable=False),
        sa.Column('check_interval_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_status', sa.String(length=50), nullable=False, server_default='UNKNOWN'),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'environment', 'endpoint_url', name='uq_project_env_endpoint'),
    )
    op.create_index('idx_health_targets_active', 'health_targets', ['is_active'])

    # 5. health_logs
    op.create_table(
        'health_logs',
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), primary_key=True, autoincrement=True),
        sa.Column('target_id', sa.String(length=36), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('is_up', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['target_id'], ['health_targets.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_health_logs_target_checked', 'health_logs', ['target_id', 'checked_at'])
    op.create_index('idx_health_logs_checked_at', 'health_logs', ['checked_at'])

    # 6. alert_configs
    op.create_table(
        'alert_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('channel_type', sa.String(length=50), nullable=False),
        sa.Column('destination_url_encrypted', sa.Text(), nullable=False),
        sa.Column('notify_on_deployment_fail', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_on_health_fail', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 7. incidents
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('target_id', sa.String(length=36), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
        sa.Column('failure_reason', sa.Text(), nullable=False),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['target_id'], ['health_targets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_incidents_target_status', 'incidents', ['target_id', 'status'])


def downgrade() -> None:
    op.drop_table('incidents')
    op.drop_table('alert_configs')
    op.drop_table('health_logs')
    op.drop_table('health_targets')
    op.drop_table('deployments')
    op.drop_table('projects')
    op.drop_table('users')
