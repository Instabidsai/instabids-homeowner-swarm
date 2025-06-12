"""
Redis Streams Coordinator for Instabids Agent Swarm
Manages stream creation, consumer groups, and agent coordination.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

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

class StreamCoordinator:
    """
    Coordinates Redis Streams for agent swarm communication
    Manages stream creation, consumer groups, and health monitoring
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        # Use environment variable for Redis connection
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.logger = logging.getLogger(__name__)
        
        # Stream definitions for agent coordination
        self.stream_definitions = {
            # Homeowner Journey Streams
            "homeowner:projects": {
                "description": "Project submissions and updates",
                "consumer_groups": ["intake_processors", "scope_processors", "security_filters"]
            },
            "homeowner:intake_complete": {
                "description": "Completed intake processing",
                "consumer_groups": ["scope_processors", "ui_updaters"]
            },
            "homeowner:scope_complete": {
                "description": "Completed project scoping",
                "consumer_groups": ["contractor_matchers", "ui_updaters"]
            },
            
            # Security and Monitoring Streams
            "security:violations": {
                "description": "Security violation events",
                "consumer_groups": ["violation_processors", "audit_loggers"]
            },
            "security:contact_blocked": {
                "description": "Blocked contact information attempts", 
                "consumer_groups": ["escalation_handlers", "audit_loggers"]
            },
            
            # Agent Coordination Streams
            "agent:heartbeats": {
                "description": "Agent health and activity monitoring",
                "consumer_groups": ["ui_consumers", "health_monitors"]
            },
            "agent:errors": {
                "description": "Agent error reporting",
                "consumer_groups": ["error_handlers", "alert_managers"]
            },
            
            # Payment Streams
            "payment:required": {
                "description": "Payment requirements for contractors",
                "consumer_groups": ["payment_processors", "notification_senders"]
            },
            "payment:complete": {
                "description": "Completed payments",
                "consumer_groups": ["contact_releasers", "revenue_trackers"]
            },
            
            # System Streams
            "system:cost_control": {
                "description": "Cost monitoring and circuit breaker events",
                "consumer_groups": ["cost_monitors", "circuit_breakers"]
            },
            "system:audit": {
                "description": "Complete audit trail",
                "consumer_groups": ["audit_processors", "compliance_checkers"]
            }
        }
    
    async def initialize_streams(self) -> Dict[str, bool]:
        """
        Initialize all required streams and consumer groups
        Returns: Dict of stream_name -> success_status
        """
        self.logger.info("Initializing Redis Streams infrastructure...")
        results = {}
        
        for stream_name, config in self.stream_definitions.items():
            try:
                # Create stream if it doesn't exist
                await self._create_stream_if_not_exists(stream_name)
                
                # Create consumer groups
                for group_name in config["consumer_groups"]:
                    await self._create_consumer_group(stream_name, group_name)
                
                results[stream_name] = True
                self.logger.info(f"✅ Stream {stream_name} initialized with {len(config['consumer_groups'])} consumer groups")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize stream {stream_name}: {e}")
                results[stream_name] = False
        
        return results
    
    async def _create_stream_if_not_exists(self, stream_name: str) -> bool:
        """Create stream if it doesn't exist using MCP Redis tool"""
        try:
            # Check if stream exists
            stream_info = await mcp.call_tool("redis", {
                "command": "exists",
                "key": stream_name
            })
            
            if not stream_info:
                # Create stream with initial message
                await mcp.call_tool("redis", {
                    "command": "xadd",
                    "stream": stream_name,
                    "fields": {
                        "event_type": "stream_created",
                        "timestamp": datetime.utcnow().isoformat(),
                        "created_by": "stream_coordinator"
                    }
                })
                self.logger.info(f"Created stream: {stream_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create stream {stream_name}: {e}")
            return False
    
    async def _create_consumer_group(self, stream_name: str, group_name: str) -> bool:
        """Create consumer group using MCP Redis tool"""
        try:
            await mcp.call_tool("redis", {
                "command": "xgroup",
                "subcommand": "create",
                "stream": stream_name,
                "group": group_name,
                "id": "$",
                "mkstream": True
            })
            
            self.logger.info(f"Created consumer group: {group_name} for stream: {stream_name}")
            return True
            
        except Exception as e:
            # Group might already exist - that's okay
            if "BUSYGROUP" in str(e):
                self.logger.debug(f"Consumer group {group_name} already exists for {stream_name}")
                return True
            else:
                self.logger.error(f"Failed to create consumer group {group_name}: {e}")
                return False
    
    async def get_stream_health(self) -> Dict[str, Any]:
        """
        Get health status of all streams
        Returns comprehensive health information
        """
        health_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "streams": {},
            "overall_status": "healthy"
        }
        
        for stream_name in self.stream_definitions.keys():
            try:
                # Get stream info using MCP
                stream_info = await mcp.call_tool("redis", {
                    "command": "xinfo",
                    "subcommand": "stream",
                    "key": stream_name
                })
                
                # Get consumer group info
                group_info = await mcp.call_tool("redis", {
                    "command": "xinfo",
                    "subcommand": "groups",
                    "key": stream_name
                })
                
                health_data["streams"][stream_name] = {
                    "length": stream_info.get("length", 0),
                    "last_generated_id": stream_info.get("last-generated-id"),
                    "consumer_groups": len(group_info) if group_info else 0,
                    "status": "healthy"
                }
                
            except Exception as e:
                health_data["streams"][stream_name] = {
                    "status": "error",
                    "error": str(e)
                }
                health_data["overall_status"] = "degraded"
        
        return health_data
    
    async def cleanup_old_events(self, retention_hours: int = 24) -> Dict[str, int]:
        """
        Clean up old events from streams to manage memory
        Returns: Dict of stream_name -> events_removed
        """
        cutoff_timestamp = datetime.utcnow() - timedelta(hours=retention_hours)
        cutoff_ms = int(cutoff_timestamp.timestamp() * 1000)
        
        cleanup_results = {}
        
        for stream_name in self.stream_definitions.keys():
            try:
                # Trim stream to remove old events
                result = await mcp.call_tool("redis", {
                    "command": "xtrim", 
                    "key": stream_name,
                    "strategy": "MINID",
                    "threshold": f"{cutoff_ms}-0"
                })
                
                cleanup_results[stream_name] = result if result else 0
                
            except Exception as e:
                self.logger.error(f"Failed to cleanup stream {stream_name}: {e}")
                cleanup_results[stream_name] = -1
        
        return cleanup_results
    
    async def monitor_agent_activity(self) -> Dict[str, Any]:
        """
        Monitor agent activity across all streams
        Returns activity metrics and alerts
        """
        activity_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "active_agents": [],
            "stream_activity": {},
            "alerts": []
        }
        
        # Check agent heartbeat stream
        try:
            # Get recent heartbeats (last 5 minutes)
            five_min_ago = int((datetime.utcnow() - timedelta(minutes=5)).timestamp() * 1000)
            
            heartbeats = await mcp.call_tool("redis", {
                "command": "xrange",
                "key": "agent:heartbeats",
                "start": f"{five_min_ago}-0",
                "end": "+"
            })
            
            if heartbeats:
                for heartbeat in heartbeats:
                    agent_id = heartbeat[1].get("source_agent_id")
                    if agent_id and agent_id not in activity_data["active_agents"]:
                        activity_data["active_agents"].append(agent_id)
            
            # Check for inactive agents
            if len(activity_data["active_agents"]) < 3:  # Expecting at least 3 active agents
                activity_data["alerts"].append({
                    "type": "low_agent_activity",
                    "message": f"Only {len(activity_data['active_agents'])} agents active",
                    "severity": "warning"
                })
        
        except Exception as e:
            activity_data["alerts"].append({
                "type": "monitoring_error",
                "message": f"Failed to monitor agent activity: {e}",
                "severity": "error"
            })
        
        return activity_data
    
    async def get_stream_metrics(self) -> Dict[str, Any]:
        """
        Get detailed metrics for all streams
        """
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_streams": len(self.stream_definitions),
            "stream_details": {},
            "system_health": "healthy"
        }
        
        for stream_name in self.stream_definitions.keys():
            try:
                # Get stream length and recent activity
                stream_len = await mcp.call_tool("redis", {
                    "command": "xlen",
                    "key": stream_name
                })
                
                # Get recent events (last hour)
                one_hour_ago = int((datetime.utcnow() - timedelta(hours=1)).timestamp() * 1000)
                recent_events = await mcp.call_tool("redis", {
                    "command": "xrange",
                    "key": stream_name,
                    "start": f"{one_hour_ago}-0",
                    "end": "+",
                    "count": 1000
                })
                
                metrics["stream_details"][stream_name] = {
                    "total_events": stream_len or 0,
                    "recent_events_1h": len(recent_events) if recent_events else 0,
                    "events_per_minute": (len(recent_events) / 60) if recent_events else 0
                }
                
            except Exception as e:
                metrics["stream_details"][stream_name] = {
                    "error": str(e),
                    "status": "error"
                }
                metrics["system_health"] = "degraded"
        
        return metrics

# Global coordinator instance
stream_coordinator = StreamCoordinator()