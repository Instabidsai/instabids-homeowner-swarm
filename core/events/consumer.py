"""
Redis Streams Event Consumer with MCP Integration
Agent 1 Domain - Core Infrastructure
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from core import mcp


class EventConsumer:
    """Redis Streams consumer with consumer group support and MCP integration"""
    
    def __init__(self, consumer_group: str, consumer_name: str, agent_id: str):
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.agent_id = agent_id
        self.is_running = False
        self.event_handlers = {}
        self.error_handlers = {}
    
    async def start_consuming(self, streams: List[str], count: int = 10, 
                            block_time: int = 1000) -> None:
        """
        Start consuming events from Redis Streams
        
        Args:
            streams: List of stream names to consume from
            count: Maximum number of events to consume per call
            block_time: Milliseconds to block waiting for events
            
        Usage:
            consumer = EventConsumer("intake_processors", "intake_001", "agent_2")
            await consumer.start_consuming(["homeowner:projects"])
        """
        
        self.is_running = True
        
        # Ensure consumer groups exist
        await self._ensure_consumer_groups(streams)
        
        while self.is_running:
            try:
                # Consume events from streams via MCP
                events = await mcp.call_tool("redis", {
                    "command": "xreadgroup",
                    "group": self.consumer_group,
                    "consumer": self.consumer_name,
                    "streams": streams,
                    "count": count,
                    "block": block_time
                })
                
                if events:
                    await self._process_events(events)
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.1)
                
            except Exception as e:
                await self._handle_consumption_error(e)
                # Back off on errors
                await asyncio.sleep(5)
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """
        Register handler function for specific event type
        
        Args:
            event_type: Type of event to handle
            handler: Async function to handle the event
            
        Usage:
            consumer.register_event_handler("project_submitted", handle_project_submission)
        """
        self.event_handlers[event_type] = handler
    
    def register_error_handler(self, error_type: str, handler: Callable):
        """Register error handler for specific error types"""
        self.error_handlers[error_type] = handler
    
    async def consume_events(self, streams: List[str], count: int = 10) -> List[Dict]:
        """
        Consume events once (non-blocking)
        
        Returns:
            List of processed events
        """
        
        try:
            # Consume events via MCP
            events = await mcp.call_tool("redis", {
                "command": "xreadgroup",
                "group": self.consumer_group,
                "consumer": self.consumer_name,
                "streams": streams,
                "count": count
            })
            
            processed_events = []
            
            if events:
                for stream_data in events:
                    stream_name = stream_data[0]
                    stream_events = stream_data[1]
                    
                    for event_id, event_fields in stream_events:
                        processed_event = await self._process_single_event(
                            stream_name, event_id, event_fields
                        )
                        processed_events.append(processed_event)
            
            return processed_events
            
        except Exception as e:
            await self._handle_consumption_error(e)
            return []
    
    async def _process_events(self, events: List) -> None:
        """Process consumed events from Redis Streams"""
        
        for stream_data in events:
            stream_name = stream_data[0]
            stream_events = stream_data[1]
            
            for event_id, event_fields in stream_events:
                try:
                    await self._process_single_event(stream_name, event_id, event_fields)
                    
                    # Acknowledge successful processing
                    await self._acknowledge_event(stream_name, event_id)
                    
                except Exception as e:
                    await self._handle_event_processing_error(
                        stream_name, event_id, event_fields, e
                    )
    
    async def _process_single_event(self, stream_name: str, event_id: str, 
                                  event_fields: Dict) -> Dict:
        """Process a single event from the stream"""
        
        # Parse event data
        event_type = event_fields.get("event_type")
        event_data = event_fields.get("data")
        
        # Parse JSON data if present
        if event_data:
            try:
                event_data = json.loads(event_data)
            except json.JSONDecodeError:
                # Keep as string if not valid JSON
                pass
        
        processed_event = {
            "stream_name": stream_name,
            "event_id": event_id,
            "event_type": event_type,
            "data": event_data,
            "timestamp": event_fields.get("timestamp"),
            "correlation_id": event_fields.get("correlation_id"),
            "processed_by": self.agent_id,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        # Call registered handler if available
        if event_type in self.event_handlers:
            try:
                await self.event_handlers[event_type](processed_event)
            except Exception as e:
                await self._handle_handler_error(event_type, processed_event, e)
        
        # Log event processing
        await self._log_event_processing(processed_event)
        
        return processed_event
    
    async def _ensure_consumer_groups(self, streams: List[str]) -> None:
        """Ensure consumer groups exist for all streams"""
        
        for stream in streams:
            try:
                # Create consumer group if it doesn't exist
                await mcp.call_tool("redis", {
                    "command": "xgroup",
                    "action": "CREATE",
                    "stream": stream,
                    "group": self.consumer_group,
                    "id": "$",
                    "mkstream": True
                })
            except Exception as e:
                # Group might already exist, which is fine
                if "BUSYGROUP" not in str(e):
                    print(f"Warning: Could not create consumer group for {stream}: {e}")
    
    async def _acknowledge_event(self, stream_name: str, event_id: str) -> None:
        """Acknowledge successful event processing"""
        
        try:
            await mcp.call_tool("redis", {
                "command": "xack",
                "stream": stream_name,
                "group": self.consumer_group,
                "id": event_id
            })
        except Exception as e:
            print(f"Warning: Failed to acknowledge event {event_id}: {e}")
    
    async def _log_event_processing(self, event: Dict) -> None:
        """Log event processing for audit trail"""
        
        try:
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO event_processing_log (
                        event_id, stream_name, event_type, consumer_group,
                        consumer_name, agent_id, processed_at, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                "params": [
                    event["event_id"], event["stream_name"], event["event_type"],
                    self.consumer_group, self.consumer_name, self.agent_id,
                    event["processed_at"], "success"
                ]
            })
        except Exception as e:
            print(f"Warning: Failed to log event processing: {e}")
    
    async def _handle_consumption_error(self, error: Exception) -> None:
        """Handle errors during event consumption"""
        
        error_log = {
            "error_type": "consumption_error",
            "error_message": str(error),
            "consumer_group": self.consumer_group,
            "consumer_name": self.consumer_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO consumer_errors (
                        error_type, error_message, consumer_group,
                        consumer_name, timestamp
                    ) VALUES ($1, $2, $3, $4, $5)
                """,
                "params": [
                    error_log["error_type"], error_log["error_message"],
                    error_log["consumer_group"], error_log["consumer_name"],
                    error_log["timestamp"]
                ]
            })
        except Exception as e:
            print(f"Critical: Failed to log consumption error: {e}")
    
    async def _handle_event_processing_error(self, stream_name: str, event_id: str,
                                           event_fields: Dict, error: Exception) -> None:
        """Handle errors during event processing"""
        
        # Log the error
        print(f"Error processing event {event_id} from {stream_name}: {error}")
        
        # Move event to dead letter queue for manual inspection
        await self._move_to_dead_letter_queue(stream_name, event_id, event_fields, error)
    
    async def _move_to_dead_letter_queue(self, stream_name: str, event_id: str,
                                       event_fields: Dict, error: Exception) -> None:
        """Move failed events to dead letter queue"""
        
        dead_letter_event = {
            "original_stream": stream_name,
            "original_event_id": event_id,
            "original_event_fields": json.dumps(event_fields),
            "error_message": str(error),
            "failed_at": datetime.utcnow().isoformat(),
            "consumer_group": self.consumer_group,
            "consumer_name": self.consumer_name
        }
        
        try:
            await mcp.call_tool("redis", {
                "command": "xadd",
                "stream": "dead_letter_queue",
                "fields": dead_letter_event
            })
        except Exception as e:
            print(f"Critical: Failed to move event to dead letter queue: {e}")
    
    async def _handle_handler_error(self, event_type: str, event: Dict, error: Exception) -> None:
        """Handle errors from registered event handlers"""
        
        if "handler_error" in self.error_handlers:
            try:
                await self.error_handlers["handler_error"](event_type, event, error)
            except Exception as e:
                print(f"Error in error handler: {e}")
        else:
            print(f"Handler error for {event_type}: {error}")
    
    def stop_consuming(self) -> None:
        """Stop the consumer loop"""
        self.is_running = False


# Example usage for all agents:
"""
# Agent 2 - Homeowner Intake
consumer = EventConsumer("intake_processors", "intake_001", "agent_2")

async def handle_project_submission(event):
    # Process project submission
    project_data = event["data"]
    # ... processing logic ...

consumer.register_event_handler("project_submitted", handle_project_submission)
await consumer.start_consuming(["homeowner:projects"])
"""
