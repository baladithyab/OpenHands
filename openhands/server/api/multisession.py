"""API endpoints for multi-session management."""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import BaseModel

from openhands.server.api.auth import get_current_user
from openhands.server.multisession.manager import (
    MultiSessionManager,
    ResourceLimitError,
    SessionLimitError
)
from openhands.server.multisession.models import SessionState

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Pydantic models for API
class SessionCreate(BaseModel):
    """Request model for session creation."""
    name: str
    metadata: Optional[Dict[str, str]] = None

class SessionUpdate(BaseModel):
    """Request model for session updates."""
    name: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None

class ResourceUsageResponse(BaseModel):
    """Response model for resource usage."""
    cpu_percent: float
    memory_mb: float
    disk_mb: float
    container_count: int
    last_updated: datetime

class SessionResponse(BaseModel):
    """Response model for session information."""
    session_id: str
    user_id: str
    name: str
    state: str
    created_at: datetime
    last_active: datetime
    resource_usage: ResourceUsageResponse
    metadata: Dict[str, str]
    error_message: Optional[str] = None

def get_session_manager() -> MultiSessionManager:
    """Dependency to get the session manager instance."""
    # TODO: Get from app state
    raise NotImplementedError()

@router.post("/", response_model=SessionResponse)
async def create_session(
    request: SessionCreate,
    current_user: str = Depends(get_current_user),
    manager: MultiSessionManager = Depends(get_session_manager)
):
    """Create a new session."""
    try:
        session_info = await manager.create_session(
            user_id=current_user,
            name=request.name,
            metadata=request.metadata
        )
        return SessionResponse(
            session_id=session_info.session_id,
            user_id=session_info.user_id,
            name=session_info.name,
            state=session_info.state.name,
            created_at=session_info.created_at,
            last_active=session_info.last_active,
            resource_usage=ResourceUsageResponse(**session_info.resource_usage.__dict__),
            metadata=session_info.metadata,
            error_message=session_info.error_message
        )
    except SessionLimitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ResourceLimitError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[SessionResponse])
async def list_sessions(
    current_user: str = Depends(get_current_user),
    manager: MultiSessionManager = Depends(get_session_manager)
):
    """List all sessions for the current user."""
    sessions = manager.list_user_sessions(current_user)
    return [
        SessionResponse(
            session_id=s.session_id,
            user_id=s.user_id,
            name=s.name,
            state=s.state.name,
            created_at=s.created_at,
            last_active=s.last_active,
            resource_usage=ResourceUsageResponse(**s.resource_usage.__dict__),
            metadata=s.metadata,
            error_message=s.error_message
        )
        for s in sessions
    ]

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: str = Depends(get_current_user),
    manager: MultiSessionManager = Depends(get_session_manager)
):
    """Get details of a specific session."""
    session_info = manager.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_info.user_id != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")
        
    return SessionResponse(
        session_id=session_info.session_id,
        user_id=session_info.user_id,
        name=session_info.name,
        state=session_info.state.name,
        created_at=session_info.created_at,
        last_active=session_info.last_active,
        resource_usage=ResourceUsageResponse(**session_info.resource_usage.__dict__),
        metadata=session_info.metadata,
        error_message=session_info.error_message
    )

@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    request: SessionUpdate,
    current_user: str = Depends(get_current_user),
    manager: MultiSessionManager = Depends(get_session_manager)
):
    """Update session metadata."""
    session_info = manager.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_info.user_id != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to modify this session")
    
    if request.name:
        session_info.name = request.name
    if request.metadata:
        session_info.metadata.update(request.metadata)
        
    return SessionResponse(
        session_id=session_info.session_id,
        user_id=session_info.user_id,
        name=session_info.name,
        state=session_info.state.name,
        created_at=session_info.created_at,
        last_active=session_info.last_active,
        resource_usage=ResourceUsageResponse(**session_info.resource_usage.__dict__),
        metadata=session_info.metadata,
        error_message=session_info.error_message
    )

@router.post("/{session_id}/stop")
async def stop_session(
    session_id: str,
    current_user: str = Depends(get_current_user),
    manager: MultiSessionManager = Depends(get_session_manager)
):
    """Stop a session."""
    session_info = manager.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_info.user_id != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to stop this session")
        
    await manager.stop_session(session_id)
    return {"status": "stopped"}

@router.post("/{session_id}/pause")
async def pause_session(
    session_id: str,
    current_user: str = Depends(get_current_user),
    manager: MultiSessionManager = Depends(get_session_manager)
):
    """Pause a session."""
    session_info = manager.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_info.user_id != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to pause this session")
        
    if not session_info.is_active():
        raise HTTPException(status_code=400, detail="Session is not in a pausable state")
        
    await manager.pause_session(session_id)
    return {"status": "paused"}

@router.post("/{session_id}/resume")
async def resume_session(
    session_id: str,
    current_user: str = Depends(get_current_user),
    manager: MultiSessionManager = Depends(get_session_manager)
):
    """Resume a paused session."""
    session_info = manager.get_session_info(session_id)
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session_info.user_id != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to resume this session")
        
    if session_info.state != SessionState.PAUSED:
        raise HTTPException(status_code=400, detail="Session is not paused")
        
    await manager.resume_session(session_id)
    return {"status": "resumed"}

@router.websocket("/{session_id}/events")
async def session_events(
    websocket: WebSocket,
    session_id: str,
    current_user: str = Depends(get_current_user),
    manager: MultiSessionManager = Depends(get_session_manager)
):
    """WebSocket endpoint for session events."""
    session_info = manager.get_session_info(session_id)
    if not session_info:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    if session_info.user_id != current_user:
        await websocket.close(code=4003, reason="Not authorized")
        return
        
    await websocket.accept()
    
    try:
        while True:
            # Send session updates
            session_info = manager.get_session_info(session_id)
            if not session_info:
                break
                
            await websocket.send_json({
                "type": "session_update",
                "data": {
                    "state": session_info.state.name,
                    "resource_usage": session_info.resource_usage.__dict__,
                    "error_message": session_info.error_message
                }
            })
            
            await websocket.receive_text()  # Wait for ping
            
    except Exception as e:
        await websocket.close(code=4000, reason=str(e))
    finally:
        await websocket.close()