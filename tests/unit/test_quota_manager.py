"""Tests for resource quota management."""

import asyncio
from datetime import datetime, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.server.monitoring.quota_manager import (
    AutoScaler,
    QuotaLimits,
    QuotaManager,
    QuotaUsage
)
from openhands.server.monitoring.resource_monitor import MonitoringManager
from openhands.server.multisession.models import ResourceUsage, SessionInfo, SessionState

@pytest.fixture
def session_info():
    return SessionInfo(
        session_id="test_session",
        user_id="test_user",
        name="Test Session",
        state=SessionState.RUNNING,
        created_at=datetime.utcnow(),
        last_active=datetime.utcnow(),
        resource_usage=ResourceUsage(
            cpu_percent=0.0,
            memory_mb=0.0,
            disk_mb=0.0,
            container_count=0,
            last_updated=datetime.utcnow()
        ),
        metadata={}
    )

@pytest.fixture
def monitoring_manager():
    manager = MagicMock(spec=MonitoringManager)
    manager.resource_monitor = MagicMock()
    return manager

@pytest.fixture
def quota_manager(monitoring_manager):
    return QuotaManager(monitoring_manager)

@pytest.fixture
def auto_scaler(monitoring_manager, quota_manager):
    return AutoScaler(monitoring_manager, quota_manager)

@pytest.mark.asyncio
async def test_quota_enforcement(session_info, monitoring_manager, quota_manager):
    """Test basic quota enforcement."""
    # Set up mock resource usage
    monitoring_manager.resource_monitor.get_current_usage.return_value = ResourceUsage(
        cpu_percent=250.0,  # Exceeds normal limit
        memory_mb=1024.0,
        disk_mb=1024.0,
        container_count=2,
        last_updated=datetime.utcnow()
    )
    
    # Set up violation handler
    violations = []
    async def handler(session_id, violation_type, details):
        violations.append((session_id, violation_type, details))
    
    quota_manager.register_violation_handler(handler)
    
    # Set quota and start enforcement
    quota_manager.set_quota(session_info.session_id, QuotaLimits())
    await quota_manager.start()
    
    # Wait for enforcement check
    await asyncio.sleep(6)
    
    # Verify violations were detected
    assert len(violations) > 0
    assert any(v[1] == 'cpu_burst_limit' for v in violations)
    
    await quota_manager.stop()

@pytest.mark.asyncio
async def test_burst_allowance(session_info, monitoring_manager, quota_manager):
    """Test burst resource allowance."""
    # Set up mock resource usage within burst limits
    monitoring_manager.resource_monitor.get_current_usage.return_value = ResourceUsage(
        cpu_percent=250.0,  # Above normal but within burst
        memory_mb=2500.0,   # Above normal but within burst
        disk_mb=1024.0,
        container_count=2,
        last_updated=datetime.utcnow()
    )
    
    violations = []
    async def handler(session_id, violation_type, details):
        violations.append((session_id, violation_type, details))
    
    quota_manager.register_violation_handler(handler)
    
    # Set quota and start enforcement
    quota_manager.set_quota(session_info.session_id, QuotaLimits())
    await quota_manager.start()
    
    # Wait for initial check
    await asyncio.sleep(6)
    
    # Should not have violations yet (within burst period)
    assert len(violations) == 0
    
    # Simulate burst duration exceeded
    usage = quota_manager.get_usage(session_info.session_id)
    usage.burst_start = datetime.utcnow() - timedelta(seconds=301)
    
    # Wait for next check
    await asyncio.sleep(6)
    
    # Should now have burst duration violations
    assert len(violations) > 0
    assert any(v[1] == 'cpu_burst_duration' for v in violations)
    assert any(v[1] == 'memory_burst_duration' for v in violations)
    
    await quota_manager.stop()

@pytest.mark.asyncio
async def test_auto_scaling(session_info, monitoring_manager, quota_manager, auto_scaler):
    """Test automatic resource scaling."""
    # Set up mock resource usage near scale-up threshold
    monitoring_manager.resource_monitor.get_current_usage.return_value = ResourceUsage(
        cpu_percent=180.0,  # 90% of default limit
        memory_mb=1638.4,   # 80% of default limit
        disk_mb=1024.0,
        container_count=2,
        last_updated=datetime.utcnow()
    )
    
    # Set initial quota
    quota_manager.set_quota(session_info.session_id, QuotaLimits())
    initial_quota = quota_manager.get_quota(session_info.session_id)
    
    # Start auto-scaler
    await auto_scaler.start()
    
    # Wait for scaling check
    await asyncio.sleep(61)
    
    # Verify scale-up occurred
    new_quota = quota_manager.get_quota(session_info.session_id)
    assert new_quota.max_cpu_percent > initial_quota.max_cpu_percent
    assert new_quota.max_memory_mb > initial_quota.max_memory_mb
    
    # Change usage to trigger scale-down
    monitoring_manager.resource_monitor.get_current_usage.return_value = ResourceUsage(
        cpu_percent=40.0,   # 20% of new limit
        memory_mb=409.6,    # 20% of new limit
        disk_mb=1024.0,
        container_count=2,
        last_updated=datetime.utcnow()
    )
    
    # Clear cooldown
    auto_scaler._last_scale.clear()
    
    # Wait for next check
    await asyncio.sleep(61)
    
    # Verify scale-down occurred
    final_quota = quota_manager.get_quota(session_info.session_id)
    assert final_quota.max_cpu_percent < new_quota.max_cpu_percent
    assert final_quota.max_memory_mb < new_quota.max_memory_mb
    
    await auto_scaler.stop()

@pytest.mark.asyncio
async def test_quota_removal(session_info, monitoring_manager, quota_manager):
    """Test quota removal."""
    quota_manager.set_quota(session_info.session_id, QuotaLimits())
    assert quota_manager.get_quota(session_info.session_id) is not None
    
    quota_manager.remove_quota(session_info.session_id)
    assert quota_manager.get_quota(session_info.session_id) is None
    assert quota_manager.get_usage(session_info.session_id) is None

@pytest.mark.asyncio
async def test_scaling_cooldown(session_info, monitoring_manager, quota_manager, auto_scaler):
    """Test scaling cooldown period."""
    # Set up mock resource usage
    monitoring_manager.resource_monitor.get_current_usage.return_value = ResourceUsage(
        cpu_percent=180.0,  # 90% of default limit
        memory_mb=1638.4,   # 80% of default limit
        disk_mb=1024.0,
        container_count=2,
        last_updated=datetime.utcnow()
    )
    
    # Set quota and start auto-scaler
    quota_manager.set_quota(session_info.session_id, QuotaLimits())
    await auto_scaler.start()
    
    # Wait for initial scale-up
    await asyncio.sleep(61)
    scaled_quota = quota_manager.get_quota(session_info.session_id)
    
    # Change usage to trigger scale-down (but should be prevented by cooldown)
    monitoring_manager.resource_monitor.get_current_usage.return_value = ResourceUsage(
        cpu_percent=40.0,
        memory_mb=409.6,
        disk_mb=1024.0,
        container_count=2,
        last_updated=datetime.utcnow()
    )
    
    # Wait for next check
    await asyncio.sleep(61)
    
    # Verify no scaling occurred during cooldown
    current_quota = quota_manager.get_quota(session_info.session_id)
    assert current_quota.max_cpu_percent == scaled_quota.max_cpu_percent
    assert current_quota.max_memory_mb == scaled_quota.max_memory_mb
    
    await auto_scaler.stop()