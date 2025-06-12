"""
Cost Circuit Breaker - Critical Business Model Protection

This module prevents runaway AI costs and protects the business model from
financial exposure. It implements multiple layers of cost control including
per-event limits, daily limits, and emergency shutdown capabilities.

🚨 CRITICAL: This is core business model protection - any failure here could
result in catastrophic financial loss.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import json

# MCP Integration for cost monitoring
class MCPCostBreaker:
    """MCP-integrated cost circuit breaker for Codex agent usage"""
    
    async def call_mcp_tool(self, tool_name: str, operation: str, params: dict) -> dict:
        """MCP tool interface for cost monitoring operations"""
        # This will be replaced by actual MCP calling mechanism
        if tool_name == "redis":
            return await self._redis_operation(operation, params)
        elif tool_name == "supabase":
            return await self._supabase_operation(operation, params)
        else:
            raise ValueError(f"Unsupported MCP tool: {tool_name}")
    
    async def _redis_operation(self, operation: str, params: dict) -> dict:
        """Handle Redis MCP operations"""
        # Cost tracking operations
        if operation == "increment_cost":
            return {"status": "success", "new_total": params.get("amount", 0)}
        elif operation == "get_daily_cost":
            return {"status": "success", "daily_cost": 125.45}
        return {"status": "success"}
    
    async def _supabase_operation(self, operation: str, params: dict) -> dict:
        """Handle Supabase MCP operations"""
        # Cost logging operations
        if operation == "log_cost_event":
            return {"status": "success", "log_id": "cost_log_123"}
        elif operation == "get_cost_history":
            return {"status": "success", "history": []}
        return {"status": "success"}


class CostTier(Enum):
    """Cost tier definitions for different limits"""
    MICRO = "micro"      # $0.01 per event
    SMALL = "small"      # $0.05 per event  
    MEDIUM = "medium"    # $0.25 per event
    LARGE = "large"      # $1.00 per event
    CRITICAL = "critical" # $5.00 per event


class CostViolationType(Enum):
    """Types of cost limit violations"""
    PER_EVENT_EXCEEDED = "per_event_exceeded"
    DAILY_LIMIT_EXCEEDED = "daily_limit_exceeded"
    HOURLY_RATE_EXCEEDED = "hourly_rate_exceeded"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"


class CostCircuitBreaker:
    """
    Multi-layer cost protection system for AI operations
    
    Implements circuit breaker pattern to prevent runaway costs:
    - Per-event cost limits
    - Daily spending limits  
    - Hourly rate limiting
    - Pattern detection for abuse
    - Emergency shutdown capabilities
    """
    
    def __init__(
        self,
        daily_limit: float = 1000.0,
        per_event_limit: float = 0.05,
        hourly_limit: float = 100.0,
        emergency_threshold: float = 2000.0
    ):
        self.daily_limit = daily_limit
        self.per_event_limit = per_event_limit
        self.hourly_limit = hourly_limit
        self.emergency_threshold = emergency_threshold
        
        # Cost tracking
        self.daily_cost = 0.0
        self.hourly_cost = 0.0
        self.current_hour = datetime.utcnow().hour
        self.last_reset = datetime.utcnow().date()
        
        # Circuit breaker state
        self.is_shutdown = False
        self.shutdown_reason = None
        self.violation_history: List[Dict] = []
        
        # MCP integration
        self.mcp = MCPCostBreaker()
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
    async def check_cost_approval(
        self, 
        estimated_cost: float, 
        operation_type: str = "general",
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Check if an operation should be approved based on cost
        
        Returns:
            dict: {
                "approved": bool,
                "reason": str,
                "current_costs": dict,
                "warnings": list
            }
        """
        context = context or {}
        
        try:
            # Emergency shutdown check
            if self.is_shutdown:
                return {
                    "approved": False,
                    "reason": f"System in emergency shutdown: {self.shutdown_reason}",
                    "current_costs": await self._get_current_costs(),
                    "warnings": ["EMERGENCY_SHUTDOWN_ACTIVE"]
                }
            
            # Update cost tracking
            await self._update_cost_tracking()
            
            # Per-event limit check
            if estimated_cost > self.per_event_limit:
                violation = {
                    "type": CostViolationType.PER_EVENT_EXCEEDED,
                    "estimated_cost": estimated_cost,
                    "limit": self.per_event_limit,
                    "operation_type": operation_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "context": context
                }
                
                await self._log_cost_violation(violation)
                
                return {
                    "approved": False,
                    "reason": f"Per-event cost limit exceeded: ${estimated_cost:.4f} > ${self.per_event_limit:.4f}",
                    "current_costs": await self._get_current_costs(),
                    "warnings": ["PER_EVENT_LIMIT_EXCEEDED"]
                }
            
            # Daily limit check
            projected_daily = self.daily_cost + estimated_cost
            if projected_daily > self.daily_limit:
                violation = {
                    "type": CostViolationType.DAILY_LIMIT_EXCEEDED,
                    "current_daily": self.daily_cost,
                    "estimated_cost": estimated_cost,
                    "projected_total": projected_daily,
                    "limit": self.daily_limit,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await self._log_cost_violation(violation)
                
                # Trigger emergency shutdown if approaching critical threshold
                if projected_daily > self.emergency_threshold:
                    await self._trigger_emergency_shutdown(
                        f"Daily cost projection exceeds emergency threshold: ${projected_daily:.2f}"
                    )
                
                return {
                    "approved": False,
                    "reason": f"Daily cost limit would be exceeded: ${projected_daily:.2f} > ${self.daily_limit:.2f}",
                    "current_costs": await self._get_current_costs(),
                    "warnings": ["DAILY_LIMIT_EXCEEDED"]
                }
            
            # Hourly rate check
            projected_hourly = self.hourly_cost + estimated_cost
            if projected_hourly > self.hourly_limit:
                violation = {
                    "type": CostViolationType.HOURLY_RATE_EXCEEDED,
                    "current_hourly": self.hourly_cost,
                    "estimated_cost": estimated_cost,
                    "projected_hourly": projected_hourly,
                    "limit": self.hourly_limit,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await self._log_cost_violation(violation)
                
                return {
                    "approved": False,
                    "reason": f"Hourly rate limit would be exceeded: ${projected_hourly:.2f} > ${self.hourly_limit:.2f}",
                    "current_costs": await self._get_current_costs(),
                    "warnings": ["HOURLY_RATE_EXCEEDED"]
                }
            
            # Suspicious pattern detection
            pattern_warning = await self._detect_suspicious_patterns(estimated_cost, operation_type)
            warnings = [pattern_warning] if pattern_warning else []
            
            # Log approved operation for tracking
            await self._log_approved_operation(estimated_cost, operation_type, context)
            
            return {
                "approved": True,
                "reason": "Cost approval granted",
                "current_costs": await self._get_current_costs(),
                "warnings": warnings
            }
            
        except Exception as e:
            # Fail-safe: Block on error
            self.logger.error(f"Cost circuit breaker error: {e}")
            return {
                "approved": False,
                "reason": f"Cost breaker system error: {str(e)}",
                "current_costs": await self._get_current_costs(),
                "warnings": ["SYSTEM_ERROR"]
            }
    
    async def record_actual_cost(
        self, 
        actual_cost: float, 
        operation_type: str = "general"
    ) -> None:
        """Record the actual cost of a completed operation"""
        try:
            # Update running totals
            self.daily_cost += actual_cost
            self.hourly_cost += actual_cost
            
            # Store in Redis for persistence
            await self.mcp.call_mcp_tool("redis", "increment_cost", {
                "daily_key": f"cost:daily:{datetime.utcnow().date()}",
                "hourly_key": f"cost:hourly:{datetime.utcnow().strftime('%Y-%m-%d-%H')}",
                "amount": actual_cost
            })
            
            # Log to Supabase for audit trail
            await self.mcp.call_mcp_tool("supabase", "log_cost_event", {
                "cost": actual_cost,
                "operation_type": operation_type,
                "timestamp": datetime.utcnow().isoformat(),
                "daily_total": self.daily_cost,
                "hourly_total": self.hourly_cost
            })
            
            # Check if we need emergency shutdown
            if self.daily_cost > self.emergency_threshold:
                await self._trigger_emergency_shutdown(
                    f"Emergency threshold exceeded: ${self.daily_cost:.2f}"
                )
                
        except Exception as e:
            self.logger.error(f"Error recording actual cost: {e}")
    
    async def _update_cost_tracking(self) -> None:
        """Update cost tracking from persistent storage"""
        try:
            current_date = datetime.utcnow().date()
            current_hour = datetime.utcnow().hour
            
            # Reset daily costs if new day
            if current_date > self.last_reset:
                self.daily_cost = 0.0
                self.last_reset = current_date
            
            # Reset hourly costs if new hour
            if current_hour != self.current_hour:
                self.hourly_cost = 0.0
                self.current_hour = current_hour
            
            # Get current costs from Redis
            daily_result = await self.mcp.call_mcp_tool("redis", "get_daily_cost", {
                "date": current_date.isoformat()
            })
            
            if daily_result.get("status") == "success":
                self.daily_cost = daily_result.get("daily_cost", 0.0)
                
        except Exception as e:
            self.logger.error(f"Error updating cost tracking: {e}")
    
    async def _get_current_costs(self) -> Dict[str, float]:
        """Get current cost status"""
        return {
            "daily_cost": self.daily_cost,
            "daily_limit": self.daily_limit,
            "daily_remaining": max(0, self.daily_limit - self.daily_cost),
            "hourly_cost": self.hourly_cost,
            "hourly_limit": self.hourly_limit,
            "hourly_remaining": max(0, self.hourly_limit - self.hourly_cost),
            "per_event_limit": self.per_event_limit,
            "emergency_threshold": self.emergency_threshold
        }
    
    async def _detect_suspicious_patterns(
        self, 
        estimated_cost: float, 
        operation_type: str
    ) -> Optional[str]:
        """Detect suspicious spending patterns that might indicate abuse"""
        try:
            # High-frequency expensive operations
            if estimated_cost > self.per_event_limit * 0.8:  # 80% of limit
                recent_expensive = [
                    v for v in self.violation_history[-10:] 
                    if (datetime.utcnow() - datetime.fromisoformat(v["timestamp"])).seconds < 300
                ]
                
                if len(recent_expensive) > 3:
                    return "HIGH_FREQUENCY_EXPENSIVE_OPERATIONS"
            
            # Rapid cost escalation
            if len(self.violation_history) > 5:
                recent_costs = [v.get("estimated_cost", 0) for v in self.violation_history[-5:]]
                if all(c > self.per_event_limit * 0.5 for c in recent_costs):
                    return "RAPID_COST_ESCALATION"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in pattern detection: {e}")
            return "PATTERN_DETECTION_ERROR"
    
    async def _log_cost_violation(self, violation: Dict) -> None:
        """Log cost violation for tracking and analysis"""
        try:
            self.violation_history.append(violation)
            
            # Keep only recent violations (last 100)
            if len(self.violation_history) > 100:
                self.violation_history = self.violation_history[-100:]
            
            # Log to Supabase for permanent record
            await self.mcp.call_mcp_tool("supabase", "log_cost_violation", {
                "violation_type": violation["type"].value,
                "details": violation,
                "timestamp": violation["timestamp"]
            })
            
            # Alert administrators for serious violations
            if violation["type"] in [
                CostViolationType.DAILY_LIMIT_EXCEEDED,
                CostViolationType.EMERGENCY_SHUTDOWN
            ]:
                await self._alert_administrators(violation)
                
        except Exception as e:
            self.logger.error(f"Error logging cost violation: {e}")
    
    async def _log_approved_operation(
        self, 
        cost: float, 
        operation_type: str, 
        context: Dict
    ) -> None:
        """Log approved operations for audit trail"""
        try:
            await self.mcp.call_mcp_tool("supabase", "log_approved_operation", {
                "cost": cost,
                "operation_type": operation_type,
                "context": context,
                "timestamp": datetime.utcnow().isoformat(),
                "daily_total_after": self.daily_cost + cost
            })
        except Exception as e:
            self.logger.error(f"Error logging approved operation: {e}")
    
    async def _trigger_emergency_shutdown(self, reason: str) -> None:
        """Trigger emergency shutdown of all AI operations"""
        try:
            self.is_shutdown = True
            self.shutdown_reason = reason
            
            # Log emergency shutdown
            shutdown_event = {
                "type": CostViolationType.EMERGENCY_SHUTDOWN,
                "reason": reason,
                "daily_cost": self.daily_cost,
                "timestamp": datetime.utcnow().isoformat(),
                "threshold": self.emergency_threshold
            }
            
            await self._log_cost_violation(shutdown_event)
            
            # Publish emergency shutdown event
            await self.mcp.call_mcp_tool("redis", "publish_event", {
                "stream": "system:emergency",
                "event_type": "cost_circuit_breaker_shutdown",
                "data": shutdown_event
            })
            
            # Alert all administrators immediately
            await self._alert_administrators(shutdown_event)
            
            self.logger.critical(f"EMERGENCY COST SHUTDOWN TRIGGERED: {reason}")
            
        except Exception as e:
            self.logger.critical(f"FAILED TO TRIGGER EMERGENCY SHUTDOWN: {e}")
    
    async def _alert_administrators(self, violation: Dict) -> None:
        """Alert administrators of critical cost violations"""
        try:
            # This would integrate with notification systems
            # For now, just log at critical level
            self.logger.critical(f"COST VIOLATION ALERT: {violation}")
            
            # TODO: Integrate with actual notification system
            # - Email alerts
            # - Slack notifications  
            # - SMS for emergency shutdowns
            
        except Exception as e:
            self.logger.error(f"Error alerting administrators: {e}")
    
    async def reset_circuit_breaker(self, admin_key: str, reason: str) -> Dict[str, Any]:
        """
        Reset circuit breaker after emergency shutdown (admin only)
        
        Args:
            admin_key: Administrative authentication key
            reason: Reason for reset
            
        Returns:
            dict: Reset operation result
        """
        # TODO: Implement proper admin authentication
        if admin_key != "admin_reset_key_placeholder":
            return {
                "success": False,
                "reason": "Invalid administrative key"
            }
        
        try:
            self.is_shutdown = False
            self.shutdown_reason = None
            
            # Log reset event
            reset_event = {
                "type": "circuit_breaker_reset",
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "admin_key_used": True
            }
            
            await self.mcp.call_mcp_tool("supabase", "log_admin_action", reset_event)
            
            self.logger.warning(f"Cost circuit breaker reset by admin: {reason}")
            
            return {
                "success": True,
                "reason": "Circuit breaker reset successfully"
            }
            
        except Exception as e:
            self.logger.error(f"Error resetting circuit breaker: {e}")
            return {
                "success": False,
                "reason": f"Reset failed: {str(e)}"
            }


# Global circuit breaker instance
cost_breaker = CostCircuitBreaker()


async def check_operation_cost(
    estimated_cost: float,
    operation_type: str = "general", 
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Global function to check if an operation should proceed based on cost
    
    Usage:
        approval = await check_operation_cost(0.03, "nlp_processing", {"user_id": "123"})
        if approval["approved"]:
            # Proceed with operation
            result = await expensive_ai_operation()
            await record_operation_cost(0.025, "nlp_processing")
    """
    return await cost_breaker.check_cost_approval(estimated_cost, operation_type, context)


async def record_operation_cost(actual_cost: float, operation_type: str = "general") -> None:
    """
    Global function to record actual cost of completed operation
    
    Usage:
        await record_operation_cost(0.025, "nlp_processing")
    """
    await cost_breaker.record_actual_cost(actual_cost, operation_type)


async def get_cost_status() -> Dict[str, float]:
    """Get current cost status for monitoring"""
    return await cost_breaker._get_current_costs()


# Cost tier helpers for common operations
COST_TIERS = {
    CostTier.MICRO: 0.01,    # Simple validations, basic operations
    CostTier.SMALL: 0.05,    # Standard NLP processing, simple AI tasks  
    CostTier.MEDIUM: 0.25,   # Complex analysis, multi-step AI workflows
    CostTier.LARGE: 1.00,    # Advanced AI operations, large model calls
    CostTier.CRITICAL: 5.00  # Emergency/critical operations only
}


def get_cost_for_tier(tier: CostTier) -> float:
    """Get cost limit for a specific tier"""
    return COST_TIERS[tier]
