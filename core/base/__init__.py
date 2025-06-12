"""
Core Base Module - Shared Agent Patterns

This module contains the foundational patterns and utilities that all agents
in the Instabids swarm inherit and use for consistent behavior, event handling,
and health monitoring.

🤖 FOUNDATION: These are the building blocks that enable:
- Consistent agent behavior across the swarm
- Event-driven coordination via Redis Streams
- Health monitoring and performance tracking
- Shared utilities and patterns

All base components integrate with MCP tools for Codex agent usage.
"""

from .base_agent import BaseAgent, AgentState, AgentConfig
from .event_mixin import (
    EventHandlerMixin,
    EventPatterns,
    SampleEventHandler
)
from .health_monitor import (
    HealthMonitor,
    HealthStatus,
    AlertLevel,
    HealthMetric,
    HealthReport,
    HealthThresholds,
    get_health_monitor,
    start_monitoring_all,
    stop_monitoring_all
)

__all__ = [
    # Base Agent Foundation
    'BaseAgent',
    'AgentState',
    'AgentConfig',
    
    # Event Handling
    'EventHandlerMixin',
    'EventPatterns',
    'SampleEventHandler',
    
    # Health Monitoring
    'HealthMonitor',
    'HealthStatus',
    'AlertLevel',
    'HealthMetric',
    'HealthReport', 
    'HealthThresholds',
    'get_health_monitor',
    'start_monitoring_all',
    'stop_monitoring_all'
]

# Base configuration for all agents
BASE_CONFIG = {
    # Agent defaults
    "default_retry_count": 3,
    "default_timeout": 30,
    "health_check_interval": 60,
    "event_batch_size": 10,
    
    # Event handling
    "event_processing_enabled": True,
    "automatic_ack": True,
    "dead_letter_queue": True,
    
    # Health monitoring
    "health_monitoring_enabled": True,
    "performance_tracking": True,
    "alert_notifications": True,
    
    # Integration
    "mcp_integration": True,
    "audit_logging": True,
    "cost_tracking": True
}


def create_agent_with_patterns(
    agent_class,
    agent_id: str,
    agent_type: str,
    **kwargs
) -> 'BaseAgent':
    """
    Factory function to create an agent with all standard patterns
    
    Args:
        agent_class: The agent class to instantiate
        agent_id: Unique agent identifier
        agent_type: Type of agent for categorization
        **kwargs: Additional arguments for agent construction
        
    Returns:
        Configured agent instance with all patterns enabled
    """
    # Create agent instance
    agent = agent_class(agent_id=agent_id, agent_type=agent_type, **kwargs)
    
    # Ensure event handling is enabled
    if hasattr(agent, 'start_event_processing'):
        # Event handling will be started when agent starts
        pass
    
    # Setup health monitoring
    health_monitor = get_health_monitor(agent_id, agent_type)
    
    # Add standard health metrics
    if hasattr(agent, 'add_custom_metric_collector'):
        agent.add_custom_metric_collector(
            lambda: _collect_agent_specific_metrics(agent)
        )
    
    return agent


async def _collect_agent_specific_metrics(agent) -> list:
    """Collect standard metrics for any agent"""
    from datetime import datetime
    
    metrics = []
    timestamp = datetime.utcnow().isoformat()
    
    # Agent uptime metric
    if hasattr(agent, 'start_time'):
        uptime = (datetime.utcnow() - agent.start_time).total_seconds()
        metrics.append({
            "name": "agent_uptime",
            "value": uptime,
            "unit": "seconds",
            "timestamp": timestamp,
            "description": "Agent uptime in seconds"
        })
    
    # Event processing metrics
    if hasattr(agent, 'get_event_processing_stats'):
        stats = agent.get_event_processing_stats()
        metrics.append({
            "name": "events_processed",
            "value": stats.get("processed_events", 0),
            "unit": "count",
            "timestamp": timestamp,
            "description": "Total events processed"
        })
        
        metrics.append({
            "name": "event_success_rate",
            "value": stats.get("success_rate", 100),
            "unit": "percent", 
            "timestamp": timestamp,
            "description": "Event processing success rate"
        })
    
    return metrics


def get_base_config() -> dict:
    """Get the base configuration for agents"""
    return BASE_CONFIG.copy()


def update_base_config(updates: dict) -> None:
    """Update base configuration for all agents"""
    BASE_CONFIG.update(updates)


# Agent registry for tracking active agents
_active_agents = {}


def register_agent(agent: 'BaseAgent') -> None:
    """Register an agent in the global registry"""
    _active_agents[agent.agent_id] = agent


def unregister_agent(agent_id: str) -> None:
    """Unregister an agent from the global registry"""
    if agent_id in _active_agents:
        del _active_agents[agent_id]


def get_active_agents() -> dict:
    """Get all currently active agents"""
    return _active_agents.copy()


def get_agent_by_id(agent_id: str) -> 'BaseAgent':
    """Get an agent by its ID"""
    return _active_agents.get(agent_id)


async def start_all_agents() -> dict:
    """Start all registered agents"""
    results = {}
    
    for agent_id, agent in _active_agents.items():
        try:
            if hasattr(agent, 'start'):
                await agent.start()
                results[agent_id] = "started"
            else:
                results[agent_id] = "no_start_method"
        except Exception as e:
            results[agent_id] = f"error: {str(e)}"
    
    return results


async def stop_all_agents() -> dict:
    """Stop all registered agents gracefully"""
    results = {}
    
    for agent_id, agent in _active_agents.items():
        try:
            if hasattr(agent, 'stop'):
                await agent.stop()
                results[agent_id] = "stopped"
            else:
                results[agent_id] = "no_stop_method"
        except Exception as e:
            results[agent_id] = f"error: {str(e)}"
    
    return results


async def get_swarm_status() -> dict:
    """Get comprehensive status of the agent swarm"""
    status = {
        "total_agents": len(_active_agents),
        "agent_types": {},
        "overall_health": "unknown",
        "active_agents": []
    }
    
    healthy_agents = 0
    
    for agent_id, agent in _active_agents.items():
        agent_info = {
            "agent_id": agent_id,
            "agent_type": getattr(agent, 'agent_type', 'unknown'),
            "status": "unknown"
        }
        
        # Get agent type counts
        agent_type = agent_info["agent_type"]
        status["agent_types"][agent_type] = status["agent_types"].get(agent_type, 0) + 1
        
        # Get health status if available
        if hasattr(agent, 'get_current_health'):
            try:
                health = agent.get_current_health()
                agent_info["health"] = health
                if health.get("overall_status") == "healthy":
                    healthy_agents += 1
                    agent_info["status"] = "healthy"
                else:
                    agent_info["status"] = health.get("overall_status", "unknown")
            except:
                agent_info["status"] = "health_check_failed"
        
        status["active_agents"].append(agent_info)
    
    # Calculate overall health
    if len(_active_agents) == 0:
        status["overall_health"] = "no_agents"
    elif healthy_agents == len(_active_agents):
        status["overall_health"] = "healthy"
    elif healthy_agents > len(_active_agents) * 0.5:
        status["overall_health"] = "degraded"
    else:
        status["overall_health"] = "critical"
    
    return status


# Module validation
def validate_base_module() -> bool:
    """Validate that all base components are properly loaded"""
    required_components = [
        'BaseAgent',
        'EventHandlerMixin',
        'HealthMonitor'
    ]
    
    for component in required_components:
        if component not in globals():
            return False
    
    return True


# Initialize on import
if not validate_base_module():
    raise ImportError("Critical base components failed to load")
