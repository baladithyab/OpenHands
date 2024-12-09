"""Resource quota management for OpenHands sessions."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from openhands.core.logger import openhands_logger as logger
from openhands.server.monitoring.resource_monitor import MonitoringManager
from openhands.server.multisession.models import SessionInfo, SessionState

@dataclass
class QuotaLimits:
    """Resource quota limits for a session."""
    max_cpu_percent: float = 200.0  # 200% = 2 cores
    max_memory_mb: float = 2048.0   # 2GB
    max_disk_mb: float = 5120.0     # 5GB
    max_containers: int = 5
    burst_cpu_percent: float = 300.0  # Allowed burst CPU (3 cores)
    burst_memory_mb: float = 3072.0   # Allowed burst memory (3GB)
    burst_duration_seconds: int = 300  # Max burst duration (5 minutes)

@dataclass
class QuotaUsage:
    """Current quota usage for a session."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    disk_mb: float = 0.0
    container_count: int = 0
    burst_start: Optional[datetime] = None
    in_burst: bool = False

class QuotaManager:
    """Manages resource quotas for sessions."""

    def __init__(self, monitoring_manager: MonitoringManager):
        """Initialize the quota manager.
        
        Args:
            monitoring_manager: Manager for resource monitoring
        """
        self.monitoring = monitoring_manager
        self._quotas: Dict[str, QuotaLimits] = {}
        self._usage: Dict[str, QuotaUsage] = {}
        self._enforcement_task: Optional[asyncio.Task] = None
        self._violation_handlers: List[callable] = []

    async def start(self) -> None:
        """Start quota enforcement."""
        self._enforcement_task = asyncio.create_task(self._enforce_quotas())
        logger.info("Started quota manager")

    async def stop(self) -> None:
        """Stop quota enforcement."""
        if self._enforcement_task:
            self._enforcement_task.cancel()
            try:
                await self._enforcement_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped quota manager")

    def register_violation_handler(self, handler: callable) -> None:
        """Register a handler for quota violations.
        
        Args:
            handler: Async function(session_id: str, violation_type: str, details: dict)
        """
        self._violation_handlers.append(handler)

    def set_quota(self, session_id: str, quota: QuotaLimits) -> None:
        """Set quota limits for a session.
        
        Args:
            session_id: ID of the session
            quota: Quota limits to set
        """
        self._quotas[session_id] = quota
        self._usage[session_id] = QuotaUsage()
        logger.info(f"Set quota for session {session_id}")

    def remove_quota(self, session_id: str) -> None:
        """Remove quota for a session.
        
        Args:
            session_id: ID of the session
        """
        self._quotas.pop(session_id, None)
        self._usage.pop(session_id, None)
        logger.info(f"Removed quota for session {session_id}")

    def get_quota(self, session_id: str) -> Optional[QuotaLimits]:
        """Get quota limits for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Quota limits or None if not set
        """
        return self._quotas.get(session_id)

    def get_usage(self, session_id: str) -> Optional[QuotaUsage]:
        """Get current quota usage for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Current usage or None if not tracked
        """
        return self._usage.get(session_id)

    async def _enforce_quotas(self) -> None:
        """Enforce quotas for all sessions."""
        while True:
            try:
                for session_id, quota in self._quotas.items():
                    usage = self._usage[session_id]
                    
                    # Get current resource usage
                    current = self.monitoring.resource_monitor.get_current_usage(session_id)
                    if not current:
                        continue
                    
                    # Update usage tracking
                    usage.cpu_percent = current.cpu_percent
                    usage.memory_mb = current.memory_mb
                    usage.disk_mb = current.disk_mb
                    usage.container_count = current.container_count
                    
                    # Check for violations
                    violations = await self._check_violations(session_id, quota, usage)
                    
                    # Handle violations
                    if violations:
                        await self._handle_violations(session_id, violations)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error enforcing quotas: {e}")
                await asyncio.sleep(10)

    async def _check_violations(
        self,
        session_id: str,
        quota: QuotaLimits,
        usage: QuotaUsage
    ) -> List[Tuple[str, dict]]:
        """Check for quota violations.
        
        Args:
            session_id: ID of the session
            quota: Quota limits
            usage: Current usage
            
        Returns:
            List of (violation_type, details) tuples
        """
        violations = []
        
        # Check container count
        if usage.container_count > quota.max_containers:
            violations.append((
                'container_limit',
                {
                    'current': usage.container_count,
                    'limit': quota.max_containers
                }
            ))
        
        # Check disk usage
        if usage.disk_mb > quota.max_disk_mb:
            violations.append((
                'disk_limit',
                {
                    'current_mb': usage.disk_mb,
                    'limit_mb': quota.max_disk_mb
                }
            ))
        
        # Check CPU and memory with burst allowance
        now = datetime.utcnow()
        
        # CPU check
        if usage.cpu_percent > quota.max_cpu_percent:
            if usage.cpu_percent <= quota.burst_cpu_percent:
                # Within burst limits
                if not usage.in_burst:
                    usage.burst_start = now
                    usage.in_burst = True
                elif (now - usage.burst_start) > timedelta(seconds=quota.burst_duration_seconds):
                    # Burst duration exceeded
                    violations.append((
                        'cpu_burst_duration',
                        {
                            'current_percent': usage.cpu_percent,
                            'limit_percent': quota.max_cpu_percent,
                            'burst_duration_seconds': (now - usage.burst_start).total_seconds()
                        }
                    ))
            else:
                # Exceeds burst limits
                violations.append((
                    'cpu_burst_limit',
                    {
                        'current_percent': usage.cpu_percent,
                        'burst_limit_percent': quota.burst_cpu_percent
                    }
                ))
        else:
            # Reset burst tracking
            usage.in_burst = False
            usage.burst_start = None
        
        # Memory check
        if usage.memory_mb > quota.max_memory_mb:
            if usage.memory_mb <= quota.burst_memory_mb:
                # Within burst limits
                if not usage.in_burst:
                    usage.burst_start = now
                    usage.in_burst = True
                elif (now - usage.burst_start) > timedelta(seconds=quota.burst_duration_seconds):
                    # Burst duration exceeded
                    violations.append((
                        'memory_burst_duration',
                        {
                            'current_mb': usage.memory_mb,
                            'limit_mb': quota.max_memory_mb,
                            'burst_duration_seconds': (now - usage.burst_start).total_seconds()
                        }
                    ))
            else:
                # Exceeds burst limits
                violations.append((
                    'memory_burst_limit',
                    {
                        'current_mb': usage.memory_mb,
                        'burst_limit_mb': quota.burst_memory_mb
                    }
                ))
        else:
            # Reset burst tracking if not in CPU burst
            if not usage.cpu_percent > quota.max_cpu_percent:
                usage.in_burst = False
                usage.burst_start = None
        
        return violations

    async def _handle_violations(
        self,
        session_id: str,
        violations: List[Tuple[str, dict]]
    ) -> None:
        """Handle quota violations.
        
        Args:
            session_id: ID of the session
            violations: List of violations
        """
        for violation_type, details in violations:
            # Log violation
            logger.warning(
                f"Quota violation in session {session_id}: {violation_type}",
                extra={'details': details}
            )
            
            # Notify handlers
            for handler in self._violation_handlers:
                try:
                    await handler(session_id, violation_type, details)
                except Exception as e:
                    logger.error(f"Error in violation handler: {e}")

class AutoScaler:
    """Automatic resource scaling for sessions."""

    def __init__(
        self,
        monitoring_manager: MonitoringManager,
        quota_manager: QuotaManager
    ):
        """Initialize the auto-scaler.
        
        Args:
            monitoring_manager: Manager for resource monitoring
            quota_manager: Manager for quota enforcement
        """
        self.monitoring = monitoring_manager
        self.quota_manager = quota_manager
        self._scaling_task: Optional[asyncio.Task] = None
        self._scale_up_threshold = 0.8  # 80% of quota
        self._scale_down_threshold = 0.3  # 30% of quota
        self._cooldown_minutes = 5
        self._last_scale: Dict[str, datetime] = {}

    async def start(self) -> None:
        """Start auto-scaling."""
        self._scaling_task = asyncio.create_task(self._check_scaling())
        logger.info("Started auto-scaler")

    async def stop(self) -> None:
        """Stop auto-scaling."""
        if self._scaling_task:
            self._scaling_task.cancel()
            try:
                await self._scaling_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped auto-scaler")

    async def _check_scaling(self) -> None:
        """Check and apply auto-scaling."""
        while True:
            try:
                now = datetime.utcnow()
                
                for session_id, quota in self.quota_manager._quotas.items():
                    # Skip if in cooldown
                    if session_id in self._last_scale:
                        cooldown_end = self._last_scale[session_id] + timedelta(
                            minutes=self._cooldown_minutes
                        )
                        if now < cooldown_end:
                            continue
                    
                    # Get current usage
                    usage = self.quota_manager.get_usage(session_id)
                    if not usage:
                        continue
                    
                    # Check CPU utilization
                    cpu_util = usage.cpu_percent / quota.max_cpu_percent
                    memory_util = usage.memory_mb / quota.max_memory_mb
                    
                    # Scale up if needed
                    if cpu_util > self._scale_up_threshold or \
                       memory_util > self._scale_up_threshold:
                        await self._scale_up(session_id, quota, usage)
                        self._last_scale[session_id] = now
                    
                    # Scale down if possible
                    elif cpu_util < self._scale_down_threshold and \
                         memory_util < self._scale_down_threshold:
                        await self._scale_down(session_id, quota, usage)
                        self._last_scale[session_id] = now
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-scaling: {e}")
                await asyncio.sleep(60)

    async def _scale_up(
        self,
        session_id: str,
        quota: QuotaLimits,
        usage: QuotaUsage
    ) -> None:
        """Scale up resources for a session.
        
        Args:
            session_id: ID of the session
            quota: Current quota limits
            usage: Current usage
        """
        # Calculate new limits
        new_quota = QuotaLimits(
            max_cpu_percent=min(quota.max_cpu_percent * 1.5, quota.burst_cpu_percent),
            max_memory_mb=min(quota.max_memory_mb * 1.5, quota.burst_memory_mb),
            max_disk_mb=quota.max_disk_mb,
            max_containers=quota.max_containers + 1,
            burst_cpu_percent=quota.burst_cpu_percent,
            burst_memory_mb=quota.burst_memory_mb,
            burst_duration_seconds=quota.burst_duration_seconds
        )
        
        # Apply new quota
        self.quota_manager.set_quota(session_id, new_quota)
        logger.info(f"Scaled up session {session_id}")

    async def _scale_down(
        self,
        session_id: str,
        quota: QuotaLimits,
        usage: QuotaUsage
    ) -> None:
        """Scale down resources for a session.
        
        Args:
            session_id: ID of the session
            quota: Current quota limits
            usage: Current usage
        """
        # Calculate new limits
        new_quota = QuotaLimits(
            max_cpu_percent=max(quota.max_cpu_percent * 0.7, 100.0),
            max_memory_mb=max(quota.max_memory_mb * 0.7, 1024.0),
            max_disk_mb=quota.max_disk_mb,
            max_containers=max(quota.max_containers - 1, 1),
            burst_cpu_percent=quota.burst_cpu_percent,
            burst_memory_mb=quota.burst_memory_mb,
            burst_duration_seconds=quota.burst_duration_seconds
        )
        
        # Apply new quota
        self.quota_manager.set_quota(session_id, new_quota)
        logger.info(f"Scaled down session {session_id}")