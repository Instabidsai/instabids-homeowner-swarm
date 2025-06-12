"""
Event Mixin - Shared Event Handling Patterns for Agents

This module provides reusable event handling capabilities that can be mixed
into any agent class, ensuring consistent event processing, error handling,
and coordination patterns across the entire agent swarm.

🔄 CORE: This enables the event-driven architecture that coordinates all
agent activities through Redis Streams.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import uuid

# MCP Integration for event operations
class MCPEventMixin:
    """MCP-integrated event handling for Codex agent usage"""
    
    async def call_mcp_tool(self, tool_name: str, operation: str, params: dict) -> dict:
        """MCP tool interface for event operations"""
        # This will be replaced by actual MCP calling mechanism
        if tool_name == "redis":
            return await self._redis_operation(operation, params)
        elif tool_name == "supabase":
            return await self._supabase_operation(operation, params)
        else:
            raise ValueError(f"Unsupported MCP tool: {tool_name}")
    
    async def _redis_operation(self, operation: str, params: dict) -> dict:
        """Handle Redis MCP operations for event streaming"""
        if operation == "publish_event":
            return {"status": "success", "event_id": f"event_{uuid.uuid4().hex[:8]}"}
        elif operation == "consume_events":
            return {"status": "success", "events": []}
        elif operation == "create_consumer_group":
            return {"status": "success", "group_created": True}
        elif operation == "ack_event":
            return {"status": "success", "acknowledged": True}
        return {"status": "success"}
    
    async def _supabase_operation(self, operation: str, params: dict) -> dict:
        """Handle Supabase MCP operations for event storage"""
        if operation == "store_event":
            return {"status": "success", "stored_id": f"store_{uuid.uuid4().hex[:8]}"}
        elif operation == "query_events":
            return {"status": "success", "events": []}
        return {"status": "success"}


class EventHandlerMixin(MCPEventMixin):
    """
    Mixin class providing event handling capabilities for agents
    
    Features:
    - Event publishing and consumption via Redis Streams
    - Automatic event acknowledgment and error handling
    - Event filtering and routing
    - Retry logic for failed events
    - Health monitoring for event processing
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Event handling configuration
        self.event_config = {
            "max_retries": 3,
            "retry_delay": 5.0,
            "ack_timeout": 30.0,
            "batch_size": 10,
            "consumer_timeout": 5000  # milliseconds
        }
        
        # Event tracking
        self.processed_events = 0
        self.failed_events = 0
        self.last_event_time = None
        
        # Event handlers registry
        self.event_handlers: Dict[str, Callable] = {}
        self.event_filters: List[Callable] = []
        
        # Processing state
        self.is_processing = False
        self.processing_task: Optional[asyncio.Task] = None
        
        # Logging
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
    
    async def publish_event(
        self,
        stream_name: str,
        event_type: str,
        event_data: Dict[str, Any],
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Publish an event to a Redis Stream
        
        Args:
            stream_name: Redis stream to publish to
            event_type: Type identifier for the event
            event_data: Event payload data
            correlation_id: Optional correlation ID for event tracking
            metadata: Additional metadata for the event
            
        Returns:
            str: Event ID for tracking
        """
        try:
            # Generate event ID
            event_id = f"{event_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Build event payload
            event_payload = {
                "event_id": event_id,
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id or str(uuid.uuid4()),
                "agent_id": getattr(self, 'agent_id', 'unknown'),
                "agent_type": getattr(self, 'agent_type', 'unknown'),
                "data": event_data,
                "metadata": metadata or {}
            }
            
            # Publish via MCP
            result = await self.call_mcp_tool("redis", "publish_event", {
                "stream": stream_name,
                "event_type": event_type,
                "payload": event_payload
            })
            
            if result.get("status") == "success":
                self.logger.info(f"Published event {event_id} to {stream_name}")
                
                # Store event in audit trail
                await self.call_mcp_tool("supabase", "store_event", {
                    "table": "event_audit",
                    "event": event_payload
                })
                
                return event_id
            else:
                raise Exception(f"Failed to publish event: {result}")
                
        except Exception as e:
            self.logger.error(f"Error publishing event to {stream_name}: {e}")
            raise
    
    async def consume_events(
        self,
        stream_names: List[str],
        consumer_group: str,
        consumer_name: Optional[str] = None,
        count: int = None,
        timeout: int = None
    ) -> List[Dict[str, Any]]:
        """
        Consume events from Redis Streams
        
        Args:
            stream_names: List of streams to consume from
            consumer_group: Consumer group name
            consumer_name: Consumer name (defaults to agent_id)
            count: Maximum number of events to consume
            timeout: Timeout in milliseconds
            
        Returns:
            List of consumed events
        """
        try:
            consumer_name = consumer_name or getattr(self, 'agent_id', f'consumer_{uuid.uuid4().hex[:8]}')
            count = count or self.event_config["batch_size"]
            timeout = timeout or self.event_config["consumer_timeout"]
            
            # Consume events via MCP
            result = await self.call_mcp_tool("redis", "consume_events", {
                "streams": stream_names,
                "consumer_group": consumer_group,
                "consumer_name": consumer_name,
                "count": count,
                "timeout": timeout
            })
            
            if result.get("status") == "success":
                events = result.get("events", [])
                self.logger.debug(f"Consumed {len(events)} events from {stream_names}")
                return events
            else:
                self.logger.warning(f"No events consumed: {result}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error consuming events from {stream_names}: {e}")
            return []
    
    async def start_event_processing(
        self,
        stream_names: List[str],
        consumer_group: str,
        consumer_name: Optional[str] = None
    ) -> None:
        """
        Start continuous event processing
        
        Args:
            stream_names: Streams to process
            consumer_group: Consumer group for coordination
            consumer_name: Unique consumer name
        """
        if self.is_processing:
            self.logger.warning("Event processing already started")
            return
        
        self.is_processing = True
        consumer_name = consumer_name or getattr(self, 'agent_id', f'consumer_{uuid.uuid4().hex[:8]}')
        
        # Ensure consumer group exists
        for stream in stream_names:
            await self.call_mcp_tool("redis", "create_consumer_group", {
                "stream": stream,
                "group": consumer_group,
                "start_id": "$"
            })
        
        # Start processing task
        self.processing_task = asyncio.create_task(
            self._event_processing_loop(stream_names, consumer_group, consumer_name)
        )
        
        self.logger.info(f"Started event processing for streams: {stream_names}")
    
    async def stop_event_processing(self) -> None:
        """Stop event processing gracefully"""
        if not self.is_processing:
            return
        
        self.is_processing = False
        
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped event processing")
    
    async def _event_processing_loop(
        self,
        stream_names: List[str],
        consumer_group: str,
        consumer_name: str
    ) -> None:
        """Main event processing loop"""
        while self.is_processing:
            try:
                # Consume events
                events = await self.consume_events(
                    stream_names, consumer_group, consumer_name
                )
                
                # Process each event
                for event in events:
                    await self._process_single_event(event, consumer_group)
                
                # Update processing statistics
                self.processed_events += len(events)
                if events:
                    self.last_event_time = datetime.utcnow()
                
                # Small delay if no events to prevent busy waiting
                if not events:
                    await asyncio.sleep(1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in event processing loop: {e}")
                await asyncio.sleep(self.event_config["retry_delay"])
    
    async def _process_single_event(
        self,
        event: Dict[str, Any],
        consumer_group: str
    ) -> None:
        """Process a single event with error handling and retries"""
        event_id = event.get("event_id", "unknown")
        event_type = event.get("event_type", "unknown")
        
        try:
            # Apply event filters
            if not await self._should_process_event(event):
                await self._acknowledge_event(event, consumer_group)
                return
            
            # Route to appropriate handler
            handler = await self._get_event_handler(event_type)
            if handler:
                await handler(event)
            else:
                # Default processing if no specific handler
                await self._default_event_handler(event)
            
            # Acknowledge successful processing
            await self._acknowledge_event(event, consumer_group)
            
            self.logger.debug(f"Successfully processed event {event_id}")
            
        except Exception as e:
            self.failed_events += 1
            self.logger.error(f"Error processing event {event_id}: {e}")
            
            # Handle retry logic
            await self._handle_event_failure(event, consumer_group, e)
    
    async def _should_process_event(self, event: Dict[str, Any]) -> bool:
        """Apply event filters to determine if event should be processed"""
        for filter_func in self.event_filters:
            try:
                if not await filter_func(event):
                    return False
            except Exception as e:
                self.logger.warning(f"Event filter error: {e}")
                # Continue processing on filter error
        
        return True
    
    async def _get_event_handler(self, event_type: str) -> Optional[Callable]:
        """Get registered handler for event type"""
        return self.event_handlers.get(event_type)
    
    async def _default_event_handler(self, event: Dict[str, Any]) -> None:
        """Default event handler - override in implementing classes"""
        # This should be overridden by implementing classes
        self.logger.info(f"Received event: {event.get('event_type')} - {event.get('event_id')}")
    
    async def _acknowledge_event(
        self,
        event: Dict[str, Any],
        consumer_group: str
    ) -> None:
        """Acknowledge event processing completion"""
        try:
            await self.call_mcp_tool("redis", "ack_event", {
                "stream": event.get("stream_name"),
                "group": consumer_group,
                "event_id": event.get("event_id")
            })
        except Exception as e:
            self.logger.error(f"Error acknowledging event: {e}")
    
    async def _handle_event_failure(
        self,
        event: Dict[str, Any],
        consumer_group: str,
        error: Exception
    ) -> None:
        """Handle event processing failures with retry logic"""
        event_id = event.get("event_id", "unknown")
        retry_count = event.get("retry_count", 0)
        
        if retry_count < self.event_config["max_retries"]:
            # Increment retry count and republish
            event["retry_count"] = retry_count + 1
            event["last_error"] = str(error)
            event["retry_timestamp"] = datetime.utcnow().isoformat()
            
            # Add delay before retry
            await asyncio.sleep(self.event_config["retry_delay"] * (retry_count + 1))
            
            # Republish for retry
            await self.publish_event(
                stream_name=event.get("stream_name", "retry:events"),
                event_type=f"retry_{event.get('event_type')}",
                event_data=event
            )
            
            self.logger.warning(f"Retrying event {event_id} (attempt {retry_count + 1})")
        else:
            # Max retries exceeded - send to dead letter queue
            await self._send_to_dead_letter_queue(event, error)
            
            # Acknowledge to prevent reprocessing
            await self._acknowledge_event(event, consumer_group)
    
    async def _send_to_dead_letter_queue(
        self,
        event: Dict[str, Any],
        error: Exception
    ) -> None:
        """Send failed event to dead letter queue for manual investigation"""
        try:
            dead_letter_event = {
                "original_event": event,
                "failure_reason": str(error),
                "failure_timestamp": datetime.utcnow().isoformat(),
                "max_retries_exceeded": True
            }
            
            await self.publish_event(
                stream_name="dead_letter:events",
                event_type="dead_letter",
                event_data=dead_letter_event
            )
            
            self.logger.error(f"Sent event {event.get('event_id')} to dead letter queue")
            
        except Exception as e:
            self.logger.critical(f"Failed to send event to dead letter queue: {e}")
    
    def register_event_handler(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register a handler for specific event types"""
        self.event_handlers[event_type] = handler
        self.logger.info(f"Registered handler for event type: {event_type}")
    
    def add_event_filter(self, filter_func: Callable[[Dict[str, Any]], bool]) -> None:
        """Add an event filter function"""
        self.event_filters.append(filter_func)
        self.logger.info("Added event filter")
    
    def get_event_processing_stats(self) -> Dict[str, Any]:
        """Get event processing statistics"""
        return {
            "processed_events": self.processed_events,
            "failed_events": self.failed_events,
            "success_rate": (
                (self.processed_events - self.failed_events) / max(self.processed_events, 1)
            ) * 100,
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
            "is_processing": self.is_processing,
            "registered_handlers": list(self.event_handlers.keys()),
            "filter_count": len(self.event_filters)
        }


class EventPatterns:
    """Common event patterns and utilities"""
    
    @staticmethod
    async def create_event_filter_by_type(allowed_types: List[str]) -> Callable:
        """Create filter that only allows specific event types"""
        async def type_filter(event: Dict[str, Any]) -> bool:
            return event.get("event_type") in allowed_types
        return type_filter
    
    @staticmethod
    async def create_event_filter_by_agent(allowed_agents: List[str]) -> Callable:
        """Create filter that only allows events from specific agents"""
        async def agent_filter(event: Dict[str, Any]) -> bool:
            return event.get("agent_id") in allowed_agents
        return agent_filter
    
    @staticmethod
    async def create_correlation_filter(correlation_id: str) -> Callable:
        """Create filter for events with specific correlation ID"""
        async def correlation_filter(event: Dict[str, Any]) -> bool:
            return event.get("correlation_id") == correlation_id
        return correlation_filter
    
    @staticmethod
    def create_retry_handler(max_retries: int = 3, delay: float = 5.0) -> Callable:
        """Create a retry handler for failed operations"""
        async def retry_handler(operation: Callable, *args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await operation(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(delay * (attempt + 1))
        return retry_handler


# Example usage for agents
class SampleEventHandler(EventHandlerMixin):
    """Example implementation of event handling mixin"""
    
    def __init__(self, agent_id: str):
        super().__init__()
        self.agent_id = agent_id
        self.agent_type = "sample_agent"
        
        # Register event handlers
        self.register_event_handler("project_created", self.handle_project_created)
        self.register_event_handler("contact_violation", self.handle_contact_violation)
        
        # Add event filters
        self.add_event_filter(
            lambda event: event.get("agent_id") != self.agent_id  # Don't process own events
        )
    
    async def handle_project_created(self, event: Dict[str, Any]) -> None:
        """Handle project creation events"""
        project_id = event.get("data", {}).get("project_id")
        self.logger.info(f"Processing project creation: {project_id}")
        
        # Process the project creation
        # ...
        
        # Publish downstream event
        await self.publish_event(
            stream_name="project:processing",
            event_type="project_accepted",
            event_data={"project_id": project_id, "processor": self.agent_id}
        )
    
    async def handle_contact_violation(self, event: Dict[str, Any]) -> None:
        """Handle security violations"""
        violation_data = event.get("data", {})
        self.logger.warning(f"Security violation detected: {violation_data}")
        
        # Process violation
        # ...
