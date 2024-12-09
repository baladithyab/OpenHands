"""Tests for LLM cost tracking."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock

from openhands.server.monitoring.cost_tracker import (
    CostTracker,
    ModelCosts,
    SessionCostManager,
    UsageEvent
)

@pytest.fixture
def usage_event():
    return UsageEvent(
        timestamp=datetime.utcnow(),
        model_id="gpt-4",
        input_tokens=100,
        output_tokens=50,
        success=True
    )

@pytest.fixture
def cost_tracker():
    return CostTracker()

@pytest.fixture
def cost_manager():
    return SessionCostManager()

def test_model_costs():
    """Test cost calculations for different models."""
    # GPT-4
    gpt4_costs = ModelCosts.for_model("gpt-4")
    assert gpt4_costs.input_per_1k_tokens == Decimal('0.03')
    assert gpt4_costs.output_per_1k_tokens == Decimal('0.06')
    
    # GPT-4 Turbo
    turbo_costs = ModelCosts.for_model("gpt-4-turbo")
    assert turbo_costs.input_per_1k_tokens == Decimal('0.01')
    assert turbo_costs.output_per_1k_tokens == Decimal('0.03')
    
    # Claude 3
    claude_costs = ModelCosts.for_model("claude-3-opus")
    assert claude_costs.input_per_1k_tokens == Decimal('0.015')
    assert claude_costs.output_per_1k_tokens == Decimal('0.075')

def test_usage_event_cost(usage_event):
    """Test cost calculation for usage events."""
    costs = ModelCosts.for_model(usage_event.model_id)
    cost = usage_event.calculate_cost(costs)
    
    # Calculate expected cost
    expected = (
        (Decimal('100') / 1000) * costs.input_per_1k_tokens +
        (Decimal('50') / 1000) * costs.output_per_1k_tokens
    )
    
    assert cost == expected
    
    # Failed events should cost nothing
    usage_event.success = False
    assert usage_event.calculate_cost(costs) == Decimal('0.0')

@pytest.mark.asyncio
async def test_cost_tracking(cost_tracker, usage_event):
    """Test basic cost tracking functionality."""
    session_id = "test_session"
    
    # Record some usage
    cost_tracker.record_usage(session_id, usage_event)
    
    # Get current cost
    cost = cost_tracker.get_current_cost(session_id)
    assert cost > Decimal('0.0')
    
    # Start tracking and wait for summary
    await cost_tracker.start()
    await asyncio.sleep(1)
    
    # Get summaries
    summaries = cost_tracker.get_summaries(session_id)
    assert len(summaries) > 0
    assert summaries[0].total_cost == cost
    
    await cost_tracker.stop()

@pytest.mark.asyncio
async def test_cost_limits(cost_manager, usage_event):
    """Test cost limit enforcement."""
    session_id = "test_session"
    
    # Set a low cost limit
    cost_manager.set_cost_limit(session_id, Decimal('0.001'))
    
    # Create a high-cost event
    usage_event.input_tokens = 1000
    usage_event.output_tokens = 1000
    
    # Should reject the event
    allowed = await cost_manager.check_cost_limit(session_id, usage_event)
    assert not allowed
    
    # Should raise on record
    with pytest.raises(ValueError):
        await cost_manager.record_usage(session_id, usage_event)

@pytest.mark.asyncio
async def test_cost_warnings(cost_manager, usage_event):
    """Test cost warning thresholds."""
    session_id = "test_session"
    warnings_received = []
    
    async def warning_handler(sid, cost, threshold):
        warnings_received.append((sid, cost, threshold))
    
    # Set up warning thresholds
    cost_manager.set_cost_limit(
        session_id,
        Decimal('0.1'),
        warning_thresholds=[Decimal('0.05')]
    )
    cost_manager.register_warning_handler(warning_handler)
    
    # Record usage below threshold
    usage_event.input_tokens = 100
    await cost_manager.record_usage(session_id, usage_event)
    assert len(warnings_received) == 0
    
    # Record usage that crosses threshold
    usage_event.input_tokens = 2000
    await cost_manager.record_usage(session_id, usage_event)
    assert len(warnings_received) > 0
    assert warnings_received[0][0] == session_id
    assert warnings_received[0][2] == Decimal('0.05')

@pytest.mark.asyncio
async def test_cost_summary(cost_manager, usage_event):
    """Test cost summary generation."""
    session_id = "test_session"
    
    # Record some usage
    await cost_manager.record_usage(session_id, usage_event)
    
    # Get summary
    summary = cost_manager.get_cost_summary(session_id)
    
    assert 'current_cost' in summary
    assert Decimal(summary['current_cost']) > Decimal('0.0')
    assert 'usage_summaries' in summary
    
    # Start tracking and wait for periodic summary
    await cost_manager.start()
    await asyncio.sleep(1)
    
    # Get updated summary
    new_summary = cost_manager.get_cost_summary(session_id)
    assert len(new_summary['usage_summaries']) > 0
    
    await cost_manager.stop()

@pytest.mark.asyncio
async def test_multiple_models(cost_manager):
    """Test tracking costs across different models."""
    session_id = "test_session"
    
    # Create events for different models
    gpt4_event = UsageEvent(
        timestamp=datetime.utcnow(),
        model_id="gpt-4",
        input_tokens=100,
        output_tokens=50
    )
    
    claude_event = UsageEvent(
        timestamp=datetime.utcnow(),
        model_id="claude-3-opus",
        input_tokens=100,
        output_tokens=50
    )
    
    # Record usage
    await cost_manager.record_usage(session_id, gpt4_event)
    await cost_manager.record_usage(session_id, claude_event)
    
    # Get summary
    summary = cost_manager.get_cost_summary(session_id)
    current_cost = Decimal(summary['current_cost'])
    
    # Calculate expected costs
    gpt4_costs = ModelCosts.for_model("gpt-4")
    claude_costs = ModelCosts.for_model("claude-3-opus")
    
    gpt4_cost = gpt4_event.calculate_cost(gpt4_costs)
    claude_cost = claude_event.calculate_cost(claude_costs)
    expected_cost = gpt4_cost + claude_cost
    
    assert current_cost == expected_cost

@pytest.mark.asyncio
async def test_time_filtered_summaries(cost_tracker, usage_event):
    """Test getting time-filtered cost summaries."""
    session_id = "test_session"
    
    # Create events at different times
    now = datetime.utcnow()
    
    old_event = UsageEvent(
        timestamp=now - timedelta(hours=2),
        model_id="gpt-4",
        input_tokens=100,
        output_tokens=50
    )
    
    new_event = UsageEvent(
        timestamp=now,
        model_id="gpt-4",
        input_tokens=100,
        output_tokens=50
    )
    
    # Record events
    cost_tracker.record_usage(session_id, old_event)
    cost_tracker.record_usage(session_id, new_event)
    
    # Get filtered summaries
    recent_summaries = cost_tracker.get_summaries(
        session_id,
        start_time=now - timedelta(hours=1)
    )
    
    all_summaries = cost_tracker.get_summaries(session_id)
    
    assert len(recent_summaries) < len(all_summaries)