"""
💬 CONVERSATION HANDLER - Multi-turn Conversation Management
===========================================================

Handles multi-turn conversations with homeowners for project clarification.
Manages conversation state, context preservation, and intelligent follow-up
questions to gather complete project requirements.

MCP Integration:
- Uses redis for conversation state storage and event coordination
- Stores conversation logs in supabase for analysis
- Leverages context7 for conversational AI best practices

Business Rules:
- Maintain conversation context across multiple messages
- Ask intelligent follow-up questions for missing information
- Handle conversation flow based on project type
- Cost control: <$0.03 per conversation turn
- Security: Block all contact information attempts
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from core.base.base_agent import BaseAgent
from core.security.cost_breaker import CostCircuitBreaker
from core.security.audit_logger import AuditLogger
from core.security.contact_filter import ContactProtectionFilter
from .data_extractor import ProjectData, ProjectType, UrgencyLevel, BudgetRange


class ConversationState(Enum):
    """Conversation state tracking"""
    STARTED = "started"
    GATHERING_BASICS = "gathering_basics"
    CLARIFYING_DETAILS = "clarifying_details"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    BLOCKED = "blocked"  # Contact violation detected


class QuestionType(Enum):
    """Types of clarification questions"""
    PROJECT_TYPE = "project_type"
    BUDGET_RANGE = "budget_range"
    TIMELINE = "timeline"
    SPECIFIC_REQUIREMENTS = "specific_requirements"
    LOCATION_DETAILS = "location_details"
    STYLE_PREFERENCES = "style_preferences"
    SPECIAL_CONSIDERATIONS = "special_considerations"
    CONFIRMATION = "confirmation"


@dataclass
class ConversationMessage:
    """Individual conversation message"""
    message_id: str
    conversation_id: str
    user_id: str
    role: str  # "homeowner" or "assistant"
    content: str
    timestamp: str
    message_type: str = "text"  # text/question/clarification/confirmation
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ConversationContext:
    """Conversation context and state"""
    conversation_id: str
    project_id: str
    homeowner_id: str
    state: ConversationState
    started_at: str
    last_activity: str
    
    # Project data being gathered
    project_data: Optional[ProjectData] = None
    
    # Conversation tracking
    messages: List[ConversationMessage] = None
    pending_questions: List[str] = None
    asked_questions: List[str] = None
    clarification_needed: List[str] = None
    
    # Quality tracking
    completeness_score: float = 0.0
    clarification_attempts: int = 0
    max_clarification_attempts: int = 5
    
    # Security tracking
    security_violations: int = 0
    blocked_until: Optional[str] = None
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = []
        if self.pending_questions is None:
            self.pending_questions = []
        if self.asked_questions is None:
            self.asked_questions = []
        if self.clarification_needed is None:
            self.clarification_needed = []


class ConversationHandler:
    """Multi-turn conversation management with MCP integration"""
    
    def __init__(self, mcp_client=None):
        """Initialize conversation handler with MCP integration"""
        self.mcp_client = mcp_client
        self.cost_breaker = CostCircuitBreaker()
        self.audit_logger = AuditLogger()
        self.contact_filter = ContactProtectionFilter()
        
        # Conversation templates by project type
        self.question_templates = self._initialize_question_templates()
        self.follow_up_strategies = self._initialize_follow_up_strategies()
        
    def _initialize_question_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """Initialize question templates for different project types"""
        
        return {
            "bathroom_remodel": {
                QuestionType.SPECIFIC_REQUIREMENTS.value: [
                    "What specific work would you like done in your bathroom?",
                    "Are you looking to replace fixtures like the toilet, shower, or vanity?",
                    "Do you want to change the layout or keep it the same?"
                ],
                QuestionType.BUDGET_RANGE.value: [
                    "What's your budget range for this bathroom remodel?",
                    "Are you looking for a basic refresh or a complete renovation?",
                    "Have you gotten any quotes or estimates yet?"
                ],
                QuestionType.TIMELINE.value: [
                    "When would you like to start this project?",
                    "Do you have any deadline requirements?",
                    "Is this urgent or can it wait a few months?"
                ],
                QuestionType.STYLE_PREFERENCES.value: [
                    "What style are you going for? (modern, traditional, farmhouse, etc.)",
                    "Do you have any color preferences?",
                    "Are there any specific materials you want to use?"
                ]
            },
            
            "kitchen_remodel": {
                QuestionType.SPECIFIC_REQUIREMENTS.value: [
                    "What aspects of your kitchen do you want to update?",
                    "Are you planning to replace cabinets, countertops, or appliances?",
                    "Do you want to change the kitchen layout?"
                ],
                QuestionType.BUDGET_RANGE.value: [
                    "What's your budget for this kitchen remodel?",
                    "Are you looking for a partial or complete renovation?",
                    "What's the most important element to invest in?"
                ],
                QuestionType.TIMELINE.value: [
                    "When do you want to start the kitchen work?",
                    "How long can you go without a functional kitchen?",
                    "Any special timing considerations (holidays, events, etc.)?"
                ]
            },
            
            "general_repair": {
                QuestionType.SPECIFIC_REQUIREMENTS.value: [
                    "Can you describe exactly what needs to be repaired or updated?",
                    "Is this an emergency repair or general maintenance?",
                    "Have you noticed any related issues that might need attention?"
                ],
                QuestionType.BUDGET_RANGE.value: [
                    "What's your budget for this repair work?",
                    "Is this covered by insurance or warranty?",
                    "Are you looking for the most affordable option or highest quality?"
                ],
                QuestionType.TIMELINE.value: [
                    "How urgent is this repair?",
                    "When would you like the work completed?",
                    "Is this causing any daily inconvenience?"
                ]
            }
        }
    
    def _initialize_follow_up_strategies(self) -> Dict[str, Dict[str, str]]:
        """Initialize follow-up question strategies"""
        
        return {
            "unclear_budget": {
                "low_range": "For projects under $5,000, we can often do basic updates. Does that sound about right?",
                "mid_range": "Most homeowners spend between $10,000-$30,000 for this type of work. Does that fit your expectations?",
                "high_range": "Premium projects can range from $50,000+. Are you looking for high-end finishes?",
                "flexible": "Would you like me to show you options at different price points?"
            },
            
            "unclear_timeline": {
                "urgent": "If this is urgent, we can prioritize finding contractors available within 1-2 weeks.",
                "normal": "Most projects like this take 2-6 weeks to complete. Does that work for your schedule?",
                "flexible": "Since timing is flexible, we can focus on finding the best contractors even if they're booked a few months out.",
                "seasonal": "Some work is better done in certain seasons. Would you prefer to wait for optimal timing?"
            },
            
            "unclear_scope": {
                "minimal": "Are you looking for a quick fix or basic improvement?",
                "moderate": "Would you like a good balance of quality and cost?",
                "comprehensive": "Are you interested in a complete transformation?",
                "phased": "Would you prefer to break this into phases over time?"
            }
        }
    
    async def start_conversation(self, project_id: str, homeowner_id: str, 
                               initial_message: str) -> ConversationContext:
        """
        Start a new conversation for project clarification
        
        Args:
            project_id: Project identifier
            homeowner_id: Homeowner identifier
            initial_message: Initial project description
            
        Returns:
            ConversationContext object
        """
        
        # Cost control check
        estimated_cost = 0.025  # Estimated cost per conversation start
        if not await self.cost_breaker.check_cost_approval(estimated_cost):
            raise Exception("Cost limit exceeded for conversation processing")
        
        try:
            # Create conversation context
            conversation_id = str(uuid.uuid4())
            context = ConversationContext(
                conversation_id=conversation_id,
                project_id=project_id,
                homeowner_id=homeowner_id,
                state=ConversationState.STARTED,
                started_at=datetime.utcnow().isoformat(),
                last_activity=datetime.utcnow().isoformat()
            )
            
            # Security screening of initial message
            violations = self.contact_filter.scan_content(initial_message)
            if any(violations.values()):
                await self._handle_security_violation(context, violations)
                return context
            
            # Process initial message
            await self._add_message(context, homeowner_id, "homeowner", initial_message)
            
            # Analyze initial message and determine clarification needs
            clarification_needed = await self._analyze_initial_message(initial_message)
            context.clarification_needed = clarification_needed
            
            # Generate initial response
            response = await self._generate_initial_response(context, clarification_needed)
            await self._add_message(context, "assistant", "assistant", response)
            
            # Update conversation state
            context.state = ConversationState.GATHERING_BASICS
            
            # Store conversation using MCP
            await self._store_conversation_with_mcp(context)
            
            # Log conversation start
            await self.audit_logger.log_event(
                "conversation_started",
                {
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "homeowner_id": homeowner_id,
                    "clarification_needed": clarification_needed
                },
                user_id=homeowner_id
            )
            
            return context
            
        except Exception as e:
            await self.audit_logger.log_event(
                "conversation_start_failed",
                {
                    "project_id": project_id,
                    "homeowner_id": homeowner_id,
                    "error": str(e)
                },
                user_id=homeowner_id,
                severity="error"
            )
            raise
    
    async def process_message(self, conversation_id: str, user_id: str, 
                            message: str) -> Tuple[ConversationContext, str]:
        """
        Process a new message in an existing conversation
        
        Args:
            conversation_id: Conversation identifier
            user_id: User sending the message
            message: Message content
            
        Returns:
            Tuple of (updated_context, response_message)
        """
        
        # Cost control check
        estimated_cost = 0.02  # Estimated cost per message processing
        if not await self.cost_breaker.check_cost_approval(estimated_cost):
            raise Exception("Cost limit exceeded for message processing")
        
        try:
            # Load conversation context
            context = await self._load_conversation_with_mcp(conversation_id)
            if not context:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            # Check if conversation is blocked
            if context.state == ConversationState.BLOCKED:
                return context, "This conversation has been suspended due to policy violations. Please start a new project submission."
            
            # Security screening
            violations = self.contact_filter.scan_content(message)
            if any(violations.values()):
                await self._handle_security_violation(context, violations)
                return context, "I notice you're trying to share contact information. For your protection, we handle all communication through our platform until you're matched with a contractor and payment is confirmed."
            
            # Add user message
            await self._add_message(context, user_id, "homeowner", message)
            
            # Process message based on conversation state
            response = await self._process_message_by_state(context, message)
            
            # Add assistant response
            await self._add_message(context, "assistant", "assistant", response)
            
            # Update conversation state
            await self._update_conversation_state(context)
            
            # Store updated conversation
            await self._store_conversation_with_mcp(context)
            
            # Log message processing
            await self.audit_logger.log_event(
                "message_processed",
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "state": context.state.value,
                    "completeness_score": context.completeness_score
                },
                user_id=user_id
            )
            
            return context, response
            
        except Exception as e:
            await self.audit_logger.log_event(
                "message_processing_failed",
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "error": str(e)
                },
                user_id=user_id,
                severity="error"
            )
            raise
    
    async def _analyze_initial_message(self, message: str) -> List[str]:
        """Analyze initial message to determine what clarification is needed"""
        
        clarification_needed = []
        message_lower = message.lower()
        
        # Check for missing project type clarity
        if not any(project_type in message_lower for project_type in [
            "bathroom", "kitchen", "floor", "paint", "plumb", "electric", "roof"
        ]):
            clarification_needed.append(QuestionType.PROJECT_TYPE.value)
        
        # Check for missing budget information
        if not any(budget_indicator in message_lower for budget_indicator in [
            "$", "budget", "cost", "spend", "afford", "price"
        ]):
            clarification_needed.append(QuestionType.BUDGET_RANGE.value)
        
        # Check for missing timeline information
        if not any(timeline_indicator in message_lower for timeline_indicator in [
            "when", "time", "soon", "urgent", "weeks", "months", "deadline"
        ]):
            clarification_needed.append(QuestionType.TIMELINE.value)
        
        # Check for vague requirements
        if len(message.split()) < 10:  # Very short description
            clarification_needed.append(QuestionType.SPECIFIC_REQUIREMENTS.value)
        
        # Check for missing location details
        if not any(location_indicator in message_lower for location_indicator in [
            "bathroom", "kitchen", "bedroom", "room", "area", "house", "home"
        ]):
            clarification_needed.append(QuestionType.LOCATION_DETAILS.value)
        
        return clarification_needed
    
    async def _generate_initial_response(self, context: ConversationContext, 
                                       clarification_needed: List[str]) -> str:
        """Generate initial response based on clarification needs"""
        
        if not clarification_needed:
            return "Thank you for your detailed project description! I have all the information needed to find you qualified contractors. Let me process your request."
        
        # Start with acknowledgment
        response_parts = [
            "Thank you for reaching out! I'd like to ask a few questions to make sure I find you the perfect contractors for your project."
        ]
        
        # Add specific questions based on what's needed
        if QuestionType.PROJECT_TYPE.value in clarification_needed:
            response_parts.append("First, could you tell me what type of project this is? (For example: bathroom remodel, kitchen renovation, flooring, etc.)")
        
        elif QuestionType.SPECIFIC_REQUIREMENTS.value in clarification_needed:
            response_parts.append("Could you provide more details about exactly what work you'd like done?")
        
        elif QuestionType.BUDGET_RANGE.value in clarification_needed:
            response_parts.append("What's your budget range for this project? This helps me match you with contractors in your price range.")
        
        elif QuestionType.TIMELINE.value in clarification_needed:
            response_parts.append("When would you like to start this project? Are there any timing constraints I should know about?")
        
        return " ".join(response_parts)
    
    async def _process_message_by_state(self, context: ConversationContext, 
                                      message: str) -> str:
        """Process message based on current conversation state"""
        
        if context.state == ConversationState.GATHERING_BASICS:
            return await self._process_basic_gathering(context, message)
        
        elif context.state == ConversationState.CLARIFYING_DETAILS:
            return await self._process_detail_clarification(context, message)
        
        elif context.state == ConversationState.FINALIZING:
            return await self._process_finalization(context, message)
        
        else:
            return "I'm sorry, there seems to be an issue with our conversation. Let me help you start fresh."
    
    async def _process_basic_gathering(self, context: ConversationContext, 
                                     message: str) -> str:
        """Process message during basic information gathering phase"""
        
        # Analyze what information this message provides
        provided_info = self._analyze_message_content(message)
        
        # Update clarification needed list
        for info_type in provided_info:
            if info_type in context.clarification_needed:
                context.clarification_needed.remove(info_type)
        
        # Check if we have enough basic information
        basic_requirements = [
            QuestionType.PROJECT_TYPE.value,
            QuestionType.SPECIFIC_REQUIREMENTS.value
        ]
        
        if all(req not in context.clarification_needed for req in basic_requirements):
            context.state = ConversationState.CLARIFYING_DETAILS
            return await self._generate_detail_questions(context)
        
        # Ask for next missing basic information
        return await self._ask_next_basic_question(context)
    
    async def _process_detail_clarification(self, context: ConversationContext, 
                                          message: str) -> str:
        """Process message during detail clarification phase"""
        
        # Analyze what details this message provides
        provided_details = self._analyze_message_content(message)
        
        # Update clarification needed list
        for detail_type in provided_details:
            if detail_type in context.clarification_needed:
                context.clarification_needed.remove(detail_type)
        
        # Check if we have enough details
        context.completeness_score = self._calculate_completeness(context)
        
        if context.completeness_score >= 0.8 or not context.clarification_needed:
            context.state = ConversationState.FINALIZING
            return await self._generate_final_confirmation(context)
        
        # Ask for next missing detail
        return await self._ask_next_detail_question(context)
    
    async def _process_finalization(self, context: ConversationContext, 
                                  message: str) -> str:
        """Process message during finalization phase"""
        
        message_lower = message.lower()
        
        # Check for confirmation
        if any(confirm in message_lower for confirm in ["yes", "correct", "sounds good", "that's right"]):
            context.state = ConversationState.COMPLETED
            return "Perfect! I have all the information needed. I'll now find qualified contractors in your area and you'll hear from them soon. Thank you!"
        
        # Check for corrections
        elif any(correction in message_lower for correction in ["no", "not quite", "actually", "change"]):
            context.state = ConversationState.CLARIFYING_DETAILS
            return "No problem! What would you like to clarify or change?"
        
        # Ask for explicit confirmation
        else:
            return "Could you please confirm if all the details I've gathered are correct, or let me know what needs to be changed?"
    
    def _analyze_message_content(self, message: str) -> List[str]:
        """Analyze message content to determine what information it provides"""
        
        provided_info = []
        message_lower = message.lower()
        
        # Check for project type information
        project_keywords = {
            "bathroom": ["bathroom", "shower", "tub", "vanity"],
            "kitchen": ["kitchen", "cabinet", "countertop"],
            "flooring": ["floor", "carpet", "tile", "hardwood"],
            "painting": ["paint", "color", "wall"],
            "plumbing": ["plumb", "pipe", "leak", "drain"],
            "electrical": ["electric", "outlet", "wiring", "light"]
        }
        
        if any(any(keyword in message_lower for keyword in keywords) 
               for keywords in project_keywords.values()):
            provided_info.append(QuestionType.PROJECT_TYPE.value)
        
        # Check for budget information
        if any(budget_indicator in message_lower for budget_indicator in [
            "$", "budget", "cost", "spend", "afford", "price", "thousand", "k"
        ]):
            provided_info.append(QuestionType.BUDGET_RANGE.value)
        
        # Check for timeline information
        if any(timeline_indicator in message_lower for timeline_indicator in [
            "when", "time", "soon", "urgent", "weeks", "months", "deadline", "start"
        ]):
            provided_info.append(QuestionType.TIMELINE.value)
        
        # Check for specific requirements
        if any(requirement_indicator in message_lower for requirement_indicator in [
            "need", "want", "replace", "install", "repair", "fix", "upgrade"
        ]):
            provided_info.append(QuestionType.SPECIFIC_REQUIREMENTS.value)
        
        # Check for location details
        if any(location_indicator in message_lower for location_indicator in [
            "room", "area", "space", "house", "home", "upstairs", "downstairs"
        ]):
            provided_info.append(QuestionType.LOCATION_DETAILS.value)
        
        # Check for style preferences
        if any(style_indicator in message_lower for style_indicator in [
            "style", "modern", "traditional", "color", "material", "design"
        ]):
            provided_info.append(QuestionType.STYLE_PREFERENCES.value)
        
        return provided_info
    
    async def _ask_next_basic_question(self, context: ConversationContext) -> str:
        """Ask the next basic question needed"""
        
        if not context.clarification_needed:
            return "Thank you! I have all the basic information. Let me ask about some details."
        
        next_question_type = context.clarification_needed[0]
        
        # Map to appropriate question
        question_map = {
            QuestionType.PROJECT_TYPE.value: "What type of project is this? (bathroom remodel, kitchen work, flooring, etc.)",
            QuestionType.SPECIFIC_REQUIREMENTS.value: "Could you provide more specific details about what work you'd like done?",
            QuestionType.BUDGET_RANGE.value: "What's your budget range for this project?",
            QuestionType.TIMELINE.value: "When would you like to start this work?",
            QuestionType.LOCATION_DETAILS.value: "Which room or area of your home is this for?"
        }
        
        return question_map.get(next_question_type, "Could you provide more details about your project?")
    
    async def _ask_next_detail_question(self, context: ConversationContext) -> str:
        """Ask the next detail question needed"""
        
        if not context.clarification_needed:
            return "I think I have all the details I need. Let me summarize your project."
        
        next_detail = context.clarification_needed[0]
        
        # Generate contextual detail questions
        if next_detail == QuestionType.STYLE_PREFERENCES.value:
            return "Do you have any style preferences? (modern, traditional, colors, materials, etc.)"
        
        elif next_detail == QuestionType.SPECIAL_CONSIDERATIONS.value:
            return "Are there any special considerations I should know about? (accessibility needs, pets, timing constraints, etc.)"
        
        elif next_detail == QuestionType.BUDGET_RANGE.value:
            return "Could you share your budget range? This helps me find contractors that match your investment level."
        
        elif next_detail == QuestionType.TIMELINE.value:
            return "What's your ideal timeline for this project?"
        
        else:
            return "Is there anything else about your project that would help me find the right contractors?"
    
    async def _generate_detail_questions(self, context: ConversationContext) -> str:
        """Generate detail clarification questions"""
        
        response_parts = ["Great! Now I'd like to gather some additional details to find you the best contractors."]
        
        # Prioritize most important missing details
        priority_details = [
            QuestionType.BUDGET_RANGE.value,
            QuestionType.TIMELINE.value,
            QuestionType.STYLE_PREFERENCES.value
        ]
        
        for detail in priority_details:
            if detail in context.clarification_needed:
                if detail == QuestionType.BUDGET_RANGE.value:
                    response_parts.append("What's your budget range for this project?")
                elif detail == QuestionType.TIMELINE.value:
                    response_parts.append("When would you like to start?")
                elif detail == QuestionType.STYLE_PREFERENCES.value:
                    response_parts.append("Do you have any style preferences?")
                break
        
        return " ".join(response_parts)
    
    async def _generate_final_confirmation(self, context: ConversationContext) -> str:
        """Generate final confirmation summary"""
        
        # TODO: Build summary from collected project data
        summary_parts = [
            "Perfect! Let me confirm the details of your project:",
            "- Project type: [project type from context]",
            "- Budget range: [budget from context]", 
            "- Timeline: [timeline from context]",
            "- Location: [location from context]",
            "",
            "Does this look correct? I'll use these details to find qualified contractors in your area."
        ]
        
        return "\n".join(summary_parts)
    
    def _calculate_completeness(self, context: ConversationContext) -> float:
        """Calculate conversation completeness score"""
        
        # Define essential information categories
        essential_categories = [
            QuestionType.PROJECT_TYPE.value,
            QuestionType.SPECIFIC_REQUIREMENTS.value,
            QuestionType.BUDGET_RANGE.value,
            QuestionType.TIMELINE.value
        ]
        
        # Calculate how many essential categories we have
        collected_essential = sum(1 for category in essential_categories 
                                if category not in context.clarification_needed)
        
        # Base completeness from essential categories
        base_completeness = collected_essential / len(essential_categories)
        
        # Bonus for additional details
        total_possible_details = len(QuestionType)
        collected_details = total_possible_details - len(context.clarification_needed)
        detail_bonus = (collected_details / total_possible_details) * 0.3
        
        return min(base_completeness + detail_bonus, 1.0)
    
    async def _handle_security_violation(self, context: ConversationContext, 
                                       violations: Dict[str, List[str]]):
        """Handle security violations in conversation"""
        
        context.security_violations += 1
        
        # Log security violation
        await self.audit_logger.log_event(
            "conversation_security_violation",
            {
                "conversation_id": context.conversation_id,
                "homeowner_id": context.homeowner_id,
                "violations": violations,
                "violation_count": context.security_violations
            },
            user_id=context.homeowner_id,
            severity="warning"
        )
        
        # Apply escalation based on violation count
        if context.security_violations >= 3:
            context.state = ConversationState.BLOCKED
            context.blocked_until = (datetime.utcnow() + timedelta(hours=24)).isoformat()
            
            await self.audit_logger.log_event(
                "conversation_blocked",
                {
                    "conversation_id": context.conversation_id,
                    "homeowner_id": context.homeowner_id,
                    "blocked_until": context.blocked_until
                },
                user_id=context.homeowner_id,
                severity="error"
            )
    
    async def _add_message(self, context: ConversationContext, user_id: str, 
                         role: str, content: str):
        """Add a message to the conversation"""
        
        message = ConversationMessage(
            message_id=str(uuid.uuid4()),
            conversation_id=context.conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            timestamp=datetime.utcnow().isoformat()
        )
        
        context.messages.append(message)
        context.last_activity = datetime.utcnow().isoformat()
    
    async def _update_conversation_state(self, context: ConversationContext):
        """Update conversation state based on current context"""
        
        # Calculate current completeness
        context.completeness_score = self._calculate_completeness(context)
        
        # Update clarification attempts
        if context.clarification_needed:
            context.clarification_attempts += 1
        
        # Check for completion conditions
        if context.completeness_score >= 0.9 and context.state != ConversationState.COMPLETED:
            context.state = ConversationState.FINALIZING
        
        # Check for max attempts reached
        if context.clarification_attempts >= context.max_clarification_attempts:
            context.state = ConversationState.FINALIZING
    
    async def _store_conversation_with_mcp(self, context: ConversationContext):
        """Store conversation using MCP integration"""
        
        if not self.mcp_client:
            return
        
        try:
            # Convert to dictionary for storage
            context_dict = asdict(context)
            context_dict["state"] = context.state.value
            
            # Store in Redis for fast access
            await self.mcp_client.call_tool("redis", {
                "command": "set",
                "key": f"conversation:{context.conversation_id}",
                "value": json.dumps(context_dict),
                "expiration": 86400  # 24 hours
            })
            
            # Store in Supabase for long-term storage
            await self.mcp_client.call_tool("supabase", {
                "action": "store_conversation",
                "table": "conversations",
                "data": context_dict
            })
            
        except Exception as e:
            await self.audit_logger.log_event(
                "conversation_storage_failed",
                {"error": str(e), "conversation_id": context.conversation_id},
                user_id=context.homeowner_id,
                severity="error"
            )
    
    async def _load_conversation_with_mcp(self, conversation_id: str) -> Optional[ConversationContext]:
        """Load conversation using MCP integration"""
        
        if not self.mcp_client:
            return None
        
        try:
            # Try Redis first (fast)
            redis_result = await self.mcp_client.call_tool("redis", {
                "command": "get",
                "key": f"conversation:{conversation_id}"
            })
            
            if redis_result:
                context_dict = json.loads(redis_result)
                context_dict["state"] = ConversationState(context_dict["state"])
                return ConversationContext(**context_dict)
            
            # Fallback to Supabase
            supabase_result = await self.mcp_client.call_tool("supabase", {
                "action": "get_conversation",
                "table": "conversations",
                "conversation_id": conversation_id
            })
            
            if supabase_result:
                context_dict = supabase_result
                context_dict["state"] = ConversationState(context_dict["state"])
                return ConversationContext(**context_dict)
            
            return None
            
        except Exception as e:
            await self.audit_logger.log_event(
                "conversation_loading_failed",
                {"error": str(e), "conversation_id": conversation_id},
                severity="error"
            )
            return None


# MCP Integration Functions
async def start_conversation_with_mcp(mcp_client, project_id: str, homeowner_id: str, 
                                    initial_message: str) -> ConversationContext:
    """
    Start conversation using MCP tools
    
    This function integrates with the MCP ecosystem to:
    1. Research conversation patterns with context7
    2. Coordinate with Redis for state management
    3. Store conversation data in Supabase
    """
    
    handler = ConversationHandler(mcp_client=mcp_client)
    
    # Use MCP context7 tool for conversation research if needed
    if mcp_client:
        try:
            # Research conversational AI best practices
            research_result = await mcp_client.call_tool("context7", {
                "query": "conversational AI project clarification best practices",
                "topic": "multi-turn conversation management"
            })
            
        except Exception as e:
            # Continue processing even if MCP research fails
            pass
    
    # Start the conversation
    context = await handler.start_conversation(project_id, homeowner_id, initial_message)
    
    return context


async def process_message_with_mcp(mcp_client, conversation_id: str, user_id: str, 
                                 message: str) -> Tuple[ConversationContext, str]:
    """
    Process conversation message using MCP tools
    """
    
    handler = ConversationHandler(mcp_client=mcp_client)
    
    # Process the message
    context, response = await handler.process_message(conversation_id, user_id, message)
    
    return context, response
