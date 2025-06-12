"""
Core Events Package for Instabids Agent Swarm
Provides Redis Streams-based event coordination for agent communication.

This package implements the complete event-driven architecture that enables
agents to communicate exclusively through Redis Streams without any direct
communication.
"""

from .publisher import EventPublisher
from .consumer import EventConsumer
from .coordinator import StreamCoordinator, stream_coordinator
from .schemas import (
    EventType, 
    BaseEvent, 
    ProjectEvent, 
    SecurityEvent, 
    AgentHeartbeatEvent,
    CostControlEvent,
    EventValidator,
    create_event
)

__all__ = [
    'EventPublisher',
    'EventConsumer', 
    'StreamCoordinator',
    'stream_coordinator',
    'EventType',
    'BaseEvent',
    'ProjectEvent',
    'SecurityEvent', 
    'AgentHeartbeatEvent',
    'CostControlEvent',
    'EventValidator',
    'create_event'
]

# Package metadata
__version__ = "1.0.0"
__description__ = "Event-driven coordination for Instabids Agent Swarm"