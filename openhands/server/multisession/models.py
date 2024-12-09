"""Data models for multi-session management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, Optional

class SessionState(Enum):
    """Possible states of a session."""
    INITIALIZING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()

@dataclass
class ResourceUsage:
    """Resource usage metrics for a session."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    disk_mb: float = 0.0
    container_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

@dataclass
class ResourceLimits:
    """Resource limits for sessions."""
    max_cpu_percent: float = 80.0
    max_memory_mb: float = 1024.0  # 1GB per session
    max_disk_mb: float = 2048.0    # 2GB per session
    max_containers: int = 3         # Max containers per session

@dataclass
class SessionLimits:
    """Limits for session management."""
    max_sessions_per_user: int = 5
    max_total_sessions: int = 20
    session_timeout_minutes: int = 60
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)

@dataclass
class SessionInfo:
    """Information about a session."""
    session_id: str
    user_id: str
    name: str
    state: SessionState
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    metadata: Dict[str, str] = field(default_factory=dict)
    error_message: Optional[str] = None

    def is_active(self) -> bool:
        """Check if the session is in an active state."""
        return self.state in {SessionState.RUNNING, SessionState.INITIALIZING}

    def is_stoppable(self) -> bool:
        """Check if the session can be stopped."""
        return self.state in {SessionState.RUNNING, SessionState.PAUSED}

    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_active = datetime.utcnow()

    def exceeds_resource_limits(self, limits: ResourceLimits) -> bool:
        """Check if session exceeds resource limits."""
        return (
            self.resource_usage.cpu_percent > limits.max_cpu_percent or
            self.resource_usage.memory_mb > limits.max_memory_mb or
            self.resource_usage.disk_mb > limits.max_disk_mb or
            self.resource_usage.container_count > limits.max_containers
        )