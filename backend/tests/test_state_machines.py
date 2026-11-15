import pytest
from app.core.state_machines import (
    DeploymentStatus,
    DeploymentStateMachine,
    TargetHealthStatus,
    HealthStateMachine,
    IncidentStatus,
    IncidentStateMachine,
    ProjectHealthReducer,
)


# ============================================================================
# 1. Deployment State Machine Tests
# ============================================================================
def test_deployment_forward_lifecycle():
    # Queued -> In Progress
    status, transitioned = DeploymentStateMachine.transition(
        DeploymentStatus.QUEUED, DeploymentStatus.IN_PROGRESS
    )
    assert transitioned is True
    assert status == DeploymentStatus.IN_PROGRESS

    # In Progress -> Success
    status, transitioned = DeploymentStateMachine.transition(
        DeploymentStatus.IN_PROGRESS, DeploymentStatus.SUCCESS
    )
    assert transitioned is True
    assert status == DeploymentStatus.SUCCESS
    assert DeploymentStateMachine.is_terminal(status) is True


def test_deployment_out_of_order_webhook_protection():
    # Late in_progress webhook arriving after success must be REJECTED
    status, transitioned = DeploymentStateMachine.transition(
        DeploymentStatus.SUCCESS, DeploymentStatus.IN_PROGRESS
    )
    assert transitioned is False
    assert status == DeploymentStatus.SUCCESS  # Preserves terminal state

    # Late queued webhook arriving after failure must be REJECTED
    status, transitioned = DeploymentStateMachine.transition(
        DeploymentStatus.FAILURE, DeploymentStatus.QUEUED
    )
    assert transitioned is False
    assert status == DeploymentStatus.FAILURE

    # Idempotent re-delivery of success
    status, transitioned = DeploymentStateMachine.transition(
        DeploymentStatus.SUCCESS, DeploymentStatus.SUCCESS
    )
    assert transitioned is False
    assert status == DeploymentStatus.SUCCESS


# ============================================================================
# 2. Health & Outage State Machine Tests
# ============================================================================
def test_health_state_machine_evaluations():
    threshold = 3

    # Initial state: UNKNOWN. Probe fails once.
    status, failures, open_inc, resolve_inc = HealthStateMachine.evaluate_probe(
        current_status=TargetHealthStatus.UNKNOWN,
        current_consecutive_failures=0,
        is_probe_successful=False,
        has_open_incident=False,
        threshold=threshold,
    )
    assert status == TargetHealthStatus.DEGRADED
    assert failures == 1
    assert open_inc is False
    assert resolve_inc is False

    # Second failure
    status, failures, open_inc, resolve_inc = HealthStateMachine.evaluate_probe(
        current_status=status,
        current_consecutive_failures=failures,
        is_probe_successful=False,
        has_open_incident=False,
        threshold=threshold,
    )
    assert status == TargetHealthStatus.DEGRADED
    assert failures == 2
    assert open_inc is False
    assert resolve_inc is False

    # Third failure -> Threshold reached! Open incident!
    status, failures, open_inc, resolve_inc = HealthStateMachine.evaluate_probe(
        current_status=status,
        current_consecutive_failures=failures,
        is_probe_successful=False,
        has_open_incident=False,
        threshold=threshold,
    )
    assert status == TargetHealthStatus.DOWN
    assert failures == 3
    assert open_inc is True  # Must trigger incident opening
    assert resolve_inc is False

    # Fourth failure while already DOWN with open incident -> Do NOT open duplicate incident
    status, failures, open_inc, resolve_inc = HealthStateMachine.evaluate_probe(
        current_status=TargetHealthStatus.DOWN,
        current_consecutive_failures=failures,
        is_probe_successful=False,
        has_open_incident=True,  # Incident is already open
        threshold=threshold,
    )
    assert status == TargetHealthStatus.DOWN
    assert failures == 4
    assert open_inc is False  # Invariant: No duplicate incidents
    assert resolve_inc is False

    # Successful recovery probe -> Reset failures to 0, resolve incident
    status, failures, open_inc, resolve_inc = HealthStateMachine.evaluate_probe(
        current_status=TargetHealthStatus.DOWN,
        current_consecutive_failures=failures,
        is_probe_successful=True,
        has_open_incident=True,
        threshold=threshold,
    )
    assert status == TargetHealthStatus.UP
    assert failures == 0
    assert open_inc is False
    assert resolve_inc is True  # Must trigger incident resolution


# ============================================================================
# 3. Incident State Machine Tests
# ============================================================================
def test_incident_state_machine_resolution():
    assert IncidentStateMachine.can_resolve(IncidentStatus.OPEN) is True
    assert IncidentStateMachine.can_resolve(IncidentStatus.RESOLVED) is False

    new_status, did_trans = IncidentStateMachine.resolve(IncidentStatus.OPEN)
    assert did_trans is True
    assert new_status == IncidentStatus.RESOLVED

    # Cannot resolve already resolved incident
    new_status2, did_trans2 = IncidentStateMachine.resolve(IncidentStatus.RESOLVED)
    assert did_trans2 is False
    assert new_status2 == IncidentStatus.RESOLVED


# ============================================================================
# 4. Project Health Severity Lattice Tests
# ============================================================================
def test_project_health_severity_lattice():
    # Empty
    assert ProjectHealthReducer.reduce_health([]) == TargetHealthStatus.UNKNOWN

    # All UP
    assert ProjectHealthReducer.reduce_health([
        TargetHealthStatus.UP,
        TargetHealthStatus.UP
    ]) == TargetHealthStatus.UP

    # One DEGRADED dominates UP
    assert ProjectHealthReducer.reduce_health([
        TargetHealthStatus.UP,
        TargetHealthStatus.DEGRADED,
        TargetHealthStatus.UP
    ]) == TargetHealthStatus.DEGRADED

    # One DOWN dominates DEGRADED and UP
    assert ProjectHealthReducer.reduce_health([
        TargetHealthStatus.UP,
        TargetHealthStatus.DEGRADED,
        TargetHealthStatus.DOWN,
        TargetHealthStatus.UP
    ]) == TargetHealthStatus.DOWN
