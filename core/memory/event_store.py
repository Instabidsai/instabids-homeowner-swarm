"""
Event Store Implementation for Instabids Agent Swarm
Manages complete audit trail and event sourcing capabilities.
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Iterator
from datetime import datetime, timedelta
from dataclasses import dataclass
from .redis_client import redis_client
from .supabase_client import supabase_client, QueryResult

@dataclass
class EventRecord:
    """Complete event record with metadata"""
    id: str
    stream_name: str
    event_type: str
    event_data: Dict[str, Any]
    source_agent_id: str
    correlation_id: Optional[str]
    timestamp: datetime
    stored_in_redis: bool = False
    stored_in_supabase: bool = False

class EventStore:
    """
    Complete event store implementation with dual storage
    Manages event persistence, replay, and audit capabilities
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis = redis_client
        self.supabase = supabase_client
        
        # Event store configuration
        self.redis_retention_hours = 24  # Keep events in Redis for 24 hours
        self.batch_size = 100  # Batch size for bulk operations
        
        # Performance tracking
        self.store_metrics = {
            "events_stored": 0,
            "events_retrieved": 0,
            "redis_operations": 0,
            "supabase_operations": 0,
            "errors": 0
        }
    
    async def store_event(self, stream_name: str, event_type: str,
                         event_data: Dict[str, Any], source_agent_id: str,
                         correlation_id: Optional[str] = None) -> EventRecord:
        """
        Store event in both Redis (real-time) and Supabase (persistent)
        Implements write-through pattern for consistency
        """
        import uuid
        
        try:
            # Create event record
            event_id = str(uuid.uuid4())
            timestamp = datetime.utcnow()
            
            event_record = EventRecord(
                id=event_id,
                stream_name=stream_name,
                event_type=event_type,
                event_data=event_data,
                source_agent_id=source_agent_id,
                correlation_id=correlation_id or str(uuid.uuid4()),
                timestamp=timestamp
            )
            
            # Store in Redis first (real-time access)
            redis_success = await self._store_in_redis(event_record)
            event_record.stored_in_redis = redis_success
            
            # Store in Supabase (persistent audit trail)
            supabase_success = await self._store_in_supabase(event_record)
            event_record.stored_in_supabase = supabase_success
            
            # Update metrics
            self.store_metrics["events_stored"] += 1
            if redis_success:
                self.store_metrics["redis_operations"] += 1
            if supabase_success:
                self.store_metrics["supabase_operations"] += 1
            
            self.logger.debug(f"Stored event {event_id} in stream {stream_name}")
            return event_record
            
        except Exception as e:
            self.store_metrics["errors"] += 1
            self.logger.error(f"Failed to store event: {e}")
            raise
    
    async def _store_in_redis(self, event: EventRecord) -> bool:
        """Store event in Redis Stream"""
        try:
            event_data = {
                "event_id": event.id,
                "event_type": event.event_type,
                "event_data": json.dumps(event.event_data),
                "source_agent_id": event.source_agent_id,
                "correlation_id": event.correlation_id,
                "timestamp": event.timestamp.isoformat()
            }
            
            event_id = await self.redis.publish_event(event.stream_name, event_data)
            return bool(event_id)
            
        except Exception as e:
            self.logger.error(f"Failed to store event in Redis: {e}")
            return False
    
    async def _store_in_supabase(self, event: EventRecord) -> bool:
        """Store event in Supabase for persistent audit trail"""
        try:
            result = await self.supabase.store_event(
                stream_name=event.stream_name,
                event_type=event.event_type,
                event_data=event.event_data,
                source_agent_id=event.source_agent_id,
                correlation_id=event.correlation_id
            )
            
            return result.status == "success"
            
        except Exception as e:
            self.logger.error(f"Failed to store event in Supabase: {e}")
            return False
    
    async def get_events(self, stream_name: str, limit: int = 100,
                        since_timestamp: Optional[datetime] = None) -> List[EventRecord]:
        """
        Get events from stream, trying Redis first then Supabase
        """
        try:
            # Try Redis first for recent events
            redis_events = await self._get_from_redis(stream_name, limit, since_timestamp)
            
            if redis_events and len(redis_events) >= limit:
                return redis_events
            
            # Fallback to Supabase for older events
            supabase_events = await self._get_from_supabase(stream_name, limit, since_timestamp)
            
            # Combine and deduplicate
            all_events = redis_events + supabase_events
            unique_events = self._deduplicate_events(all_events)
            
            # Sort by timestamp and limit
            unique_events.sort(key=lambda e: e.timestamp, reverse=True)
            return unique_events[:limit]
            
        except Exception as e:
            self.logger.error(f"Failed to get events: {e}")
            return []
    
    async def _get_from_redis(self, stream_name: str, limit: int,
                             since_timestamp: Optional[datetime] = None) -> List[EventRecord]:
        """Get events from Redis Stream"""
        try:
            # Calculate start timestamp for Redis
            start_timestamp = since_timestamp or (datetime.utcnow() - timedelta(hours=self.redis_retention_hours))
            start_ms = int(start_timestamp.timestamp() * 1000)
            
            # Get stream info
            stream_info = await self.redis.get_stream_info(stream_name)
            if not stream_info:
                return []
            
            # Read events from stream
            events_data = await self.redis.mcp.call_tool("redis", {
                "command": "xrange",
                "key": stream_name,
                "start": f"{start_ms}-0",
                "end": "+",
                "count": limit
            })
            
            # Convert to EventRecord objects
            events = []
            for event_data in events_data or []:
                event_id = event_data[0]
                fields = event_data[1]
                
                event_record = EventRecord(
                    id=fields.get("event_id", event_id),
                    stream_name=stream_name,
                    event_type=fields.get("event_type", "unknown"),
                    event_data=json.loads(fields.get("event_data", "{}")),
                    source_agent_id=fields.get("source_agent_id", "unknown"),
                    correlation_id=fields.get("correlation_id"),
                    timestamp=datetime.fromisoformat(fields.get("timestamp", datetime.utcnow().isoformat())),
                    stored_in_redis=True
                )
                events.append(event_record)
            
            self.store_metrics["events_retrieved"] += len(events)
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to get events from Redis: {e}")
            return []
    
    async def _get_from_supabase(self, stream_name: str, limit: int,
                                since_timestamp: Optional[datetime] = None) -> List[EventRecord]:
        """Get events from Supabase"""
        try:
            # Query Supabase for events
            result = await self.supabase.get_event_history(
                stream_name=stream_name,
                limit=limit
            )
            
            if result.status != "success" or not result.data:
                return []
            
            # Convert to EventRecord objects
            events = []
            for row in result.data:
                event_record = EventRecord(
                    id=row["id"],
                    stream_name=row["stream_name"],
                    event_type=row["event_type"],
                    event_data=row["event_data"],
                    source_agent_id=row["source_agent_id"],
                    correlation_id=row["correlation_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    stored_in_supabase=True
                )
                
                # Filter by timestamp if specified
                if since_timestamp and event_record.timestamp < since_timestamp:
                    continue
                    
                events.append(event_record)
            
            self.store_metrics["events_retrieved"] += len(events)
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to get events from Supabase: {e}")
            return []
    
    def _deduplicate_events(self, events: List[EventRecord]) -> List[EventRecord]:
        """Remove duplicate events based on event ID"""
        seen_ids = set()
        unique_events = []
        
        for event in events:
            if event.id not in seen_ids:
                seen_ids.add(event.id)
                unique_events.append(event)
        
        return unique_events
    
    async def get_events_by_correlation(self, correlation_id: str) -> List[EventRecord]:
        """Get all events for a specific correlation ID (business transaction)"""
        try:
            # Check Supabase for complete correlation chain
            result = await self.supabase.get_event_history(
                correlation_id=correlation_id,
                limit=1000  # High limit for complete transaction
            )
            
            if result.status != "success":
                return []
            
            events = []
            for row in result.data or []:
                event_record = EventRecord(
                    id=row["id"],
                    stream_name=row["stream_name"],
                    event_type=row["event_type"],
                    event_data=row["event_data"],
                    source_agent_id=row["source_agent_id"],
                    correlation_id=row["correlation_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    stored_in_supabase=True
                )
                events.append(event_record)
            
            # Sort by timestamp for transaction order
            events.sort(key=lambda e: e.timestamp)
            return events
            
        except Exception as e:
            self.logger.error(f"Failed to get events by correlation: {e}")
            return []
    
    async def replay_events(self, stream_name: str, 
                           since_timestamp: Optional[datetime] = None,
                           event_processor: Optional[callable] = None) -> int:
        """
        Replay events from stream for event sourcing
        Returns: Number of events replayed
        """
        try:
            events = await self.get_events(stream_name, limit=10000, since_timestamp=since_timestamp)
            replayed_count = 0
            
            for event in events:
                if event_processor:
                    try:
                        await event_processor(event)
                        replayed_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to process event {event.id}: {e}")
                else:
                    self.logger.info(f"Replaying event: {event.event_type} from {event.source_agent_id}")
                    replayed_count += 1
            
            self.logger.info(f"Replayed {replayed_count} events from stream {stream_name}")
            return replayed_count
            
        except Exception as e:
            self.logger.error(f"Failed to replay events: {e}")
            return 0
    
    async def archive_old_redis_events(self) -> Dict[str, int]:
        """
        Archive old events from Redis to free memory
        Events are already in Supabase for permanent storage
        """
        try:
            # Get all stream names from Redis
            stream_pattern = "*:*"  # Match all streams
            stream_keys = await self.redis.mcp.call_tool("redis", {
                "command": "keys",
                "pattern": stream_pattern
            })
            
            archive_results = {}
            cutoff_time = datetime.utcnow() - timedelta(hours=self.redis_retention_hours)
            cutoff_ms = int(cutoff_time.timestamp() * 1000)
            
            for stream_name in stream_keys or []:
                try:
                    # Trim old events from stream
                    trimmed = await self.redis.cleanup_processed_events(stream_name, retention_count=1000)
                    archive_results[stream_name] = trimmed
                    
                except Exception as e:
                    self.logger.error(f"Failed to archive stream {stream_name}: {e}")
                    archive_results[stream_name] = -1
            
            self.logger.info(f"Archived events from {len(archive_results)} streams")
            return archive_results
            
        except Exception as e:
            self.logger.error(f"Failed to archive Redis events: {e}")
            return {}
    
    async def get_store_health(self) -> Dict[str, Any]:
        """Get event store health and performance metrics"""
        try:
            redis_health = await self.redis.health_check()
            supabase_health = await self.supabase.health_check()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": "healthy" if (
                    redis_health.get("status") == "healthy" and 
                    supabase_health.get("status") == "healthy"
                ) else "degraded",
                "redis_tier": redis_health,
                "supabase_tier": supabase_health,
                "store_metrics": self.store_metrics,
                "redis_retention_hours": self.redis_retention_hours
            }
            
        except Exception as e:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": "error",
                "error": str(e)
            }

# Global event store instance
event_store = EventStore()