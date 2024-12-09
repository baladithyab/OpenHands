"""Tests for resource monitoring functionality."""

import asyncio
from datetime import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.server.monitoring.resource_monitor import (
    ResourceMonitor,
    SystemMonitor,
    MonitoringManager
)
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
def mock_docker_container():
    container = MagicMock()
    container.id = "test_container"
    container.stats.return_value = {
        'cpu_stats': {
            'cpu_usage': {
                'total_usage': 100000000
            },
            'system_cpu_usage': 1000000000
        },
        'precpu_stats': {
            'cpu_usage': {
                'total_usage': 90000000
            },
            'system_cpu_usage': 990000000
        },
        'memory_stats': {
            'usage': 104857600  # 100MB
        }
    }
    return container

@pytest.fixture
def mock_docker_client(mock_docker_container):
    client = MagicMock()
    client.containers.list.return_value = [mock_docker_container]
    client.info.return_value = {
        'ContainersRunning': 1,
        'Containers': 2,
        'Images': 10
    }
    return client

@pytest.mark.asyncio
async def test_resource_monitor(session_info, mock_docker_client):
    """Test resource monitoring for a session."""
    with patch('docker.from_env', return_value=mock_docker_client):
        monitor = ResourceMonitor()
        
        # Start monitoring
        await monitor.start_monitoring(session_info)
        
        # Wait for stats update
        await asyncio.sleep(6)
        
        # Get current usage
        usage = monitor.get_current_usage(session_info.session_id)
        assert usage is not None
        assert usage.cpu_percent > 0
        assert usage.memory_mb > 0
        assert usage.container_count == 1
        
        # Stop monitoring
        await monitor.stop_monitoring(session_info.session_id)
        assert session_info.session_id not in monitor._monitoring_tasks

@pytest.mark.asyncio
async def test_system_monitor(mock_docker_client):
    """Test system resource monitoring."""
    with patch('docker.from_env', return_value=mock_docker_client), \
         patch('psutil.cpu_percent', return_value=50.0), \
         patch('psutil.cpu_count', return_value=4), \
         patch('psutil.virtual_memory', return_value=MagicMock(
             total=8589934592,  # 8GB
             used=4294967296,   # 4GB
             percent=50.0
         )), \
         patch('psutil.disk_usage', return_value=MagicMock(
             total=107374182400,  # 100GB
             used=53687091200,   # 50GB
             percent=50.0
         )):
        monitor = SystemMonitor()
        stats = await monitor.get_system_resources()
        
        assert stats['cpu']['percent'] == 50.0
        assert stats['cpu']['count'] == 4
        assert stats['memory']['percent'] == 50.0
        assert stats['disk']['percent'] == 50.0
        assert stats['docker']['containers_running'] == 1
        assert stats['docker']['containers_total'] == 2
        assert stats['docker']['images'] == 10

@pytest.mark.asyncio
async def test_monitoring_manager(session_info, mock_docker_client):
    """Test monitoring manager functionality."""
    with patch('docker.from_env', return_value=mock_docker_client):
        manager = MonitoringManager()
        
        # Start manager
        await manager.start()
        
        # Register session
        await manager.register_session(session_info)
        
        # Add client
        queue = await manager.add_client(session_info.session_id)
        
        # Wait for update
        try:
            message = await asyncio.wait_for(queue.get(), timeout=7)
            data = eval(message)  # Safe since we control the test data
            
            assert data['type'] == 'resource_update'
            assert data['data']['session']['id'] == session_info.session_id
            assert 'cpu' in data['data']['system']
            
        except asyncio.TimeoutError:
            pytest.fail("Did not receive monitoring update")
        
        # Remove client
        await manager.remove_client(session_info.session_id, queue)
        
        # Unregister session
        await manager.unregister_session(session_info.session_id)
        
        # Stop manager
        await manager.stop()

@pytest.mark.asyncio
async def test_monitoring_error_handling(session_info):
    """Test error handling in monitoring."""
    with patch('docker.from_env', side_effect=Exception("Docker error")):
        monitor = ResourceMonitor()
        
        # Should not raise exception
        await monitor.start_monitoring(session_info)
        
        # Wait for error handling
        await asyncio.sleep(2)
        
        # Should return None on error
        usage = monitor.get_current_usage(session_info.session_id)
        assert usage is None
        
        # Should not raise exception
        await monitor.stop_monitoring(session_info.session_id)