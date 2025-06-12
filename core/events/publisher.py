"""
Redis Streams Event Publisher with MCP Integration
Agent 1 Domain - Core Infrastructure
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from core import mcp


class EventPublisher:
    """Redis Streams event publisher with MCP tool integration"""
    
    def __init__(self, publisher_id: str = "event_publisher"):
        self.publisher_id = publisher_id
        self.cost_tracker = CostTracker()
    
    async def publish(self, stream: str, event_type: str, data: Dict[str, Any], 
                     correlation_id: Optional[str] = None) -> str:
        """
        Publish event to Redis Stream using MCP tools
        
        Args:
            stream: Redis stream name (e.g., 'homeowner:projects')
            event_type: Type of event (e.g., 'project_submitted')
            data: Event payload data
            correlation_id: Optional correlation ID for event tracking
            
        Returns:
            Event ID from Redis
            
        Usage:
            await publisher.publish(
                "homeowner:projects", 
                "project_submitted",
                {"project_id": "123", "description": "..."}
            )
        """
        
        # Cost control check before processing
        if not await self.cost_tracker.check_cost_approval(0.02):  # Estimated cost
            raise CostLimitExceededError("Event publishing blocked - cost limit reached")
        
        # Create event payload with metadata
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        event_payload = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "publisher_id": self.publisher_id,
            "correlation_id": correlation_id or event_id,
            "data": json.dumps(data) if isinstance(data, dict) else str(data)
        }
        
        try:
            # Publish to Redis Stream via MCP
            result = await mcp.call_tool("redis", {
                "command": "xadd",
                "stream": stream,
                "fields": event_payload
            })
            
            # Log successful publication
            await self._log_event_publication(stream, event_type, event_id, "success")
            
            return result
            
        except Exception as e:
            # Log failed publication
            await self._log_event_publication(stream, event_type, event_id, "failed", str(e))
            raise EventPublicationError(f"Failed to publish event: {e}")
    
    async def publish_batch(self, events: list) -> list:
        """Publish multiple events efficiently"""
        results = []
        
        for event in events:
            try:
                result = await self.publish(**event)
                results.append({"status": "success", "event_id": result})
            except Exception as e:
                results.append({"status": "failed", "error": str(e)})
        
        return results
    
    async def _log_event_publication(self, stream: str, event_type: str, 
                                   event_id: str, status: str, error: str = None):
        """Log event publication for audit trail"""
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "publisher_id": self.publisher_id,
            "stream": stream,
            "event_type": event_type,
            "event_id": event_id,
            "status": status,
            "error": error
        }
        
        try:
            # Store in Supabase events table via MCP
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO events (
                        event_id, stream_name, event_type, 
                        publisher_id, status, error_message, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                "params": [
                    event_id, stream, event_type, 
                    self.publisher_id, status, error, log_entry["timestamp"]
                ]
            })
        except Exception as e:
            # Don't fail event publication due to logging issues
            print(f"Warning: Failed to log event publication: {e}")


class CostTracker:
    """Cost control and circuit breaker for event processing"""
    
    def __init__(self, daily_limit: float = 1000.0, per_event_limit: float = 0.05):
        self.daily_limit = daily_limit
        self.per_event_limit = per_event_limit
        self.daily_cost = 0.0
        self.last_reset_date = datetime.utcnow().date()
    
    async def check_cost_approval(self, estimated_cost: float) -> bool:
        """
        Check if operation is within cost limits
        
        Returns:
            True if operation approved, False if blocked
        """
        
        # Reset daily cost if new day
        current_date = datetime.utcnow().date()
        if current_date > self.last_reset_date:
            self.daily_cost = 0.0
            self.last_reset_date = current_date
        
        # Check per-event limit
        if estimated_cost > self.per_event_limit:
            await self._log_cost_violation("per_event_limit_exceeded", estimated_cost)
            return False
        
        # Check daily limit
        if self.daily_cost + estimated_cost > self.daily_limit:
            await self._trigger_emergency_shutdown()
            return False
        
        # Approve operation
        self.daily_cost += estimated_cost
        return True
    
    async def _log_cost_violation(self, violation_type: str, cost: float):
        """Log cost limit violations"""
        try:
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO cost_violations (
                        violation_type, attempted_cost, daily_total, 
                        timestamp, action_taken
                    ) VALUES ($1, $2, $3, $4, $5)
                """,
                "params": [
                    violation_type, cost, self.daily_cost,
                    datetime.utcnow().isoformat(), "operation_blocked"
                ]
            })
        except Exception as e:
            print(f"Critical: Failed to log cost violation: {e}")
    
    async def _trigger_emergency_shutdown(self):
        """Trigger emergency shutdown on cost limit breach"""
        try:
            # Publish emergency shutdown event
            emergency_event = {
                "event_type": "system_emergency_shutdown",
                "reason": "daily_cost_limit_exceeded",
                "daily_cost": self.daily_cost,
                "daily_limit": self.daily_limit,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await mcp.call_tool("redis", {
                "command": "xadd",
                "stream": "system:emergency",
                "fields": emergency_event
            })
            
        except Exception as e:
            print(f"Critical: Failed to trigger emergency shutdown: {e}")


# Custom Exceptions
class EventPublicationError(Exception):
    """Raised when event publication fails"""
    pass

class CostLimitExceededError(Exception):
    """Raised when cost limits are exceeded"""
    pass


# Example usage for Agent 1:
"""
# Initialize publisher
publisher = EventPublisher("agent_1_infrastructure")

# Publish infrastructure ready event
await publisher.publish(
    "infrastructure:status",
    "redis_streams_operational",
    {
        "streams_created": ["homeowner:projects", "homeowner:intake_complete"],
        "consumer_groups": ["intake_processors", "scope_processors"],
        "status": "operational"
    }
)
"""
