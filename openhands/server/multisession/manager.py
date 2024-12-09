"""Multi-session manager for OpenHands."""

import asyncio
from datetime import datetime, timedelta
import uuid
from typing import Dict, List, Optional

import socketio
from openhands.core.config import AppConfig
from openhands.core.logger import openhands_logger as logger
from openhands.server.multisession.models import (
    ResourceLimits,
    SessionInfo,
    SessionLimits,
    SessionState
)
from openhands.server.session.manager import SessionManager
from openhands.storage.files import FileStore

class MultiSessionError(Exception):
    """Base exception for multi-session errors."""
    pass

class ResourceLimitError(MultiSessionError):
    """Raised when resource limits are exceeded."""
    pass

class SessionLimitError(MultiSessionError):
    """Raised when session limits are exceeded."""
    pass

class MultiSessionManager:
    """Manages multiple concurrent OpenHands sessions."""

    def __init__(
        self,
        sio: socketio.AsyncServer,
        config: AppConfig,
        file_store: FileStore,
        session_limits: Optional[SessionLimits] = None
    ):
        """Initialize the multi-session manager.
        
        Args:
            sio: Socket.IO server instance
            config: Application configuration
            file_store: File storage manager
            session_limits: Optional custom session limits
        """
        self.sio = sio
        self.config = config
        self.file_store = file_store
        self.limits = session_limits or SessionLimits()
        
        # Session tracking
        self.sessions: Dict[str, SessionInfo] = {}
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]
        
        # Underlying session managers
        self.session_managers: Dict[str, SessionManager] = {}
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None

    async def __aenter__(self):
        """Start background tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()
        
        # Stop all sessions
        for session_id in list(self.sessions.keys()):
            await self.stop_session(session_id)

    async def create_session(
        self,
        user_id: str,
        name: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> SessionInfo:
        """Create a new session for a user.
        
        Args:
            user_id: ID of the user creating the session
            name: Name of the session
            metadata: Optional metadata for the session
            
        Returns:
            SessionInfo for the created session
            
        Raises:
            SessionLimitError: If user or total session limits are exceeded
            ResourceLimitError: If system resources are insufficient
        """
        # Check session limits
        if len(self.sessions) >= self.limits.max_total_sessions:
            raise SessionLimitError("Maximum total sessions reached")
            
        user_session_count = len(self.user_sessions.get(user_id, []))
        if user_session_count >= self.limits.max_sessions_per_user:
            raise SessionLimitError(
                f"Maximum sessions per user ({self.limits.max_sessions_per_user}) reached"
            )
            
        # Generate session ID and create info
        session_id = str(uuid.uuid4())
        session_info = SessionInfo(
            session_id=session_id,
            user_id=user_id,
            name=name,
            state=SessionState.INITIALIZING,
            metadata=metadata or {}
        )
        
        try:
            # Create session manager
            session_manager = SessionManager(
                sio=self.sio,
                config=self.config,
                file_store=self.file_store
            )
            
            # Track session
            self.sessions[session_id] = session_info
            self.session_managers[session_id] = session_manager
            
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = []
            self.user_sessions[user_id].append(session_id)
            
            # Update state
            session_info.state = SessionState.RUNNING
            
            return session_info
            
        except Exception as e:
            # Clean up on failure
            self.sessions.pop(session_id, None)
            self.session_managers.pop(session_id, None)
            if user_id in self.user_sessions:
                self.user_sessions[user_id].remove(session_id)
            
            logger.error(f"Failed to create session: {e}")
            session_info.state = SessionState.ERROR
            session_info.error_message = str(e)
            raise

    async def stop_session(self, session_id: str):
        """Stop and clean up a session."""
        session_info = self.sessions.get(session_id)
        if not session_info:
            return
            
        try:
            session_info.state = SessionState.STOPPING
            
            # Clean up session manager
            session_manager = self.session_managers.get(session_id)
            if session_manager:
                # Close all connections
                for connection_id in list(session_manager.local_connection_id_to_session_id.keys()):
                    await session_manager.disconnect_from_session(connection_id)
                
            # Update tracking
            self.sessions.pop(session_id, None)
            self.session_managers.pop(session_id, None)
            
            if session_info.user_id in self.user_sessions:
                self.user_sessions[session_info.user_id].remove(session_id)
                
            session_info.state = SessionState.STOPPED
            
        except Exception as e:
            logger.error(f"Error stopping session {session_id}: {e}")
            session_info.state = SessionState.ERROR
            session_info.error_message = str(e)
            raise

    async def pause_session(self, session_id: str):
        """Pause a running session."""
        session_info = self.sessions.get(session_id)
        if not session_info or not session_info.is_active():
            return
            
        try:
            # TODO: Implement session pausing
            # This might involve saving state and releasing some resources
            session_info.state = SessionState.PAUSED
            
        except Exception as e:
            logger.error(f"Error pausing session {session_id}: {e}")
            session_info.state = SessionState.ERROR
            session_info.error_message = str(e)
            raise

    async def resume_session(self, session_id: str):
        """Resume a paused session."""
        session_info = self.sessions.get(session_id)
        if not session_info or session_info.state != SessionState.PAUSED:
            return
            
        try:
            # TODO: Implement session resuming
            # This might involve restoring state and reallocating resources
            session_info.state = SessionState.RUNNING
            
        except Exception as e:
            logger.error(f"Error resuming session {session_id}: {e}")
            session_info.state = SessionState.ERROR
            session_info.error_message = str(e)
            raise

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """Get information about a session."""
        return self.sessions.get(session_id)

    def list_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """List all sessions for a user."""
        session_ids = self.user_sessions.get(user_id, [])
        return [
            self.sessions[sid] for sid in session_ids 
            if sid in self.sessions
        ]

    async def _cleanup_loop(self):
        """Background task to clean up inactive sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow()
                timeout = timedelta(minutes=self.limits.session_timeout_minutes)
                
                for session_id, info in list(self.sessions.items()):
                    # Check for timeout
                    if (current_time - info.last_active) > timeout:
                        logger.info(f"Session {session_id} timed out, stopping")
                        await self.stop_session(session_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _monitor_loop(self):
        """Background task to monitor session resource usage."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                for session_id, info in list(self.sessions.items()):
                    if not info.is_active():
                        continue
                        
                    # TODO: Implement resource usage monitoring
                    # This should update info.resource_usage with current metrics
                    
                    # Check resource limits
                    if info.exceeds_resource_limits(self.limits.resource_limits):
                        logger.warning(f"Session {session_id} exceeded resource limits")
                        # Could automatically pause or stop the session here
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

    async def get_session_manager(self, session_id: str) -> Optional[SessionManager]:
        """Get the session manager for a session."""
        return self.session_managers.get(session_id)