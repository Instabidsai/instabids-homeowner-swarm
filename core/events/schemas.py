"""
Event Schema Validation for Instabids Agent Swarm
Provides type safety and validation for all Redis Streams events.
"""

import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum

class EventType(Enum):
    """Standard event types across the agent swarm"""
    # Homeowner Journey Events
    PROJECT_SUBMITTED = "project_submitted"
    INTAKE_COMPLETE = "intake_complete"
    SCOPE_COMPLETE = "scope_complete"
    CONTRACTOR_SELECTED = "contractor_selected"
    PAYMENT_COMPLETE = "payment_complete"
    CONTACT_RELEASED = "contact_released"
    
    # Agent Coordination Events
    AGENT_HEARTBEAT = "agent_heartbeat"
    AGENT_ERROR = "agent_error"
    AGENT_SCALING = "agent_scaling"
    
    # Security Events
    CONTACT_VIOLATION = "contact_violation"
    SECURITY_BREACH = "security_breach"
    COST_LIMIT_EXCEEDED = "cost_limit_exceeded"
    
    # System Events
    HEALTH_CHECK = "health_check"
    AUDIT_LOG = "audit_log"
    CIRCUIT_BREAKER = "circuit_breaker"

@dataclass
class BaseEvent:
    """Base event structure for all agent communications"""
    event_id: str
    event_type: str
    timestamp: str
    source_agent_id: str
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEvent':
        return cls(**data)

@dataclass
class ProjectEvent(BaseEvent):
    """Project-related events"""
    project_id: str
    homeowner_id: str
    project_data: Dict[str, Any]
    
@dataclass
class SecurityEvent(BaseEvent):
    """Security violation events"""
    user_id: str
    violation_type: str
    violation_data: Dict[str, Any]
    severity: str  # low, medium, high, critical
    action_taken: str

@dataclass
class AgentHeartbeatEvent(BaseEvent):
    """Agent health and activity tracking"""
    agent_type: str
    status: str  # active, idle, processing, error
    current_task: Optional[str] = None
    progress: Optional[int] = None
    resource_usage: Optional[Dict[str, Any]] = None

@dataclass
class CostControlEvent(BaseEvent):
    """Cost monitoring and circuit breaker events"""
    cost_type: str  # daily, per_event, cumulative
    current_cost: float
    limit: float
    action: str  # warning, throttle, stop

class EventValidator:
    """Validates events before publishing to Redis Streams"""
    
    REQUIRED_FIELDS = {
        'event_id', 'event_type', 'timestamp', 'source_agent_id'
    }
    
    EVENT_SCHEMAS = {
        EventType.PROJECT_SUBMITTED.value: ['project_id', 'homeowner_id', 'project_data'],
        EventType.INTAKE_COMPLETE.value: ['project_id', 'homeowner_id', 'extracted_data'],
        EventType.SCOPE_COMPLETE.value: ['project_id', 'scope_data', 'contractor_criteria'],
        EventType.CONTACT_VIOLATION.value: ['user_id', 'violation_type', 'violation_data'],
        EventType.AGENT_HEARTBEAT.value: ['agent_type', 'status'],
        EventType.COST_LIMIT_EXCEEDED.value: ['cost_type', 'current_cost', 'limit']
    }
    
    @classmethod
    def validate_event(cls, event_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate event structure and required fields
        Returns: (is_valid, error_message)
        """
        # Check required base fields
        missing_base = cls.REQUIRED_FIELDS - set(event_data.keys())
        if missing_base:
            return False, f"Missing required fields: {missing_base}"
        
        # Check event type
        event_type = event_data.get('event_type')
        if event_type not in [e.value for e in EventType]:
            return False, f"Invalid event type: {event_type}"
        
        # Check event-specific schema
        if event_type in cls.EVENT_SCHEMAS:
            required_fields = cls.EVENT_SCHEMAS[event_type]
            event_payload = event_data.get('data', {})
            missing_fields = set(required_fields) - set(event_payload.keys())
            if missing_fields:
                return False, f"Missing fields for {event_type}: {missing_fields}"
        
        return True, ""
    
    @classmethod
    def sanitize_event(cls, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data and ensure event safety"""
        sanitized = event_data.copy()
        
        # Remove potential contact information from all text fields
        def sanitize_text(text: str) -> str:
            if not isinstance(text, str):
                return text
            # TODO: Integrate with contact filter for sanitization
            return text
        
        # Recursively sanitize all text content
        def sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
            sanitized_dict = {}
            for key, value in d.items():
                if isinstance(value, str):
                    sanitized_dict[key] = sanitize_text(value)
                elif isinstance(value, dict):
                    sanitized_dict[key] = sanitize_dict(value)
                elif isinstance(value, list):
                    sanitized_dict[key] = [
                        sanitize_text(item) if isinstance(item, str) 
                        else sanitize_dict(item) if isinstance(item, dict)
                        else item for item in value
                    ]
                else:
                    sanitized_dict[key] = value
            return sanitized_dict
        
        return sanitize_dict(sanitized)

def create_event(event_type: EventType, source_agent_id: str, 
                data: Dict[str, Any], correlation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a properly formatted event for Redis Streams
    """
    import uuid
    
    event = {
        'event_id': str(uuid.uuid4()),
        'event_type': event_type.value,
        'timestamp': datetime.utcnow().isoformat(),
        'source_agent_id': source_agent_id,
        'correlation_id': correlation_id or str(uuid.uuid4()),
        'data': data
    }
    
    # Validate before returning
    is_valid, error = EventValidator.validate_event(event)
    if not is_valid:
        raise ValueError(f"Invalid event: {error}")
    
    return EventValidator.sanitize_event(event)