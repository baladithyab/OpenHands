"""Resource monitoring for OpenHands sessions."""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import docker
import psutil
from openhands.core.logger import openhands_logger as logger
from openhands.server.multisession.models import ResourceUsage, SessionInfo

class ResourceMonitor:
    """Monitors system and container resources for sessions."""

    def __init__(self):
        """Initialize the resource monitor."""
        self.docker_client = docker.from_env()
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._last_stats: Dict[str, ResourceUsage] = {}

    async def start_monitoring(self, session_info: SessionInfo) -> None:
        """Start monitoring resources for a session.
        
        Args:
            session_info: The session to monitor
        """
        if session_info.session_id in self._monitoring_tasks:
            return

        task = asyncio.create_task(
            self._monitor_session(session_info.session_id)
        )
        self._monitoring_tasks[session_info.session_id] = task
        logger.info(f"Started monitoring session {session_info.session_id}")

    async def stop_monitoring(self, session_id: str) -> None:
        """Stop monitoring resources for a session.
        
        Args:
            session_id: ID of the session to stop monitoring
        """
        task = self._monitoring_tasks.pop(session_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self._last_stats.pop(session_id, None)
            logger.info(f"Stopped monitoring session {session_id}")

    def get_current_usage(self, session_id: str) -> Optional[ResourceUsage]:
        """Get the current resource usage for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Current resource usage or None if not monitored
        """
        return self._last_stats.get(session_id)

    async def _monitor_session(self, session_id: str) -> None:
        """Monitor resources for a session continuously.
        
        Args:
            session_id: ID of the session to monitor
        """
        while True:
            try:
                # Get container stats
                containers = await self._get_session_containers(session_id)
                container_stats = await self._get_container_stats(containers)
                
                # Calculate total resource usage
                total_cpu = sum(stats['cpu_percent'] for stats in container_stats)
                total_memory = sum(stats['memory_mb'] for stats in container_stats)
                total_disk = await self._get_session_disk_usage(session_id)
                
                # Update stats
                self._last_stats[session_id] = ResourceUsage(
                    cpu_percent=total_cpu,
                    memory_mb=total_memory,
                    disk_mb=total_disk,
                    container_count=len(containers),
                    last_updated=datetime.utcnow()
                )
                
                # Wait before next update
                await asyncio.sleep(5)  # Update every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring session {session_id}: {e}")
                await asyncio.sleep(10)  # Wait longer on error

    async def _get_session_containers(self, session_id: str) -> List[docker.models.containers.Container]:
        """Get all containers for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            List of Docker containers
        """
        try:
            containers = self.docker_client.containers.list(
                filters={
                    'label': [f'openhands.session_id={session_id}']
                }
            )
            return containers
        except Exception as e:
            logger.error(f"Error getting containers for session {session_id}: {e}")
            return []

    async def _get_container_stats(
        self,
        containers: List[docker.models.containers.Container]
    ) -> List[Dict]:
        """Get resource stats for containers.
        
        Args:
            containers: List of Docker containers
            
        Returns:
            List of container stats
        """
        stats = []
        for container in containers:
            try:
                # Get raw stats
                raw_stats = container.stats(stream=False)
                
                # Calculate CPU usage
                cpu_delta = raw_stats['cpu_stats']['cpu_usage']['total_usage'] - \
                           raw_stats['precpu_stats']['cpu_usage']['total_usage']
                system_delta = raw_stats['cpu_stats']['system_cpu_usage'] - \
                             raw_stats['precpu_stats']['system_cpu_usage']
                cpu_percent = 0.0
                if system_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * 100.0
                
                # Calculate memory usage
                memory_usage = raw_stats['memory_stats']['usage']
                memory_mb = memory_usage / (1024 * 1024)  # Convert to MB
                
                stats.append({
                    'container_id': container.id,
                    'cpu_percent': cpu_percent,
                    'memory_mb': memory_mb
                })
                
            except Exception as e:
                logger.error(f"Error getting stats for container {container.id}: {e}")
                continue
                
        return stats

    async def _get_session_disk_usage(self, session_id: str) -> float:
        """Get disk usage for a session in MB.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Disk usage in MB
        """
        try:
            session_path = f'./cache/sessions/{session_id}'
            if not os.path.exists(session_path):
                return 0.0
                
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(session_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
                    
            return total_size / (1024 * 1024)  # Convert to MB
            
        except Exception as e:
            logger.error(f"Error getting disk usage for session {session_id}: {e}")
            return 0.0

class SystemMonitor:
    """Monitors overall system resources."""

    def __init__(self):
        """Initialize the system monitor."""
        self.docker_client = docker.from_env()

    async def get_system_resources(self) -> Dict:
        """Get current system resource usage.
        
        Returns:
            Dictionary with system resource metrics
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_total_mb = memory.total / (1024 * 1024)
            memory_used_mb = memory.used / (1024 * 1024)
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_total_gb = disk.total / (1024 * 1024 * 1024)
            disk_used_gb = disk.used / (1024 * 1024 * 1024)
            disk_percent = disk.percent
            
            # Docker resources
            docker_info = self.docker_client.info()
            containers_running = docker_info['ContainersRunning']
            containers_total = docker_info['Containers']
            images_total = docker_info['Images']
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count
                },
                'memory': {
                    'total_mb': memory_total_mb,
                    'used_mb': memory_used_mb,
                    'percent': memory_percent
                },
                'disk': {
                    'total_gb': disk_total_gb,
                    'used_gb': disk_used_gb,
                    'percent': disk_percent
                },
                'docker': {
                    'containers_running': containers_running,
                    'containers_total': containers_total,
                    'images': images_total
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

class MonitoringManager:
    """Manages resource monitoring for all sessions."""

    def __init__(self):
        """Initialize the monitoring manager."""
        self.resource_monitor = ResourceMonitor()
        self.system_monitor = SystemMonitor()
        self._broadcast_task: Optional[asyncio.Task] = None
        self._websocket_clients: Dict[str, List[asyncio.Queue]] = {}

    async def start(self) -> None:
        """Start the monitoring manager."""
        self._broadcast_task = asyncio.create_task(self._broadcast_stats())
        logger.info("Started monitoring manager")

    async def stop(self) -> None:
        """Stop the monitoring manager."""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped monitoring manager")

    async def register_session(self, session_info: SessionInfo) -> None:
        """Register a session for monitoring.
        
        Args:
            session_info: Session to monitor
        """
        await self.resource_monitor.start_monitoring(session_info)
        self._websocket_clients[session_info.session_id] = []

    async def unregister_session(self, session_id: str) -> None:
        """Unregister a session from monitoring.
        
        Args:
            session_id: ID of the session to unregister
        """
        await self.resource_monitor.stop_monitoring(session_id)
        self._websocket_clients.pop(session_id, None)

    async def add_client(self, session_id: str) -> asyncio.Queue:
        """Add a WebSocket client for a session.
        
        Args:
            session_id: ID of the session to monitor
            
        Returns:
            Queue for receiving updates
        """
        if session_id not in self._websocket_clients:
            self._websocket_clients[session_id] = []
            
        queue = asyncio.Queue()
        self._websocket_clients[session_id].append(queue)
        return queue

    async def remove_client(self, session_id: str, queue: asyncio.Queue) -> None:
        """Remove a WebSocket client.
        
        Args:
            session_id: ID of the monitored session
            queue: Queue to remove
        """
        if session_id in self._websocket_clients:
            try:
                self._websocket_clients[session_id].remove(queue)
            except ValueError:
                pass

    async def _broadcast_stats(self) -> None:
        """Broadcast resource stats to WebSocket clients."""
        while True:
            try:
                # Get system stats
                system_stats = await self.system_monitor.get_system_resources()
                
                # Broadcast to each session's clients
                for session_id, clients in self._websocket_clients.items():
                    # Get session stats
                    session_stats = self.resource_monitor.get_current_usage(session_id)
                    if not session_stats:
                        continue
                        
                    # Create update message
                    message = {
                        'type': 'resource_update',
                        'data': {
                            'session': {
                                'id': session_id,
                                'resources': session_stats.__dict__
                            },
                            'system': system_stats
                        }
                    }
                    
                    # Send to all clients
                    for queue in clients:
                        try:
                            await queue.put(json.dumps(message))
                        except Exception as e:
                            logger.error(f"Error sending update to client: {e}")
                            
                await asyncio.sleep(5)  # Update every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stats broadcast: {e}")
                await asyncio.sleep(10)  # Wait longer on error