from enum import Enum
from typing import Dict, Set, Tuple, List, Optional
import logging

logger = logging.getLogger("pulseops.state_machines")


# ============================================================================
# 1. Deployment Lifecycle State Machine
# ============================================================================
class DeploymentStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"

    @classmethod
    def from_string(cls, val: Optional[str]) -> "DeploymentStatus":
        if not val:
            return cls.SUCCESS
        v = val.lower().strip()
        if v in ("success", "successful", "passed"):
            return cls.SUCCESS
        if v in ("failed", "failure", "error"):
            return cls.FAILURE
        if v in ("in_progress", "running", "building"):
            return cls.IN_PROGRESS
        if v in ("queued", "pending", "created"):
            return cls.QUEUED
        if v in ("canceled", "cancelled", "skipped"):
            return cls.CANCELLED
        return cls.SUCCESS


class DeploymentStateMachine:
    """
    Explicit, deterministic Deployment State Machine.
    Enforces forward-only lifecycle transitions and terminal state immutability.
    Guarantees out-of-order webhook delivery cannot overwrite terminal states.
    """

    # Directed Acyclic Graph of allowed state transitions
    _ALLOWED_TRANSITIONS: Dict[DeploymentStatus, Set[DeploymentStatus]] = {
        DeploymentStatus.QUEUED: {
            DeploymentStatus.QUEUED,       # Idempotent self-transition
            DeploymentStatus.IN_PROGRESS,
            DeploymentStatus.SUCCESS,
            DeploymentStatus.FAILURE,
            DeploymentStatus.CANCELLED,
        },
        DeploymentStatus.IN_PROGRESS: {
            DeploymentStatus.IN_PROGRESS,  # Idempotent self-transition
            DeploymentStatus.SUCCESS,
            DeploymentStatus.FAILURE,
            DeploymentStatus.CANCELLED,
        },
        # Terminal States: Cannot transition backwards to Queued or In_Progress
        DeploymentStatus.SUCCESS: {DeploymentStatus.SUCCESS},
        DeploymentStatus.FAILURE: {DeploymentStatus.FAILURE},
        DeploymentStatus.CANCELLED: {DeploymentStatus.CANCELLED},
    }

    _TERMINAL_STATES = {
        DeploymentStatus.SUCCESS,
        DeploymentStatus.FAILURE,
        DeploymentStatus.CANCELLED,
    }

    @classmethod
    def is_terminal(cls, status: DeploymentStatus) -> bool:
        return status in cls._TERMINAL_STATES

    @classmethod
    def can_transition(cls, from_status: DeploymentStatus, to_status: DeploymentStatus) -> bool:
        allowed = cls._ALLOWED_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    @classmethod
    def transition(
        cls,
        current_status: DeploymentStatus,
        incoming_status: DeploymentStatus,
    ) -> Tuple[DeploymentStatus, bool]:
        """
        Attempts state transition.
        Returns (resulting_status, did_transition).
        If incoming transition is invalid (e.g. out-of-order late arrival),
        preserves current state and returns (current_status, False).
        """
        if current_status == incoming_status:
            return current_status, False

        if cls.can_transition(current_status, incoming_status):
            logger.info(f"Deployment state transitioned: {current_status.value} -> {incoming_status.value}")
            return incoming_status, True

        logger.warning(
            f"Deployment invalid state transition rejected: {current_status.value} -> {incoming_status.value} "
            f"(Out-of-order webhook delivery detected; preserving {current_status.value})"
        )
        return current_status, False


# ============================================================================
# 2. Target Health State Machine
# ============================================================================
class TargetHealthStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"

    @classmethod
    def from_string(cls, val: Optional[str]) -> "TargetHealthStatus":
        if not val:
            return cls.UNKNOWN
        v = val.upper().strip()
        try:
            return cls(v)
        except ValueError:
            return cls.UNKNOWN


class HealthStateMachine:
    """
    Explicit Target Health & Outage State Machine.
    Enforces consecutive failure thresholding for flap prevention and
    manages incident creation/resolution lifecycle transitions deterministically.
    """

    @classmethod
    def evaluate_probe(
        cls,
        current_status: TargetHealthStatus,
        current_consecutive_failures: int,
        is_probe_successful: bool,
        has_open_incident: bool,
        threshold: int = 3,
    ) -> Tuple[TargetHealthStatus, int, bool, bool]:
        """
        Evaluates an HTTP health probe outcome against the state machine.

        Returns:
            new_status: TargetHealthStatus
            new_consecutive_failures: int
            should_open_incident: bool (True if transitioning to DOWN and no incident open)
            should_resolve_incident: bool (True if probe succeeded and an incident is open)
        """
        if is_probe_successful:
            new_consecutive_failures = 0
            new_status = TargetHealthStatus.UP
            # If an open incident exists, recovery is triggered regardless of prev status
            should_resolve_incident = has_open_incident
            should_open_incident = False
            return new_status, new_consecutive_failures, should_open_incident, should_resolve_incident

        # Probe failed
        new_consecutive_failures = current_consecutive_failures + 1

        if new_consecutive_failures >= threshold:
            new_status = TargetHealthStatus.DOWN
            # Only open incident if one is not already open
            should_open_incident = not has_open_incident
            should_resolve_incident = False
        else:
            new_status = TargetHealthStatus.DEGRADED
            should_open_incident = False
            should_resolve_incident = False

        return new_status, new_consecutive_failures, should_open_incident, should_resolve_incident


# ============================================================================
# 3. Incident Lifecycle State Machine
# ============================================================================
class IncidentStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class IncidentStateMachine:
    """
    Explicit Incident Lifecycle State Machine.
    Transitions: OPEN -> RESOLVED (Terminal).
    """

    @classmethod
    def can_resolve(cls, current_status: IncidentStatus) -> bool:
        return current_status == IncidentStatus.OPEN

    @classmethod
    def resolve(cls, current_status: IncidentStatus) -> Tuple[IncidentStatus, bool]:
        """
        Transitions incident to resolved if currently open.
        Returns (new_status, did_transition).
        """
        if current_status == IncidentStatus.OPEN:
            return IncidentStatus.RESOLVED, True
        return current_status, False


# ============================================================================
# 4. Overall Project Health Severity Lattice (State Reducer)
# ============================================================================
class ProjectHealthReducer:
    """
    Monotonic severity lattice for reducing multiple target states into an
    overall project health indicator:
        DOWN (Priority 3) > DEGRADED (Priority 2) > UNKNOWN (Priority 1) > UP (Priority 0)
    """

    _SEVERITY_ORDER = {
        TargetHealthStatus.DOWN: 3,
        TargetHealthStatus.DEGRADED: 2,
        TargetHealthStatus.UNKNOWN: 1,
        TargetHealthStatus.UP: 0,
    }

    @classmethod
    def reduce_health(cls, statuses: List[TargetHealthStatus]) -> TargetHealthStatus:
        if not statuses:
            return TargetHealthStatus.UNKNOWN

        highest_status = TargetHealthStatus.UP
        highest_severity = -1

        for s in statuses:
            severity = cls._SEVERITY_ORDER.get(s, 1)
            if severity > highest_severity:
                highest_severity = severity
                highest_status = s

        return highest_status
