"""
Core Memory Package for Instabids Agent Swarm
3-Tier Memory Architecture: Redis + Supabase + Dynamic UI

Tier 1: Redis - Real-time events, agent coordination, temporary state
Tier 2: Supabase - Event store (audit trail) + Read models (fast queries)
Tier 3: Dynamic UI - CopilotKit morphing based on agent activity
"""

from .memory_coordinator import MemoryCoordinator, memory_coordinator
from .redis_client import RedisClient, redis_client  
from .supabase_client import SupabaseClient, supabase_client, QueryResult
from .event_store import EventStore, event_store, EventRecord

__all__ = [
    'MemoryCoordinator',
    'memory_coordinator',
    'RedisClient', 
    'redis_client',
    'SupabaseClient',
    'supabase_client',
    'QueryResult',
    'EventStore',
    'event_store',
    'EventRecord'
]

# Package metadata
__version__ = "1.0.0"
__description__ = "3-tier memory system for Instabids Agent Swarm"

# Initialize memory system on import
async def initialize_memory_system():
    """
    Initialize the complete 3-tier memory system
    Call this once at application startup
    """
    return await memory_coordinator.initialize_memory_system()