"""Cost tracking for OpenHands sessions."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import json

from openhands.core.config import LLMConfig
from openhands.core.logger import openhands_logger as logger

@dataclass
class ModelCosts:
    """Cost rates for different LLM models."""
    input_per_1k_tokens: Decimal
    output_per_1k_tokens: Decimal
    embedding_per_1k_tokens: Decimal = Decimal('0.0')
    minimum_tokens: int = 1

    @classmethod
    def for_model(cls, model_id: str) -> 'ModelCosts':
        """Get cost rates for a specific model."""
        # Anthropic Claude models
        if 'claude-3' in model_id:
            if 'opus' in model_id:
                return cls(
                    input_per_1k_tokens=Decimal('0.015'),
                    output_per_1k_tokens=Decimal('0.075')
                )
            elif 'sonnet' in model_id:
                return cls(
                    input_per_1k_tokens=Decimal('0.003'),
                    output_per_1k_tokens=Decimal('0.015')
                )
            elif 'haiku' in model_id:
                return cls(
                    input_per_1k_tokens=Decimal('0.0015'),
                    output_per_1k_tokens=Decimal('0.007')
                )
        elif 'claude-2' in model_id:
            return cls(
                input_per_1k_tokens=Decimal('0.008'),
                output_per_1k_tokens=Decimal('0.024')
            )

        # OpenAI GPT-4 models
        elif 'gpt-4' in model_id:
            if 'turbo' in model_id:
                return cls(
                    input_per_1k_tokens=Decimal('0.01'),
                    output_per_1k_tokens=Decimal('0.03')
                )
            else:
                return cls(
                    input_per_1k_tokens=Decimal('0.03'),
                    output_per_1k_tokens=Decimal('0.06')
                )

        # OpenAI GPT-3.5 models
        elif 'gpt-3.5-turbo' in model_id:
            return cls(
                input_per_1k_tokens=Decimal('0.0005'),
                output_per_1k_tokens=Decimal('0.0015')
            )

        # OpenAI embedding models
        elif 'text-embedding' in model_id:
            return cls(
                input_per_1k_tokens=Decimal('0.0001'),
                output_per_1k_tokens=Decimal('0.0'),
                embedding_per_1k_tokens=Decimal('0.0001')
            )

        # Default to zero cost for unknown models
        logger.warning(f"Unknown model {model_id}, defaulting to zero cost")
        return cls(
            input_per_1k_tokens=Decimal('0.0'),
            output_per_1k_tokens=Decimal('0.0')
        )

@dataclass
class UsageEvent:
    """Record of a single LLM usage event."""
    timestamp: datetime
    model_id: str
    input_tokens: int
    output_tokens: int
    embedding_tokens: int = 0
    success: bool = True
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def calculate_cost(self, model_costs: ModelCosts) -> Decimal:
        """Calculate the cost for this usage event."""
        if not self.success:
            return Decimal('0.0')

        input_cost = (Decimal(self.input_tokens) / 1000) * model_costs.input_per_1k_tokens
        output_cost = (Decimal(self.output_tokens) / 1000) * model_costs.output_per_1k_tokens
        embedding_cost = (Decimal(self.embedding_tokens) / 1000) * model_costs.embedding_per_1k_tokens

        return input_cost + output_cost + embedding_cost

@dataclass
class CostSummary:
    """Summary of costs for a time period."""
    start_time: datetime
    end_time: datetime
    total_cost: Decimal = Decimal('0.0')
    total_tokens: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    costs_by_model: Dict[str, Decimal] = field(default_factory=dict)
    tokens_by_model: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'total_cost': str(self.total_cost),
            'total_tokens': self.total_tokens,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'costs_by_model': {k: str(v) for k, v in self.costs_by_model.items()},
            'tokens_by_model': self.tokens_by_model
        }

class CostTracker:
    """Tracks LLM usage costs for sessions."""

    def __init__(self):
        """Initialize the cost tracker."""
        self._usage_events: Dict[str, List[UsageEvent]] = {}
        self._summaries: Dict[str, List[CostSummary]] = {}
        self._summary_task: Optional[asyncio.Task] = None
        self._summary_interval = timedelta(hours=1)

    async def start(self) -> None:
        """Start cost tracking and summarization."""
        self._summary_task = asyncio.create_task(self._generate_summaries())
        logger.info("Started cost tracker")

    async def stop(self) -> None:
        """Stop cost tracking."""
        if self._summary_task:
            self._summary_task.cancel()
            try:
                await self._summary_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped cost tracker")

    def record_usage(self, session_id: str, event: UsageEvent) -> None:
        """Record a usage event for a session.
        
        Args:
            session_id: ID of the session
            event: Usage event to record
        """
        if session_id not in self._usage_events:
            self._usage_events[session_id] = []
        self._usage_events[session_id].append(event)

    def get_current_cost(self, session_id: str) -> Decimal:
        """Get the current total cost for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Total cost in USD
        """
        total = Decimal('0.0')
        for event in self._usage_events.get(session_id, []):
            costs = ModelCosts.for_model(event.model_id)
            total += event.calculate_cost(costs)
        return total

    def get_summaries(
        self,
        session_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[CostSummary]:
        """Get cost summaries for a session.
        
        Args:
            session_id: ID of the session
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            List of cost summaries
        """
        summaries = self._summaries.get(session_id, [])
        if not (start_time or end_time):
            return summaries

        filtered = []
        for summary in summaries:
            if start_time and summary.end_time < start_time:
                continue
            if end_time and summary.start_time > end_time:
                continue
            filtered.append(summary)
        return filtered

    async def _generate_summaries(self) -> None:
        """Generate periodic cost summaries."""
        while True:
            try:
                now = datetime.utcnow()
                period_start = now - self._summary_interval
                
                # Generate summaries for each session
                for session_id, events in self._usage_events.items():
                    # Filter events for this period
                    period_events = [
                        e for e in events
                        if period_start <= e.timestamp <= now
                    ]
                    
                    if not period_events:
                        continue
                    
                    # Create summary
                    summary = CostSummary(
                        start_time=period_start,
                        end_time=now
                    )
                    
                    # Calculate totals
                    for event in period_events:
                        costs = ModelCosts.for_model(event.model_id)
                        cost = event.calculate_cost(costs)
                        
                        # Update summary
                        summary.total_cost += cost
                        summary.total_tokens += (
                            event.input_tokens +
                            event.output_tokens +
                            event.embedding_tokens
                        )
                        
                        if event.success:
                            summary.successful_requests += 1
                        else:
                            summary.failed_requests += 1
                        
                        # Update per-model stats
                        if event.model_id not in summary.costs_by_model:
                            summary.costs_by_model[event.model_id] = Decimal('0.0')
                            summary.tokens_by_model[event.model_id] = 0
                        
                        summary.costs_by_model[event.model_id] += cost
                        summary.tokens_by_model[event.model_id] += (
                            event.input_tokens +
                            event.output_tokens +
                            event.embedding_tokens
                        )
                    
                    # Store summary
                    if session_id not in self._summaries:
                        self._summaries[session_id] = []
                    self._summaries[session_id].append(summary)
                    
                    # Log summary
                    logger.info(
                        f"Cost summary for session {session_id}",
                        extra={'summary': summary.to_dict()}
                    )
                
                # Clean up old events
                for session_id, events in self._usage_events.items():
                    self._usage_events[session_id] = [
                        e for e in events
                        if e.timestamp > period_start
                    ]
                
                # Wait until next period
                next_summary = now + self._summary_interval
                wait_seconds = (next_summary - datetime.utcnow()).total_seconds()
                await asyncio.sleep(max(0, wait_seconds))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error generating cost summaries: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

class SessionCostManager:
    """Manages cost tracking and limits for sessions."""

    def __init__(self):
        """Initialize the cost manager."""
        self.cost_tracker = CostTracker()
        self._cost_limits: Dict[str, Decimal] = {}
        self._warning_thresholds: Dict[str, List[Decimal]] = {}
        self._warning_handlers: List[callable] = []
        self._limit_handlers: List[callable] = []

    async def start(self) -> None:
        """Start cost management."""
        await self.cost_tracker.start()
        logger.info("Started cost manager")

    async def stop(self) -> None:
        """Stop cost management."""
        await self.cost_tracker.stop()
        logger.info("Stopped cost manager")

    def set_cost_limit(
        self,
        session_id: str,
        limit: Decimal,
        warning_thresholds: Optional[List[Decimal]] = None
    ) -> None:
        """Set a cost limit for a session.
        
        Args:
            session_id: ID of the session
            limit: Maximum cost in USD
            warning_thresholds: Optional list of warning thresholds
        """
        self._cost_limits[session_id] = limit
        if warning_thresholds:
            self._warning_thresholds[session_id] = sorted(warning_thresholds)
        logger.info(f"Set cost limit for session {session_id}: ${limit}")

    def register_warning_handler(self, handler: callable) -> None:
        """Register a handler for cost warnings.
        
        Args:
            handler: Async function(session_id: str, current_cost: Decimal, threshold: Decimal)
        """
        self._warning_handlers.append(handler)

    def register_limit_handler(self, handler: callable) -> None:
        """Register a handler for cost limit violations.
        
        Args:
            handler: Async function(session_id: str, current_cost: Decimal, limit: Decimal)
        """
        self._limit_handlers.append(handler)

    async def check_cost_limit(self, session_id: str, event: UsageEvent) -> bool:
        """Check if a usage event would exceed the cost limit.
        
        Args:
            session_id: ID of the session
            event: Proposed usage event
            
        Returns:
            True if event is allowed, False if it would exceed limit
        """
        if session_id not in self._cost_limits:
            return True

        # Calculate current cost
        current_cost = self.cost_tracker.get_current_cost(session_id)
        
        # Calculate cost of new event
        costs = ModelCosts.for_model(event.model_id)
        event_cost = event.calculate_cost(costs)
        
        total_cost = current_cost + event_cost
        limit = self._cost_limits[session_id]
        
        # Check if this would exceed limit
        if total_cost > limit:
            # Notify limit handlers
            for handler in self._limit_handlers:
                try:
                    await handler(session_id, total_cost, limit)
                except Exception as e:
                    logger.error(f"Error in limit handler: {e}")
            return False
        
        # Check warning thresholds
        if session_id in self._warning_thresholds:
            thresholds = self._warning_thresholds[session_id]
            for threshold in thresholds:
                if current_cost <= threshold < total_cost:
                    # Crossed threshold, notify handlers
                    for handler in self._warning_handlers:
                        try:
                            await handler(session_id, total_cost, threshold)
                        except Exception as e:
                            logger.error(f"Error in warning handler: {e}")
        
        return True

    async def record_usage(self, session_id: str, event: UsageEvent) -> None:
        """Record a usage event if within limits.
        
        Args:
            session_id: ID of the session
            event: Usage event to record
            
        Raises:
            ValueError: If event would exceed cost limit
        """
        if not await self.check_cost_limit(session_id, event):
            raise ValueError(f"Usage would exceed cost limit for session {session_id}")
        
        self.cost_tracker.record_usage(session_id, event)

    def get_cost_summary(self, session_id: str) -> Dict:
        """Get a cost summary for a session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dictionary with cost summary
        """
        current_cost = self.cost_tracker.get_current_cost(session_id)
        limit = self._cost_limits.get(session_id)
        warnings = self._warning_thresholds.get(session_id, [])
        
        return {
            'current_cost': str(current_cost),
            'cost_limit': str(limit) if limit else None,
            'warning_thresholds': [str(w) for w in warnings],
            'usage_summaries': [
                s.to_dict() for s in self.cost_tracker.get_summaries(session_id)
            ]
        }