"""API endpoints for resource monitoring."""

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from openhands.server.api.auth import get_current_user
from openhands.server.monitoring.resource_monitor import MonitoringManager

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

def get_monitoring_manager() -> MonitoringManager:
    """Dependency to get the monitoring manager instance."""
    # TODO: Get from app state
    raise NotImplementedError()

@router.websocket("/sessions/{session_id}/stats")
async def session_stats(
    websocket: WebSocket,
    session_id: str,
    current_user: str = Depends(get_current_user),
    manager: MonitoringManager = Depends(get_monitoring_manager)
):
    """WebSocket endpoint for session resource stats."""
    await websocket.accept()
    
    # Get update queue
    queue = await manager.add_client(session_id)
    
    try:
        while True:
            # Get and send updates
            message = await queue.get()
            await websocket.send_text(message)
            
    except Exception as e:
        await websocket.close(code=4000, reason=str(e))
    finally:
        await manager.remove_client(session_id, queue)

@router.get("/system")
async def get_system_stats(
    current_user: str = Depends(get_current_user),
    manager: MonitoringManager = Depends(get_monitoring_manager)
):
    """Get current system resource stats."""
    try:
        stats = await manager.system_monitor.get_system_resources()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}")
async def get_session_stats(
    session_id: str,
    current_user: str = Depends(get_current_user),
    manager: MonitoringManager = Depends(get_monitoring_manager)
):
    """Get current resource stats for a session."""
    try:
        stats = manager.resource_monitor.get_current_usage(session_id)
        if not stats:
            raise HTTPException(status_code=404, detail="Session not found")
        return stats.__dict__
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))