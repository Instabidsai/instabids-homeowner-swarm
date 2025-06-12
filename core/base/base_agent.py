"""
Base Agent Pattern for Instabids Agent Swarm
All agents inherit from this base class for consistent behavior
"""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
from core import mcp
from core.events.publisher import EventPublisher
from core.events.consumer import EventConsumer
from core.security.contact_filter import ContactProtectionFilter


class BaseAgent(ABC):
    """
    Base class for all Instabids agents
    
    Provides:
    - Event publishing/consuming patterns
    - Health monitoring and heartbeat
    - Error handling and recovery
    - Contact protection integration
    - Cost tracking and limits
    - Shared coordination patterns
    """
    
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.is_running = False
        self.last_heartbeat = None
        
        # Core components
        self.event_publisher = EventPublisher(f"{agent_type}_{agent_id}")
        self.contact_filter = ContactProtectionFilter()
        self.health_monitor = AgentHealthMonitor(agent_id, agent_type)
        
        # Event handling
        self.event_handlers = {}
        self.error_handlers = {}
        
        # Consumer will be created by specific agent
        self.consumer = None
    
    async def start(self) -> None:
        """Start the agent and begin processing"""
        
        try:
            self.is_running = True
            
            # Initialize agent-specific setup
            await self.initialize()
            
            # Start health monitoring
            await self.health_monitor.start_monitoring()
            
            # Start main processing loop
            await self.run()
            
        except Exception as e:
            await self.handle_startup_error(e)
            raise
    
    async def stop(self) -> None:
        """Stop the agent gracefully"""
        
        self.is_running = False
        
        # Publish shutdown event
        await self.event_publisher.publish(
            f"agent:{self.agent_type}:status",
            "agent_shutdown",
            {
                "agent_id": self.agent_id,
                "shutdown_time": datetime.utcnow().isoformat(),
                "reason": "graceful_shutdown"
            }
        )
        
        # Stop health monitoring
        if self.health_monitor:
            await self.health_monitor.stop_monitoring()
        
        # Agent-specific cleanup
        await self.cleanup()
    
    @abstractmethod
    async def initialize(self) -> None:
        """Agent-specific initialization - must be implemented by each agent"""
        pass
    
    @abstractmethod
    async def run(self) -> None:
        """Main agent processing loop - must be implemented by each agent"""
        pass
    
    async def cleanup(self) -> None:
        """Agent-specific cleanup - override if needed"""
        pass
    
    async def publish_event(self, stream: str, event_type: str, data: Dict[str, Any],
                          correlation_id: Optional[str] = None) -> str:
        """
        Publish event with automatic contact filtering
        
        CRITICAL: All outgoing content is automatically filtered for contact info
        """
        
        # Apply contact protection to all outgoing data
        filtered_data = await self._apply_contact_protection(data)
        
        return await self.event_publisher.publish(
            stream, event_type, filtered_data, correlation_id
        )
    
    async def consume_events(self, streams: List[str], consumer_group: str,
                           count: int = 10) -> List[Dict]:
        """Consume events from specified streams"""
        
        if not self.consumer:
            self.consumer = EventConsumer(consumer_group, self.agent_id, self.agent_id)
        
        return await self.consumer.consume_events(streams, count)
    
    def register_event_handler(self, event_type: str, handler):
        """Register handler for specific event type"""
        self.event_handlers[event_type] = handler
    
    async def handle_event(self, event: Dict[str, Any]) -> None:
        """Handle incoming event with registered handlers"""
        
        event_type = event.get("event_type")
        
        if event_type in self.event_handlers:
            try:
                await self.event_handlers[event_type](event)
            except Exception as e:
                await self.handle_event_error(event, e)
        else:
            await self.handle_unknown_event(event)
    
    async def handle_error(self, error: Exception, context: Optional[Dict] = None) -> None:
        """Handle errors with logging and recovery"""
        
        error_event = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            # Log error to Supabase
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO agent_errors (
                        agent_id, agent_type, error_type, error_message,
                        context, timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                "params": [
                    self.agent_id, self.agent_type, error_event["error_type"],
                    error_event["error_message"], json.dumps(error_event["context"]),
                    error_event["timestamp"]
                ]
            })
            
            # Publish error event
            await self.event_publisher.publish(
                f"agent:{self.agent_type}:errors",
                "agent_error",
                error_event
            )
            
        except Exception as e:
            # If we can't log the error, at least print it
            print(f"Critical: Agent {self.agent_id} error logging failed: {e}")
            print(f"Original error: {error}")
    
    async def _apply_contact_protection(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply contact protection to outgoing data
        
        CRITICAL: This ensures no contact info leaks in any agent communication
        """
        
        if not isinstance(data, dict):
            return data
        
        filtered_data = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Scan string content for contact info
                scan_result = await self.contact_filter.scan_content(
                    value, self.agent_id, {"context": "outgoing_data"}
                )
                
                if scan_result["violations_found"]:
                    # Use filtered content
                    filtered_data[key] = scan_result["content_filtered"]
                    
                    # Log the filtering
                    await self._log_content_filtering(key, value, scan_result)
                else:
                    filtered_data[key] = value
            else:
                # Non-string data passes through
                filtered_data[key] = value
        
        return filtered_data
    
    async def _log_content_filtering(self, field: str, original: str, scan_result: Dict) -> None:
        """Log content filtering for audit trail"""
        
        try:
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO content_filtering_log (
                        agent_id, field_name, violation_types, risk_level,
                        timestamp, filtered
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                "params": [
                    self.agent_id, field,
                    ",".join(scan_result["violation_types"]),
                    scan_result["risk_level"],
                    scan_result["scan_timestamp"],
                    True
                ]
            })
        except Exception as e:
            print(f"Warning: Failed to log content filtering: {e}")
    
    async def handle_startup_error(self, error: Exception) -> None:
        """Handle errors during agent startup"""
        await self.handle_error(error, {"phase": "startup"})
    
    async def handle_event_error(self, event: Dict, error: Exception) -> None:
        """Handle errors during event processing"""
        await self.handle_error(error, {"phase": "event_processing", "event": event})
    
    async def handle_unknown_event(self, event: Dict) -> None:
        """Handle events with no registered handler"""
        print(f"Agent {self.agent_id}: Unknown event type {event.get('event_type')}")


class AgentHealthMonitor:
    """Health monitoring and heartbeat for agents"""
    
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.is_monitoring = False
        self.heartbeat_interval = 30  # seconds
        self.last_heartbeat = None
    
    async def start_monitoring(self) -> None:
        """Start health monitoring and heartbeat"""
        
        self.is_monitoring = True
        
        # Start heartbeat task
        asyncio.create_task(self._heartbeat_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop health monitoring"""
        self.is_monitoring = False
    
    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat events"""
        
        while self.is_monitoring:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                print(f"Heartbeat error for {self.agent_id}: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _send_heartbeat(self) -> None:
        """Send heartbeat event"""
        
        self.last_heartbeat = datetime.utcnow().isoformat()
        
        heartbeat_data = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": "healthy",
            "timestamp": self.last_heartbeat,
            "heartbeat_sequence": int(datetime.utcnow().timestamp())
        }
        
        try:
            await mcp.call_tool("redis", {
                "command": "xadd",
                "stream": "agent:heartbeats",
                "fields": heartbeat_data
            })
        except Exception as e:
            print(f"Failed to send heartbeat for {self.agent_id}: {e}")


# Event Mixin for common event handling patterns
class EventMixin:
    """Mixin providing common event handling patterns"""
    
    async def wait_for_event(self, event_type: str, timeout: int = 30) -> Optional[Dict]:
        """Wait for specific event type with timeout"""
        
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).seconds < timeout:
            events = await self.consume_events(["*"], f"{self.agent_type}_waiters", 1)
            
            for event in events:
                if event.get("event_type") == event_type:
                    return event
            
            await asyncio.sleep(1)
        
        return None
    
    async def wait_for_dependency(self, dependency_agent: str, 
                                 completion_event: str, timeout: int = 300) -> bool:
        """Wait for dependency agent to complete"""
        
        event = await self.wait_for_event(completion_event, timeout)
        return event is not None


# TODO for each agent: Inherit from BaseAgent and implement:
# - initialize(): Agent-specific setup
# - run(): Main processing loop
# - register event handlers for your domain

"""
Example usage for Agent 2 (Homeowner Intake):

class HomeownerIntakeAgent(BaseAgent):
    def __init__(self):
        super().__init__("intake_001", "homeowner_intake")
    
    async def initialize(self):
        # Set up NLP processor
        # Register event handlers
        self.register_event_handler("project_submitted", self.handle_project_submission)
    
    async def run(self):
        await self.start_consuming(["homeowner:projects"], "intake_processors")
    
    async def handle_project_submission(self, event):
        # Process intake data
        # Publish completion event
        pass
"""
