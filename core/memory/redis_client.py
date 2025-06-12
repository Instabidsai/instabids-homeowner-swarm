"""
Redis Client for Instabids Agent Swarm
Provides optimized Redis operations with connection pooling and MCP integration.
"""

import asyncio
import logging
import json
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from contextlib import asynccontextmanager

# MCP Integration Pattern
class MCPClient:
    """MCP Tool wrapper for Redis operations"""
    async def call_tool(self, tool_name: str, args: dict):
        """
        Wrapper for MCP tool calls - will be replaced by actual MCP implementation
        """
        # TODO: Replace with actual MCP calling mechanism in Codex environment
        pass

# Global MCP client instance
mcp = MCPClient()

class RedisClient:
    """
    Optimized Redis client for agent swarm operations
    Provides connection pooling, retry logic, and performance monitoring
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.logger = logging.getLogger(__name__)
        self.connection_pool = None
        self.performance_metrics = {
            "operations_count": 0,
            "total_latency": 0,
            "error_count": 0,
            "last_health_check": None
        }
    
    async def initialize_connection_pool(self) -> bool:
        """Initialize Redis connection pool for optimal performance"""
        try:
            # Test connection
            ping_result = await mcp.call_tool("redis", {
                "command": "ping"
            })
            
            if ping_result != "PONG":
                raise Exception(f"Redis connection failed: {ping_result}")
            
            # Configure connection pool settings via Redis CONFIG
            pool_settings = {
                "tcp-keepalive": "60",
                "timeout": "30",
                "tcp-backlog": "511"
            }
            
            for setting, value in pool_settings.items():
                await mcp.call_tool("redis", {
                    "command": "config",
                    "subcommand": "set", 
                    "parameter": setting,
                    "value": value
                })
            
            self.logger.info("✅ Redis connection pool initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Redis pool: {e}")
            return False
    
    async def publish_event(self, stream: str, event_data: Dict[str, Any]) -> str:
        """
        Publish event to Redis Stream with performance tracking
        Returns: Event ID
        """
        start_time = datetime.now()
        
        try:
            # Validate event data
            if not isinstance(event_data, dict):
                raise ValueError("Event data must be a dictionary")
            
            # Add metadata
            enriched_event = {
                **event_data,
                "published_at": datetime.utcnow().isoformat(),
                "published_by": "redis_client"
            }
            
            # Publish to stream using MCP
            event_id = await mcp.call_tool("redis", {
                "command": "xadd",
                "stream": stream,
                "fields": enriched_event
            })
            
            # Track performance
            latency = (datetime.now() - start_time).total_seconds()
            self._update_performance_metrics(latency, success=True)
            
            self.logger.debug(f"Published event {event_id} to stream {stream}")
            return event_id
            
        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds()
            self._update_performance_metrics(latency, success=False)
            self.logger.error(f"Failed to publish event to {stream}: {e}")
            raise
    
    async def consume_events(self, streams: List[str], consumer_group: str, 
                           consumer_name: str, count: int = 10) -> List[Dict[str, Any]]:
        """
        Consume events from multiple streams with automatic acknowledgment
        """
        try:
            # Consume from multiple streams
            events = await mcp.call_tool("redis", {
                "command": "xreadgroup",
                "group": consumer_group,
                "consumer": consumer_name,
                "count": count,
                "streams": streams,
                "ids": [">"] * len(streams)  # Use ">" for all streams
            })
            
            if not events:
                return []
            
            processed_events = []
            
            # Process events from all streams
            for stream_data in events:
                stream_name = stream_data[0]
                stream_events = stream_data[1]
                
                for event in stream_events:
                    event_id = event[0]
                    event_fields = event[1]
                    
                    processed_event = {
                        "stream": stream_name,
                        "event_id": event_id,
                        "data": event_fields,
                        "consumed_at": datetime.utcnow().isoformat()
                    }
                    
                    processed_events.append(processed_event)
                    
                    # Acknowledge event
                    await self.acknowledge_event(stream_name, consumer_group, event_id)
            
            return processed_events
            
        except Exception as e:
            self.logger.error(f"Failed to consume events: {e}")
            return []
    
    async def acknowledge_event(self, stream: str, consumer_group: str, event_id: str) -> bool:
        """Acknowledge processed event"""
        try:
            await mcp.call_tool("redis", {
                "command": "xack",
                "key": stream,
                "group": consumer_group,
                "id": event_id
            })
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to acknowledge event {event_id}: {e}")
            return False
    
    async def set_with_expiry(self, key: str, value: Any, expiry_seconds: int = 3600) -> bool:
        """Set key with automatic expiry"""
        try:
            # Serialize complex objects
            if not isinstance(value, (str, int, float)):
                value = json.dumps(value)
            
            await mcp.call_tool("redis", {
                "command": "setex",
                "key": key,
                "seconds": expiry_seconds,
                "value": value
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set key {key}: {e}")
            return False
    
    async def get_with_default(self, key: str, default: Any = None) -> Any:
        """Get key value with default fallback"""
        try:
            value = await mcp.call_tool("redis", {
                "command": "get",
                "key": key
            })
            
            if value is None:
                return default
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except Exception as e:
            self.logger.error(f"Failed to get key {key}: {e}")
            return default
    
    async def hash_set_multiple(self, hash_key: str, fields: Dict[str, Any]) -> bool:
        """Set multiple fields in a hash"""
        try:
            # Serialize complex values
            serialized_fields = {}
            for field, value in fields.items():
                if not isinstance(value, (str, int, float)):
                    serialized_fields[field] = json.dumps(value)
                else:
                    serialized_fields[field] = value
            
            await mcp.call_tool("redis", {
                "command": "hmset",
                "key": hash_key,
                "fields": serialized_fields
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set hash fields for {hash_key}: {e}")
            return False
    
    async def hash_get_all(self, hash_key: str) -> Dict[str, Any]:
        """Get all fields from a hash"""
        try:
            fields = await mcp.call_tool("redis", {
                "command": "hgetall",
                "key": hash_key
            })
            
            if not fields:
                return {}
            
            # Deserialize JSON values
            deserialized = {}
            for field, value in fields.items():
                try:
                    deserialized[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    deserialized[field] = value
            
            return deserialized
            
        except Exception as e:
            self.logger.error(f"Failed to get hash {hash_key}: {e}")
            return {}
    
    async def increment_counter(self, key: str, amount: int = 1) -> int:
        """Atomic counter increment"""
        try:
            result = await mcp.call_tool("redis", {
                "command": "incrby",
                "key": key,
                "increment": amount
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to increment counter {key}: {e}")
            return 0
    
    async def acquire_lock(self, lock_key: str, timeout_seconds: int = 30) -> bool:
        """Acquire distributed lock with timeout"""
        try:
            # Use SET with NX (not exists) and EX (expiry)
            result = await mcp.call_tool("redis", {
                "command": "set",
                "key": f"lock:{lock_key}",
                "value": datetime.utcnow().isoformat(),
                "nx": True,  # Only set if not exists
                "ex": timeout_seconds  # Expiry in seconds
            })
            
            return result == "OK"
            
        except Exception as e:
            self.logger.error(f"Failed to acquire lock {lock_key}: {e}")
            return False
    
    async def release_lock(self, lock_key: str) -> bool:
        """Release distributed lock"""
        try:
            await mcp.call_tool("redis", {
                "command": "del",
                "key": f"lock:{lock_key}"
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to release lock {lock_key}: {e}")
            return False
    
    @asynccontextmanager
    async def distributed_lock(self, lock_key: str, timeout_seconds: int = 30):
        """Context manager for distributed locks"""
        acquired = await self.acquire_lock(lock_key, timeout_seconds)
        
        if not acquired:
            raise Exception(f"Failed to acquire lock: {lock_key}")
        
        try:
            yield
        finally:
            await self.release_lock(lock_key)
    
    async def get_stream_info(self, stream: str) -> Dict[str, Any]:
        """Get detailed stream information"""
        try:
            info = await mcp.call_tool("redis", {
                "command": "xinfo",
                "subcommand": "stream",
                "key": stream
            })
            
            return info or {}
            
        except Exception as e:
            self.logger.error(f"Failed to get stream info for {stream}: {e}")
            return {}
    
    async def cleanup_processed_events(self, stream: str, retention_count: int = 1000) -> int:
        """Clean up processed events from stream"""
        try:
            # Trim stream to keep only recent events
            trimmed = await mcp.call_tool("redis", {
                "command": "xtrim",
                "key": stream,
                "strategy": "MAXLEN",
                "threshold": retention_count,
                "approximate": True
            })
            
            return trimmed or 0
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup stream {stream}: {e}")
            return 0
    
    def _update_performance_metrics(self, latency: float, success: bool = True):
        """Update internal performance metrics"""
        self.performance_metrics["operations_count"] += 1
        self.performance_metrics["total_latency"] += latency
        
        if not success:
            self.performance_metrics["error_count"] += 1
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get client performance metrics"""
        ops_count = self.performance_metrics["operations_count"]
        avg_latency = (
            self.performance_metrics["total_latency"] / ops_count 
            if ops_count > 0 else 0
        )
        
        return {
            "operations_count": ops_count,
            "average_latency_seconds": avg_latency,
            "error_count": self.performance_metrics["error_count"],
            "error_rate": (
                self.performance_metrics["error_count"] / ops_count 
                if ops_count > 0 else 0
            ),
            "last_health_check": self.performance_metrics["last_health_check"]
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        try:
            start_time = datetime.now()
            
            # Basic connectivity
            ping_result = await mcp.call_tool("redis", {"command": "ping"})
            
            # Get Redis info
            info = await mcp.call_tool("redis", {
                "command": "info",
                "section": "server"
            })
            
            latency = (datetime.now() - start_time).total_seconds()
            self.performance_metrics["last_health_check"] = datetime.utcnow().isoformat()
            
            return {
                "status": "healthy" if ping_result == "PONG" else "unhealthy",
                "latency_seconds": latency,
                "redis_version": info.get("redis_version"),
                "uptime_seconds": info.get("uptime_in_seconds"),
                "performance_metrics": await self.get_performance_metrics()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

# Global Redis client instance
redis_client = RedisClient()