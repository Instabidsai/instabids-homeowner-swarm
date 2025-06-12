"""
📊 INTAKE SCHEMAS - Data Validation and Schema Definitions
========================================================

Defines all data validation schemas, input/output formats, and API contracts
for the homeowner intake system. Ensures data integrity and consistency
across all intake processing components.

MCP Integration:
- Validation schemas used across Redis event payloads
- Supabase table schemas and constraints
- API response formats for external integrations

Business Rules:
- Strict validation of all homeowner input
- Contact information must be blocked/filtered
- Cost tracking and validation
- Audit trail requirements
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import re
from pydantic import BaseModel, Field, validator, root_validator


# Enum definitions for consistent data types
class ProjectTypeSchema(str, Enum):
    """Project type validation schema"""
    BATHROOM_REMODEL = "bathroom_remodel"
    KITCHEN_REMODEL = "kitchen_remodel"
    FLOORING = "flooring"
    PAINTING = "painting"
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    HVAC = "hvac"
    ROOFING = "roofing"
    SIDING = "siding"
    WINDOWS = "windows"
    DOORS = "doors"
    LANDSCAPING = "landscaping"
    DECK_PATIO = "deck_patio"
    BASEMENT_FINISHING = "basement_finishing"
    ATTIC_CONVERSION = "attic_conversion"
    ADDITION = "addition"
    GARAGE = "garage"
    DRIVEWAY = "driveway"
    FENCE = "fence"
    GENERAL_REPAIR = "general_repair"
    MAINTENANCE = "maintenance"
    CUSTOM_WORK = "custom_work"


class UrgencyLevelSchema(str, Enum):
    """Urgency level validation schema"""
    URGENT = "urgent"
    NORMAL = "normal"
    FLEXIBLE = "flexible"


class BudgetRangeSchema(str, Enum):
    """Budget range validation schema"""
    UNDER_5K = "under_5k"
    RANGE_5K_15K = "5k_to_15k"
    RANGE_15K_30K = "15k_to_30k"
    RANGE_30K_50K = "30k_to_50k"
    RANGE_50K_100K = "50k_to_100k"
    OVER_100K = "over_100k"
    UNKNOWN = "unknown"


class ConversationStateSchema(str, Enum):
    """Conversation state validation schema"""
    STARTED = "started"
    GATHERING_BASICS = "gathering_basics"
    CLARIFYING_DETAILS = "clarifying_details"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    BLOCKED = "blocked"


# Input validation schemas
class HomeownerProjectSubmissionSchema(BaseModel):
    """Schema for initial homeowner project submission"""
    
    # Required fields
    homeowner_id: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=10, max_length=5000)
    
    # Optional structured fields
    project_type: Optional[ProjectTypeSchema] = None
    budget_min: Optional[float] = Field(None, ge=0, le=10000000)
    budget_max: Optional[float] = Field(None, ge=0, le=10000000)
    timeline_preference: Optional[str] = Field(None, max_length=200)
    urgency_level: Optional[UrgencyLevelSchema] = UrgencyLevelSchema.NORMAL
    
    # Location information
    room_locations: Optional[List[str]] = Field(default_factory=list, max_items=10)
    property_address: Optional[str] = Field(None, max_length=500)
    property_type: Optional[str] = Field(None, max_length=50)
    
    # Preferences
    style_preferences: Optional[List[str]] = Field(default_factory=list, max_items=20)
    material_preferences: Optional[List[str]] = Field(default_factory=list, max_items=20)
    brand_preferences: Optional[List[str]] = Field(default_factory=list, max_items=10)
    
    # Special considerations
    accessibility_needs: Optional[List[str]] = Field(default_factory=list, max_items=10)
    pet_considerations: Optional[List[str]] = Field(default_factory=list, max_items=10)
    family_considerations: Optional[List[str]] = Field(default_factory=list, max_items=10)
    
    # Metadata
    submission_source: str = Field(default="web_form", max_length=50)
    user_agent: Optional[str] = Field(None, max_length=500)
    ip_address: Optional[str] = Field(None, max_length=45)
    submission_timestamp: Optional[str] = None
    
    @validator('description')
    def validate_description_content(cls, v):
        """Validate description doesn't contain contact information"""
        if not v or len(v.strip()) < 10:
            raise ValueError('Description must be at least 10 characters')
        
        # Check for contact information patterns
        contact_violations = _check_contact_violations(v)
        if contact_violations:
            raise ValueError(f'Description contains prohibited contact information: {contact_violations}')
        
        return v.strip()
    
    @validator('budget_max')
    def validate_budget_range(cls, v, values):
        """Validate budget max is greater than budget min"""
        if v is not None and 'budget_min' in values and values['budget_min'] is not None:
            if v <= values['budget_min']:
                raise ValueError('Budget max must be greater than budget min')
        return v
    
    @validator('room_locations', 'style_preferences', 'material_preferences', 'brand_preferences')
    def validate_string_lists(cls, v):
        """Validate string lists don't contain contact information"""
        if v:
            for item in v:
                if _check_contact_violations(item):
                    raise ValueError(f'List item contains prohibited contact information: {item}')
        return v
    
    @root_validator
    def validate_submission(cls, values):
        """Root validation for entire submission"""
        
        # Set submission timestamp if not provided
        if not values.get('submission_timestamp'):
            values['submission_timestamp'] = datetime.utcnow().isoformat()
        
        # Validate required combinations
        description = values.get('description', '')
        if len(description) < 20 and not values.get('project_type'):
            raise ValueError('Either detailed description or project type must be provided')
        
        return values


class ConversationMessageSchema(BaseModel):
    """Schema for conversation messages"""
    
    conversation_id: str = Field(..., min_length=1, max_length=100)
    user_id: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., regex=r'^(homeowner|assistant)$')
    content: str = Field(..., min_length=1, max_length=2000)
    message_type: str = Field(default="text", max_length=50)
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('content')
    def validate_message_content(cls, v):
        """Validate message content doesn't contain contact information"""
        if not v or len(v.strip()) < 1:
            raise ValueError('Message content cannot be empty')
        
        # Check for contact information if from homeowner
        contact_violations = _check_contact_violations(v)
        if contact_violations:
            raise ValueError(f'Message contains prohibited contact information: {contact_violations}')
        
        return v.strip()
    
    @root_validator
    def validate_message(cls, values):
        """Root validation for message"""
        
        if not values.get('timestamp'):
            values['timestamp'] = datetime.utcnow().isoformat()
        
        return values


# Processing output schemas
class NLPProcessingResultSchema(BaseModel):
    """Schema for NLP processing results"""
    
    # Core extraction results
    project_type: ProjectTypeSchema
    specific_requirements: List[str] = Field(default_factory=list, max_items=50)
    materials_mentioned: List[str] = Field(default_factory=list, max_items=30)
    room_locations: List[str] = Field(default_factory=list, max_items=20)
    style_preferences: List[str] = Field(default_factory=list, max_items=20)
    
    # Budget information
    budget_range: Optional[BudgetRangeSchema] = None
    budget_min: Optional[float] = Field(None, ge=0)
    budget_max: Optional[float] = Field(None, ge=0)
    budget_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Timeline information
    timeline_duration: Optional[str] = Field(None, max_length=100)
    urgency_level: UrgencyLevelSchema = UrgencyLevelSchema.NORMAL
    timeline_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Quality metrics
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)
    unclear_requirements: List[str] = Field(default_factory=list, max_items=20)
    
    # Processing metadata
    processing_method: str = Field(default="llm_extraction", max_length=50)
    processing_cost: float = Field(default=0.0, ge=0.0)
    processed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    @validator('specific_requirements', 'materials_mentioned', 'room_locations', 'style_preferences')
    def validate_extracted_lists(cls, v):
        """Validate extracted lists are clean"""
        if v:
            cleaned = []
            for item in v:
                if item and len(item.strip()) > 0:
                    # Check for contact information
                    if not _check_contact_violations(item):
                        cleaned.append(item.strip())
            return cleaned
        return v


class ProjectDataExtractionSchema(BaseModel):
    """Schema for complete project data extraction results"""
    
    # Identification
    project_id: str = Field(..., min_length=1, max_length=100)
    homeowner_id: str = Field(..., min_length=1, max_length=100)
    submission_timestamp: str
    
    # Core project data
    project_type: ProjectTypeSchema
    project_subtype: Optional[str] = Field(None, max_length=100)
    description: str = Field(..., min_length=10, max_length=5000)
    
    # Requirements and specifications
    specific_requirements: List[str] = Field(default_factory=list, max_items=50)
    materials_mentioned: List[str] = Field(default_factory=list, max_items=30)
    
    # Budget information
    budget_range: BudgetRangeSchema = BudgetRangeSchema.UNKNOWN
    budget_min: Optional[float] = Field(None, ge=0)
    budget_max: Optional[float] = Field(None, ge=0)
    budget_flexibility: str = Field(default="negotiable", max_length=20)
    
    # Timeline information
    timeline_duration: Optional[str] = Field(None, max_length=100)
    timeline_start_preference: Optional[str] = Field(None, max_length=100)
    urgency_level: UrgencyLevelSchema = UrgencyLevelSchema.NORMAL
    
    # Location information
    property_address: Optional[str] = Field(None, max_length=500)
    room_locations: List[str] = Field(default_factory=list, max_items=20)
    property_type: str = Field(default="unknown", max_length=50)
    
    # Preferences
    style_preferences: List[str] = Field(default_factory=list, max_items=20)
    color_preferences: List[str] = Field(default_factory=list, max_items=10)
    brand_preferences: List[str] = Field(default_factory=list, max_items=10)
    
    # Special considerations
    accessibility_needs: List[str] = Field(default_factory=list, max_items=10)
    pet_considerations: List[str] = Field(default_factory=list, max_items=10)
    family_considerations: List[str] = Field(default_factory=list, max_items=10)
    environmental_preferences: List[str] = Field(default_factory=list, max_items=10)
    
    # Quality metrics
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    unclear_requirements: List[str] = Field(default_factory=list, max_items=20)
    
    # Processing metadata
    extraction_method: str = Field(default="automated", max_length=50)
    processed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    processing_cost: float = Field(default=0.0, ge=0.0)
    
    @validator('description')
    def validate_description(cls, v):
        """Validate description content"""
        if _check_contact_violations(v):
            raise ValueError('Description contains prohibited contact information')
        return v.strip()


class ConversationContextSchema(BaseModel):
    """Schema for conversation context data"""
    
    # Identification
    conversation_id: str = Field(..., min_length=1, max_length=100)
    project_id: str = Field(..., min_length=1, max_length=100)
    homeowner_id: str = Field(..., min_length=1, max_length=100)
    
    # State tracking
    state: ConversationStateSchema
    started_at: str
    last_activity: str
    
    # Conversation data
    messages: List[ConversationMessageSchema] = Field(default_factory=list, max_items=100)
    pending_questions: List[str] = Field(default_factory=list, max_items=20)
    asked_questions: List[str] = Field(default_factory=list, max_items=50)
    clarification_needed: List[str] = Field(default_factory=list, max_items=20)
    
    # Quality tracking
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    clarification_attempts: int = Field(default=0, ge=0, le=10)
    max_clarification_attempts: int = Field(default=5, ge=1, le=10)
    
    # Security tracking
    security_violations: int = Field(default=0, ge=0)
    blocked_until: Optional[str] = None
    
    @validator('messages')
    def validate_messages_count(cls, v):
        """Validate reasonable message count"""
        if len(v) > 100:
            raise ValueError('Too many messages in conversation')
        return v
    
    @root_validator
    def validate_conversation_state(cls, values):
        """Validate conversation state consistency"""
        
        state = values.get('state')
        security_violations = values.get('security_violations', 0)
        
        # If blocked, must have violations
        if state == ConversationStateSchema.BLOCKED and security_violations == 0:
            raise ValueError('Blocked conversation must have security violations')
        
        # If completed, must have high completeness
        if state == ConversationStateSchema.COMPLETED:
            completeness = values.get('completeness_score', 0.0)
            if completeness < 0.7:
                raise ValueError('Completed conversation must have completeness score >= 0.7')
        
        return values


# Event schemas for Redis Streams
class IntakeEventBaseSchema(BaseModel):
    """Base schema for all intake events"""
    
    event_id: str = Field(..., min_length=1, max_length=100)
    event_type: str = Field(..., min_length=1, max_length=100)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    correlation_id: Optional[str] = Field(None, max_length=100)
    user_id: Optional[str] = Field(None, max_length=100)
    
    # Cost tracking
    processing_cost: float = Field(default=0.0, ge=0.0)
    
    # Security tracking
    security_validated: bool = Field(default=False)


class ProjectSubmittedEventSchema(IntakeEventBaseSchema):
    """Schema for project submission events"""
    
    event_type: str = Field(default="project_submitted", const=True)
    
    # Event data
    project_id: str = Field(..., min_length=1, max_length=100)
    homeowner_id: str = Field(..., min_length=1, max_length=100)
    submission_data: HomeownerProjectSubmissionSchema
    
    @validator('submission_data')
    def validate_submission_security(cls, v):
        """Ensure submission has been security validated"""
        # Additional security validation here
        return v


class IntakeCompleteEventSchema(IntakeEventBaseSchema):
    """Schema for intake completion events"""
    
    event_type: str = Field(default="intake_complete", const=True)
    
    # Event data
    project_id: str = Field(..., min_length=1, max_length=100)
    homeowner_id: str = Field(..., min_length=1, max_length=100)
    extracted_data: ProjectDataExtractionSchema
    needs_clarification: List[str] = Field(default_factory=list)
    
    @validator('extracted_data')
    def validate_extraction_quality(cls, v):
        """Validate extraction meets quality standards"""
        if v.completeness_score < 0.3:
            raise ValueError('Extracted data completeness score too low')
        return v


class IntakeFailedEventSchema(IntakeEventBaseSchema):
    """Schema for intake failure events"""
    
    event_type: str = Field(default="intake_failed", const=True)
    
    # Event data
    project_id: str = Field(..., min_length=1, max_length=100)
    homeowner_id: Optional[str] = Field(None, max_length=100)
    error_type: str = Field(..., max_length=100)
    error_message: str = Field(..., max_length=1000)
    retry_required: bool = Field(default=True)
    
    @validator('error_message')
    def validate_error_message(cls, v):
        """Ensure error message doesn't leak sensitive info"""
        # Remove any potential contact information from error messages
        if _check_contact_violations(v):
            return "Processing error occurred - contact information detected"
        return v


class ConversationMessageEventSchema(IntakeEventBaseSchema):
    """Schema for conversation message events"""
    
    event_type: str = Field(default="conversation_message", const=True)
    
    # Event data
    conversation_id: str = Field(..., min_length=1, max_length=100)
    message_data: ConversationMessageSchema
    conversation_state: ConversationStateSchema
    
    @validator('message_data')
    def validate_message_security(cls, v):
        """Ensure message has been security validated"""
        # Message content is already validated in ConversationMessageSchema
        return v


# API response schemas
class IntakeAPIResponseSchema(BaseModel):
    """Standard API response schema for intake operations"""
    
    success: bool
    message: str = Field(..., max_length=500)
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    
    # Request tracking
    request_id: str = Field(..., min_length=1, max_length=100)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    processing_time_ms: Optional[float] = Field(None, ge=0)
    
    # Cost information
    processing_cost: float = Field(default=0.0, ge=0.0)
    cost_breakdown: Optional[Dict[str, float]] = None


class ProjectStatusResponseSchema(BaseModel):
    """Schema for project status API responses"""
    
    project_id: str = Field(..., min_length=1, max_length=100)
    status: str = Field(..., max_length=50)
    
    # Status details
    intake_complete: bool = Field(default=False)
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_clarification: List[str] = Field(default_factory=list)
    
    # Progress tracking
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    next_action: Optional[str] = Field(None, max_length=200)
    
    # Conversation info
    conversation_active: bool = Field(default=False)
    conversation_id: Optional[str] = Field(None, max_length=100)


# Utility functions for validation
def _check_contact_violations(text: str) -> List[str]:
    """Check text for contact information violations"""
    
    violations = []
    text_lower = text.lower()
    
    # Phone number patterns
    phone_patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',
        r'\b\d{3}\s+\d{3}\s+\d{4}\b',
        r'\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
    ]
    
    for pattern in phone_patterns:
        if re.search(pattern, text):
            violations.append("phone_number")
            break
    
    # Email patterns
    email_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        r'\b[A-Za-z0-9._%+-]+\s*\[?at\]?\s*[A-Za-z0-9.-]+\s*\[?dot\]?\s*[A-Z|a-z]{2,}\b',
    ]
    
    for pattern in email_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append("email_address")
            break
    
    # Social media patterns
    if re.search(r'@[A-Za-z0-9_]+', text):
        violations.append("social_media")
    
    # Intent-based patterns
    intent_patterns = [
        r'(?:call|text|email|contact)\s+me',
        r'(?:my|the)\s+(?:number|phone|email)',
        r'(?:reach|contact)\s+(?:me\s+)?(?:at|on)',
    ]
    
    for pattern in intent_patterns:
        if re.search(pattern, text_lower):
            violations.append("contact_intent")
            break
    
    return violations


# Schema validation utility functions
def validate_project_submission(data: Dict[str, Any]) -> HomeownerProjectSubmissionSchema:
    """Validate and parse project submission data"""
    try:
        return HomeownerProjectSubmissionSchema(**data)
    except Exception as e:
        raise ValueError(f"Invalid project submission: {str(e)}")


def validate_conversation_message(data: Dict[str, Any]) -> ConversationMessageSchema:
    """Validate and parse conversation message data"""
    try:
        return ConversationMessageSchema(**data)
    except Exception as e:
        raise ValueError(f"Invalid conversation message: {str(e)}")


def validate_nlp_result(data: Dict[str, Any]) -> NLPProcessingResultSchema:
    """Validate and parse NLP processing result data"""
    try:
        return NLPProcessingResultSchema(**data)
    except Exception as e:
        raise ValueError(f"Invalid NLP result: {str(e)}")


def validate_project_data(data: Dict[str, Any]) -> ProjectDataExtractionSchema:
    """Validate and parse project data extraction result"""
    try:
        return ProjectDataExtractionSchema(**data)
    except Exception as e:
        raise ValueError(f"Invalid project data: {str(e)}")


def validate_conversation_context(data: Dict[str, Any]) -> ConversationContextSchema:
    """Validate and parse conversation context data"""
    try:
        return ConversationContextSchema(**data)
    except Exception as e:
        raise ValueError(f"Invalid conversation context: {str(e)}")


# Event validation functions
def validate_intake_event(event_type: str, data: Dict[str, Any]) -> IntakeEventBaseSchema:
    """Validate intake event based on type"""
    
    event_schemas = {
        "project_submitted": ProjectSubmittedEventSchema,
        "intake_complete": IntakeCompleteEventSchema,
        "intake_failed": IntakeFailedEventSchema,
        "conversation_message": ConversationMessageEventSchema,
    }
    
    schema_class = event_schemas.get(event_type, IntakeEventBaseSchema)
    
    try:
        return schema_class(**data)
    except Exception as e:
        raise ValueError(f"Invalid {event_type} event: {str(e)}")


# Schema export functions for MCP integration
def get_redis_event_schema(event_type: str) -> Dict[str, Any]:
    """Get JSON schema for Redis event validation"""
    
    event_schemas = {
        "project_submitted": ProjectSubmittedEventSchema,
        "intake_complete": IntakeCompleteEventSchema,
        "intake_failed": IntakeFailedEventSchema,
        "conversation_message": ConversationMessageEventSchema,
    }
    
    schema_class = event_schemas.get(event_type, IntakeEventBaseSchema)
    return schema_class.schema()


def get_supabase_table_schema(table_name: str) -> Dict[str, Any]:
    """Get table schema for Supabase integration"""
    
    table_schemas = {
        "project_submissions": HomeownerProjectSubmissionSchema,
        "project_extractions": ProjectDataExtractionSchema,
        "conversations": ConversationContextSchema,
        "conversation_messages": ConversationMessageSchema,
        "nlp_results": NLPProcessingResultSchema,
    }
    
    schema_class = table_schemas.get(table_name)
    if not schema_class:
        raise ValueError(f"Unknown table schema: {table_name}")
    
    return schema_class.schema()


def get_api_response_schema(response_type: str) -> Dict[str, Any]:
    """Get API response schema for external integrations"""
    
    response_schemas = {
        "intake_response": IntakeAPIResponseSchema,
        "project_status": ProjectStatusResponseSchema,
    }
    
    schema_class = response_schemas.get(response_type)
    if not schema_class:
        raise ValueError(f"Unknown response schema: {response_type}")
    
    return schema_class.schema()


# Configuration and constants
INTAKE_VALIDATION_CONFIG = {
    "max_description_length": 5000,
    "max_conversation_messages": 100,
    "max_clarification_attempts": 5,
    "min_completeness_score": 0.3,
    "max_processing_cost_per_event": 0.05,
    "contact_violation_patterns": {
        "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "social": r'@[A-Za-z0-9_]+',
    }
}

# Schema version for compatibility tracking
SCHEMA_VERSION = "1.0.0"
SCHEMA_LAST_UPDATED = "2025-06-12"
