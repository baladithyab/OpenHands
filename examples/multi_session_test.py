"""Example script to test multi-session and cost tracking features."""

import asyncio
from datetime import datetime
from decimal import Decimal
import logging

from openhands.core.config import AppConfig, LLMConfig
from openhands.server.monitoring.cost_tracker import (
    SessionCostManager,
    UsageEvent
)
from openhands.server.monitoring.resource_monitor import MonitoringManager
from openhands.server.multisession.manager import MultiSessionManager
from openhands.server.multisession.models import SessionLimits
from openhands.storage.files import FileStore

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def cost_warning_handler(session_id: str, current_cost: Decimal, threshold: Decimal):
    """Handle cost warnings."""
    logger.warning(
        f"Session {session_id} cost warning: "
        f"${current_cost} exceeds threshold ${threshold}"
    )

async def cost_limit_handler(session_id: str, current_cost: Decimal, limit: Decimal):
    """Handle cost limit violations."""
    logger.error(
        f"Session {session_id} cost limit violation: "
        f"${current_cost} exceeds limit ${limit}"
    )

async def main():
    """Run the test scenario."""
    try:
        # Initialize components
        config = AppConfig()
        llm_config = LLMConfig()
        file_store = FileStore()
        
        # Set up monitoring
        monitoring = MonitoringManager()
        await monitoring.start()
        
        # Set up cost tracking
        cost_manager = SessionCostManager()
        cost_manager.register_warning_handler(cost_warning_handler)
        cost_manager.register_limit_handler(cost_limit_handler)
        await cost_manager.start()
        
        # Set up session management
        session_manager = MultiSessionManager(
            sio=None,  # We don't need Socket.IO for this test
            config=config,
            file_store=file_store,
            session_limits=SessionLimits(
                max_sessions_per_user=3,
                max_total_sessions=5
            )
        )
        
        # Create test sessions
        session1 = await session_manager.create_session(
            user_id="test_user",
            name="Session 1",
            metadata={"purpose": "testing"}
        )
        logger.info(f"Created session 1: {session1.session_id}")
        
        session2 = await session_manager.create_session(
            user_id="test_user",
            name="Session 2",
            metadata={"purpose": "testing"}
        )
        logger.info(f"Created session 2: {session2.session_id}")
        
        # Set cost limits
        cost_manager.set_cost_limit(
            session1.session_id,
            Decimal("1.0"),  # $1.00 limit
            warning_thresholds=[Decimal("0.5")]  # Warning at $0.50
        )
        
        cost_manager.set_cost_limit(
            session2.session_id,
            Decimal("2.0"),  # $2.00 limit
            warning_thresholds=[Decimal("1.0")]  # Warning at $1.00
        )
        
        # Simulate some LLM usage
        models = [
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "claude-3-sonnet"
        ]
        
        for session_id in [session1.session_id, session2.session_id]:
            for model in models:
                # Record some usage
                event = UsageEvent(
                    timestamp=datetime.utcnow(),
                    model_id=model,
                    input_tokens=500,
                    output_tokens=200,
                    success=True,
                    metadata={"test": "example"}
                )
                
                try:
                    await cost_manager.record_usage(session_id, event)
                    logger.info(
                        f"Recorded usage for session {session_id}, "
                        f"model {model}"
                    )
                except ValueError as e:
                    logger.error(f"Cost limit exceeded: {e}")
        
        # Get cost summaries
        for session_id in [session1.session_id, session2.session_id]:
            summary = cost_manager.get_cost_summary(session_id)
            logger.info(f"\nCost summary for session {session_id}:")
            logger.info(f"Current cost: ${summary['current_cost']}")
            logger.info(f"Cost limit: ${summary['cost_limit']}")
            logger.info("Usage summaries:")
            for usage in summary['usage_summaries']:
                logger.info(
                    f"- Period: {usage['start_time']} to {usage['end_time']}"
                )
                logger.info(f"  Total cost: ${usage['total_cost']}")
                logger.info(f"  Total tokens: {usage['total_tokens']}")
                logger.info(
                    f"  Requests: {usage['successful_requests']} successful, "
                    f"{usage['failed_requests']} failed"
                )
        
        # Test resource monitoring
        logger.info("\nResource monitoring:")
        for session_id in [session1.session_id, session2.session_id]:
            usage = monitoring.resource_monitor.get_current_usage(session_id)
            if usage:
                logger.info(f"\nSession {session_id} resource usage:")
                logger.info(f"CPU: {usage.cpu_percent}%")
                logger.info(f"Memory: {usage.memory_mb} MB")
                logger.info(f"Disk: {usage.disk_mb} MB")
                logger.info(f"Containers: {usage.container_count}")
        
        # Test session operations
        logger.info("\nTesting session operations:")
        
        # Pause session 1
        await session_manager.pause_session(session1.session_id)
        logger.info(f"Paused session {session1.session_id}")
        
        # Resume session 1
        await session_manager.resume_session(session1.session_id)
        logger.info(f"Resumed session {session1.session_id}")
        
        # Stop session 2
        await session_manager.stop_session(session2.session_id)
        logger.info(f"Stopped session {session2.session_id}")
        
        # List remaining sessions
        sessions = session_manager.list_user_sessions("test_user")
        logger.info("\nRemaining sessions:")
        for session in sessions:
            logger.info(
                f"- {session.name} ({session.session_id}): {session.state.name}"
            )
        
        # Clean up
        await monitoring.stop()
        await cost_manager.stop()
        
    except Exception as e:
        logger.error(f"Error in test: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())