"""
Supabase Client for Instabids Agent Swarm
Provides database operations, real-time subscriptions, and read model management.
"""

import asyncio
import logging
import json
import os
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime
from dataclasses import dataclass

# MCP Integration Pattern
class MCPClient:
    """MCP Tool wrapper for Supabase operations"""
    async def call_tool(self, tool_name: str, args: dict):
        """
        Wrapper for MCP tool calls - will be replaced by actual MCP implementation
        """
        # TODO: Replace with actual MCP calling mechanism in Codex environment
        pass

# Global MCP client instance  
mcp = MCPClient()

@dataclass
class QueryResult:
    """Standard query result structure"""
    data: Any
    error: Optional[str] = None
    count: Optional[int] = None
    status: str = "success"

class SupabaseClient:
    """
    Optimized Supabase client for agent swarm operations
    Provides database operations, real-time subscriptions, and read model management
    """
    
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.getenv("SUPABASE_PROJECT_ID")
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.query_metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "total_latency": 0.0,
            "average_latency": 0.0
        }
        
        # Real-time subscriptions
        self.active_subscriptions = {}
    
    async def initialize_connection(self) -> bool:
        """Initialize Supabase connection and validate credentials"""
        try:
            # Test connection with health check
            health_result = await mcp.call_tool("supabase", {
                "action": "get_health"
            })
            
            if health_result.get("status") != "healthy":
                raise Exception(f"Supabase health check failed: {health_result}")
            
            self.logger.info("✅ Supabase connection initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Supabase connection: {e}")
            return False
    
    async def store_event(self, stream_name: str, event_type: str, 
                         event_data: Dict[str, Any], source_agent_id: str,
                         correlation_id: Optional[str] = None) -> QueryResult:
        """
        Store event in audit trail with automatic indexing
        """
        start_time = datetime.now()
        
        try:
            event_record = {
                "stream_name": stream_name,
                "event_type": event_type,
                "event_data": event_data,
                "source_agent_id": source_agent_id,
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO events (stream_name, event_type, event_data, 
                                      source_agent_id, correlation_id, timestamp)
                    VALUES (%(stream_name)s, %(event_type)s, %(event_data)s, 
                           %(source_agent_id)s, %(correlation_id)s, %(timestamp)s)
                    RETURNING id
                """,
                "params": event_record
            })
            
            self._update_metrics(start_time, success=True)
            
            return QueryResult(
                data=result,
                status="success"
            )
            
        except Exception as e:
            self._update_metrics(start_time, success=False)
            self.logger.error(f"Failed to store event: {e}")
            return QueryResult(
                data=None,
                error=str(e),
                status="error"
            )
    
    async def create_project(self, homeowner_id: str, project_data: Dict[str, Any]) -> QueryResult:
        """Create new project in read model"""
        try:
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO projects (homeowner_id, project_data, status)
                    VALUES (%(homeowner_id)s, %(project_data)s, 'intake')
                    RETURNING id, created_at
                """,
                "params": {
                    "homeowner_id": homeowner_id,
                    "project_data": project_data
                }
            })
            
            return QueryResult(data=result)
            
        except Exception as e:
            self.logger.error(f"Failed to create project: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    async def update_project_status(self, project_id: str, status: str, 
                                   additional_data: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Update project status and data"""
        try:
            # Build update fields
            update_fields = ["status = %(status)s", "updated_at = now()"]
            params = {"project_id": project_id, "status": status}
            
            if additional_data:
                for key, value in additional_data.items():
                    if key in ["intake_complete", "scope_complete", "payment_complete", 
                              "contact_released", "contractors_found", "selected_contractor"]:
                        update_fields.append(f"{key} = %({key})s")
                        params[key] = value
            
            query = f"""
                UPDATE projects 
                SET {', '.join(update_fields)}
                WHERE id = %(project_id)s
                RETURNING id, status, updated_at
            """
            
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": query,
                "params": params
            })
            
            return QueryResult(data=result)
            
        except Exception as e:
            self.logger.error(f"Failed to update project status: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    async def get_project(self, project_id: str) -> QueryResult:
        """Get project by ID with all current data"""
        try:
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    SELECT id, homeowner_id, status, project_data, 
                           intake_complete, scope_complete, contractors_found,
                           selected_contractor, payment_complete, contact_released,
                           created_at, updated_at
                    FROM projects 
                    WHERE id = %(project_id)s
                """,
                "params": {"project_id": project_id}
            })
            
            return QueryResult(data=result)
            
        except Exception as e:
            self.logger.error(f"Failed to get project: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    async def get_projects_by_status(self, status: str, limit: int = 100) -> QueryResult:
        """Get projects by status for agent processing"""
        try:
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql", 
                "query": """
                    SELECT id, homeowner_id, status, project_data, created_at
                    FROM projects 
                    WHERE status = %(status)s
                    ORDER BY created_at ASC
                    LIMIT %(limit)s
                """,
                "params": {"status": status, "limit": limit}
            })
            
            return QueryResult(data=result)
            
        except Exception as e:
            self.logger.error(f"Failed to get projects by status: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    async def log_security_violation(self, user_id: str, violation_type: str,
                                   violation_data: Dict[str, Any], severity: str,
                                   action_taken: str, escalation_level: int = 1) -> QueryResult:
        """Log security violation for contact protection system"""
        try:
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO security_violations 
                    (user_id, violation_type, violation_data, severity, 
                     action_taken, escalation_level, timestamp)
                    VALUES (%(user_id)s, %(violation_type)s, %(violation_data)s, 
                           %(severity)s, %(action_taken)s, %(escalation_level)s, now())
                    RETURNING id, timestamp
                """,
                "params": {
                    "user_id": user_id,
                    "violation_type": violation_type,
                    "violation_data": violation_data,
                    "severity": severity,
                    "action_taken": action_taken,
                    "escalation_level": escalation_level
                }
            })
            
            return QueryResult(data=result)
            
        except Exception as e:
            self.logger.error(f"Failed to log security violation: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    async def get_user_violation_history(self, user_id: str) -> QueryResult:
        """Get user's violation history for escalation decisions"""
        try:
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    SELECT violation_type, severity, action_taken, 
                           escalation_level, timestamp, resolved
                    FROM security_violations 
                    WHERE user_id = %(user_id)s
                    ORDER BY timestamp DESC
                    LIMIT 50
                """,
                "params": {"user_id": user_id}
            })
            
            return QueryResult(data=result)
            
        except Exception as e:
            self.logger.error(f"Failed to get violation history: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    async def get_event_history(self, stream_name: Optional[str] = None,
                               event_type: Optional[str] = None,
                               correlation_id: Optional[str] = None,
                               limit: int = 100) -> QueryResult:
        """Get event history for audit and debugging"""
        try:
            where_conditions = []
            params = {"limit": limit}
            
            if stream_name:
                where_conditions.append("stream_name = %(stream_name)s")
                params["stream_name"] = stream_name
                
            if event_type:
                where_conditions.append("event_type = %(event_type)s")
                params["event_type"] = event_type
                
            if correlation_id:
                where_conditions.append("correlation_id = %(correlation_id)s")
                params["correlation_id"] = correlation_id
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT id, stream_name, event_type, event_data, 
                       source_agent_id, correlation_id, timestamp, created_at
                FROM events 
                {where_clause}
                ORDER BY timestamp DESC
                LIMIT %(limit)s
            """
            
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": query,
                "params": params
            })
            
            return QueryResult(data=result)
            
        except Exception as e:
            self.logger.error(f"Failed to get event history: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    async def create_realtime_subscription(self, table: str, event_types: List[str],
                                         callback: Callable[[Dict[str, Any]], None],
                                         filter_conditions: Optional[Dict[str, Any]] = None) -> str:
        """
        Create real-time subscription for table changes
        Returns: subscription_id
        """
        try:
            import uuid
            subscription_id = str(uuid.uuid4())
            
            # Configure subscription through Supabase realtime
            subscription_config = {
                "table": table,
                "event_types": event_types,  # ['INSERT', 'UPDATE', 'DELETE']
                "callback": callback,
                "filter": filter_conditions
            }
            
            # Store subscription for management
            self.active_subscriptions[subscription_id] = subscription_config
            
            # Set up actual subscription via MCP
            await mcp.call_tool("supabase", {
                "action": "create_subscription",
                "table": table,
                "events": event_types,
                "callback": f"subscription_{subscription_id}"
            })
            
            self.logger.info(f"Created realtime subscription {subscription_id} for table {table}")
            return subscription_id
            
        except Exception as e:
            self.logger.error(f"Failed to create subscription: {e}")
            raise
    
    async def remove_subscription(self, subscription_id: str) -> bool:
        """Remove real-time subscription"""
        try:
            if subscription_id in self.active_subscriptions:
                # Remove via MCP
                await mcp.call_tool("supabase", {
                    "action": "remove_subscription",
                    "subscription_id": subscription_id
                })
                
                # Remove from local tracking
                del self.active_subscriptions[subscription_id]
                
                self.logger.info(f"Removed subscription {subscription_id}")
                return True
            else:
                self.logger.warning(f"Subscription {subscription_id} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to remove subscription: {e}")
            return False
    
    async def execute_migration(self, migration_name: str, sql: str) -> QueryResult:
        """Execute database migration"""
        try:
            result = await mcp.call_tool("supabase", {
                "action": "apply_migration",
                "name": migration_name,
                "query": sql
            })
            
            self.logger.info(f"Successfully executed migration: {migration_name}")
            return QueryResult(data=result)
            
        except Exception as e:
            self.logger.error(f"Failed to execute migration {migration_name}: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    async def get_table_stats(self, table_name: str) -> QueryResult:
        """Get table statistics for monitoring"""
        try:
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": f"""
                    SELECT 
                        schemaname,
                        tablename,
                        attname as column_name,
                        n_distinct,
                        avg_width,
                        null_frac
                    FROM pg_stats 
                    WHERE tablename = %(table_name)s
                """,
                "params": {"table_name": table_name}
            })
            
            # Also get row count
            count_result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": f"SELECT COUNT(*) as row_count FROM {table_name}"
            })
            
            return QueryResult(
                data={
                    "statistics": result,
                    "row_count": count_result[0]["row_count"] if count_result else 0
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get table stats: {e}")
            return QueryResult(data=None, error=str(e), status="error")
    
    def _update_metrics(self, start_time: datetime, success: bool = True):
        """Update query performance metrics"""
        latency = (datetime.now() - start_time).total_seconds()
        
        self.query_metrics["total_queries"] += 1
        self.query_metrics["total_latency"] += latency
        
        if success:
            self.query_metrics["successful_queries"] += 1
        else:
            self.query_metrics["failed_queries"] += 1
        
        # Update average latency
        self.query_metrics["average_latency"] = (
            self.query_metrics["total_latency"] / self.query_metrics["total_queries"]
        )
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get client performance metrics"""
        return {
            **self.query_metrics,
            "success_rate": (
                self.query_metrics["successful_queries"] / 
                max(self.query_metrics["total_queries"], 1)
            ),
            "active_subscriptions": len(self.active_subscriptions),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        try:
            start_time = datetime.now()
            
            # Test basic connectivity
            health_result = await mcp.call_tool("supabase", {
                "action": "get_health"
            })
            
            # Test query performance
            test_query_result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": "SELECT 1 as test"
            })
            
            latency = (datetime.now() - start_time).total_seconds()
            
            return {
                "status": "healthy" if health_result.get("status") == "healthy" else "unhealthy",
                "latency_seconds": latency,
                "supabase_status": health_result.get("status"),
                "query_test": "passed" if test_query_result else "failed",
                "performance_metrics": await self.get_performance_metrics()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

# Global Supabase client instance
supabase_client = SupabaseClient()