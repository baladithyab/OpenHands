"""Tests for multi-session functionality."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.core.config import AppConfig
from openhands.server.multisession.manager import (
    MultiSessionManager,
    ResourceLimitError,
    SessionLimitError
)
from openhands.server.multisession.models import (
    ResourceLimits,
    SessionInfo,
    SessionLimits,
    SessionState
)

@pytest.fixture
def app_config():
    return MagicMock(spec=AppConfig)

@pytest.fixture
def file_store():
    return MagicMock()

@pytest.fixture
def socket_server():
    server = AsyncMock()
    server.manager = MagicMock()
    server.manager.redis = MagicMock()
    return server

@pytest.fixture
def session_limits():
    return SessionLimits(
        max_sessions_per_user=2,
        max_total_sessions=5,
        session_timeout_minutes=30,
        resource_limits=ResourceLimits(
            max_cpu_percent=50.0,
            max_memory_mb=512.0,
            max_disk_mb=1024.0,
            max_containers=2
        )
    )

@pytest.mark.asyncio
async def test_create_session(app_config, file_store, socket_server, session_limits):
    """Test creating a new session."""
    manager = MultiSessionManager(
        socket_server,
        app_config,
        file_store,
        session_limits
    )
    
    # Create a session
    session_info = await manager.create_session(
        user_id="test_user",
        name="Test Session",
        metadata={"purpose": "testing"}
    )
    
    assert session_info.session_id in manager.sessions
    assert session_info.user_id == "test_user"
    assert session_info.name == "Test Session"
    assert session_info.state == SessionState.RUNNING
    assert session_info.metadata["purpose"] == "testing"
    
    # Verify session tracking
    assert len(manager.user_sessions["test_user"]) == 1
    assert session_info.session_id in manager.session_managers

@pytest.mark.asyncio
async def test_session_limits(app_config, file_store, socket_server, session_limits):
    """Test session limit enforcement."""
    manager = MultiSessionManager(
        socket_server,
        app_config,
        file_store,
        session_limits
    )
    
    # Create maximum allowed sessions for a user
    for i in range(session_limits.max_sessions_per_user):
        await manager.create_session(
            user_id="test_user",
            name=f"Session {i}"
        )
    
    # Try to create one more session
    with pytest.raises(SessionLimitError):
        await manager.create_session(
            user_id="test_user",
            name="Extra Session"
        )

@pytest.mark.asyncio
async def test_stop_session(app_config, file_store, socket_server, session_limits):
    """Test stopping a session."""
    manager = MultiSessionManager(
        socket_server,
        app_config,
        file_store,
        session_limits
    )
    
    # Create and then stop a session
    session_info = await manager.create_session(
        user_id="test_user",
        name="Test Session"
    )
    
    await manager.stop_session(session_info.session_id)
    
    # Verify session cleanup
    assert session_info.session_id not in manager.sessions
    assert session_info.session_id not in manager.session_managers
    assert session_info.session_id not in manager.user_sessions["test_user"]

@pytest.mark.asyncio
async def test_session_timeout(app_config, file_store, socket_server):
    """Test session timeout cleanup."""
    # Use a short timeout for testing
    limits = SessionLimits(session_timeout_minutes=1)
    
    manager = MultiSessionManager(
        socket_server,
        app_config,
        file_store,
        limits
    )
    
    # Create a session
    session_info = await manager.create_session(
        user_id="test_user",
        name="Test Session"
    )
    
    # Modify last_active to simulate timeout
    session_info.last_active = datetime.utcnow() - timedelta(minutes=2)
    
    # Run cleanup
    await manager._cleanup_loop()
    
    # Verify session was cleaned up
    assert session_info.session_id not in manager.sessions

@pytest.mark.asyncio
async def test_resource_monitoring(app_config, file_store, socket_server, session_limits):
    """Test resource usage monitoring."""
    manager = MultiSessionManager(
        socket_server,
        app_config,
        file_store,
        session_limits
    )
    
    # Create a session
    session_info = await manager.create_session(
        user_id="test_user",
        name="Test Session"
    )
    
    # Simulate high resource usage
    session_info.resource_usage.cpu_percent = 90.0  # Exceeds limit
    
    # Run monitoring
    await manager._monitor_loop()
    
    # Verify session was flagged
    assert session_info.exceeds_resource_limits(session_limits.resource_limits)

@pytest.mark.asyncio
async def test_pause_resume_session(app_config, file_store, socket_server, session_limits):
    """Test pausing and resuming a session."""
    manager = MultiSessionManager(
        socket_server,
        app_config,
        file_store,
        session_limits
    )
    
    # Create a session
    session_info = await manager.create_session(
        user_id="test_user",
        name="Test Session"
    )
    
    # Pause session
    await manager.pause_session(session_info.session_id)
    assert session_info.state == SessionState.PAUSED
    
    # Resume session
    await manager.resume_session(session_info.session_id)
    assert session_info.state == SessionState.RUNNING

@pytest.mark.asyncio
async def test_list_user_sessions(app_config, file_store, socket_server, session_limits):
    """Test listing user sessions."""
    manager = MultiSessionManager(
        socket_server,
        app_config,
        file_store,
        session_limits
    )
    
    # Create multiple sessions for different users
    session1 = await manager.create_session(
        user_id="user1",
        name="User1 Session1"
    )
    session2 = await manager.create_session(
        user_id="user1",
        name="User1 Session2"
    )
    session3 = await manager.create_session(
        user_id="user2",
        name="User2 Session"
    )
    
    # List sessions for user1
    user1_sessions = manager.list_user_sessions("user1")
    assert len(user1_sessions) == 2
    assert all(s.user_id == "user1" for s in user1_sessions)
    
    # List sessions for user2
    user2_sessions = manager.list_user_sessions("user2")
    assert len(user2_sessions) == 1
    assert user2_sessions[0].user_id == "user2"