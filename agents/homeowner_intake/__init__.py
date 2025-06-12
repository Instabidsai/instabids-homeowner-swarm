"""
🏠 HOMEOWNER INTAKE AGENT DOMAIN - Agent 2
===================================================

Natural language processing for homeowner project intake and conversation handling.
This agent processes homeowner project submissions, extracts structured data,
and handles multi-turn conversations for clarification.

Key Responsibilities:
- Process natural language project descriptions
- Extract structured data (project type, budget, timeline, requirements)  
- Block all contact information attempts (100% filtering)
- Handle multi-turn conversations for clarification
- Integrate with Redis Streams for event processing
- Store results in Supabase read models

MCP Integration:
- context7: Research NLP/LangChain agent patterns
- redis: Event publishing/consuming
- supabase: Store processed project data
- docker: Local testing

Event Flow:
homeowner:project_submitted → intake processing → homeowner:intake_complete
"""

from .intake_agent import HomeownerIntakeAgent
from .nlp_processor import NLPProcessor  
from .data_extractor import DataExtractor
from .conversation_handler import ConversationHandler
from .intake_schemas import IntakeSchemas

__all__ = [
    'HomeownerIntakeAgent',
    'NLPProcessor', 
    'DataExtractor',
    'ConversationHandler',
    'IntakeSchemas'
]

# Agent Configuration
AGENT_CONFIG = {
    "agent_type": "homeowner_intake",
    "version": "1.0.0",
    "description": "Natural language processing for homeowner project intake",
    "dependencies": ["core.events", "core.memory", "core.security"],
    "mcp_tools": ["context7", "redis", "supabase", "docker"],
    "event_streams": {
        "consumes": ["homeowner:project_submitted", "homeowner:conversation_message"],
        "produces": ["homeowner:intake_complete", "homeowner:intake_failed"]
    }
}
