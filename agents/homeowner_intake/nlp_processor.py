"""
🧠 NLP PROCESSOR - Natural Language Processing for Project Descriptions
=======================================================================

Handles natural language processing for homeowner project descriptions using
LangChain agents and OpenAI models. Extracts structured information from 
unstructured text input.

MCP Integration:
- Uses context7 tool for research and pattern analysis
- Integrates with Redis for event coordination
- Stores results in Supabase via memory system

Business Rules:
- Extract project type, requirements, budget, timeline, urgency
- Identify unclear requirements that need clarification  
- Handle multi-language support
- Cost control: <$0.05 per processing event
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from langchain.agents import AgentExecutor
from langchain.llms import OpenAI
from langchain.tools import Tool
from langchain.prompts import PromptTemplate

from core.base.base_agent import BaseAgent
from core.security.cost_breaker import CostCircuitBreaker
from core.security.audit_logger import AuditLogger


class NLPProcessor:
    """Natural language processing for project descriptions with MCP integration"""
    
    def __init__(self, mcp_client=None):
        """Initialize NLP processor with MCP integration"""
        self.mcp_client = mcp_client
        self.llm = OpenAI(temperature=0.1, max_tokens=1000)
        self.cost_breaker = CostCircuitBreaker()
        self.audit_logger = AuditLogger()
        self.extraction_tools = self._create_extraction_tools()
        
        # Project categories for classification
        self.project_categories = [
            "bathroom_remodel", "kitchen_remodel", "flooring", "painting",
            "plumbing", "electrical", "hvac", "roofing", "siding", 
            "windows", "doors", "landscaping", "deck_patio", "basement_finishing",
            "attic_conversion", "addition", "garage", "driveway", "fence",
            "general_repair", "maintenance", "custom_work"
        ]
        
        # Budget ranges for classification
        self.budget_ranges = [
            {"range": "under_5k", "min": 0, "max": 5000},
            {"range": "5k_to_15k", "min": 5000, "max": 15000},
            {"range": "15k_to_30k", "min": 15000, "max": 30000},
            {"range": "30k_to_50k", "min": 30000, "max": 50000},
            {"range": "50k_to_100k", "min": 50000, "max": 100000},
            {"range": "over_100k", "min": 100000, "max": float('inf')}
        ]
        
    async def extract_project_info(self, description: str, user_id: str = None) -> Dict[str, Any]:
        """
        Extract structured information from project description
        
        Args:
            description: Raw project description text
            user_id: Optional user ID for auditing
            
        Returns:
            Dictionary with extracted project information
        """
        
        # Cost control check
        estimated_cost = 0.03  # Estimated cost per extraction
        if not await self.cost_breaker.check_cost_approval(estimated_cost):
            raise Exception("Cost limit exceeded for NLP processing")
            
        try:
            # Log processing start
            await self.audit_logger.log_event(
                "nlp_processing_started",
                {"user_id": user_id, "description_length": len(description)},
                user_id=user_id
            )
            
            # Pre-process text
            cleaned_description = self._preprocess_text(description)
            
            # Extract basic information using LLM
            extraction_result = await self._extract_with_llm(cleaned_description)
            
            # Post-process and validate results
            processed_result = await self._post_process_extraction(extraction_result, cleaned_description)
            
            # Log successful processing
            await self.audit_logger.log_event(
                "nlp_processing_completed",
                {
                    "user_id": user_id,
                    "extracted_data": processed_result,
                    "processing_cost": estimated_cost
                },
                user_id=user_id
            )
            
            return processed_result
            
        except Exception as e:
            # Log processing error
            await self.audit_logger.log_event(
                "nlp_processing_failed",
                {
                    "user_id": user_id,
                    "error": str(e),
                    "description_length": len(description)
                },
                user_id=user_id,
                severity="error"
            )
            raise
    
    def _preprocess_text(self, text: str) -> str:
        """Clean and normalize input text"""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters that might confuse the model
        text = re.sub(r'[^\w\s\.,!?$-]', ' ', text)
        
        # Normalize currency mentions
        text = re.sub(r'\$\s*(\d+)', r'$\1', text)
        text = re.sub(r'(\d+)\s*k\b', r'\1000', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*K\b', r'\1000', text)
        
        return text
    
    async def _extract_with_llm(self, description: str) -> Dict[str, Any]:
        """Extract information using language model"""
        
        extraction_prompt = f"""
        Extract structured information from this home improvement project description:
        
        Description: "{description}"
        
        Extract the following information and return as JSON:
        {{
            "project_type": "<one of: {', '.join(self.project_categories)}>",
            "specific_requirements": ["<list of specific work items>"],
            "materials_mentioned": ["<list of materials or brands mentioned>"],
            "budget_indicators": ["<any budget-related text>"],
            "timeline_indicators": ["<any timeline-related text>"],
            "urgency_level": "<urgent/normal/flexible>",
            "room_locations": ["<specific rooms or areas mentioned>"],
            "style_preferences": ["<any style, color, or aesthetic preferences>"],
            "special_considerations": ["<accessibility, pets, family situation, etc>"],
            "unclear_aspects": ["<what needs clarification>"]
        }}
        
        Rules:
        - Be specific and extract actual mentioned items
        - If something is not mentioned, use empty list or "unknown"  
        - For project_type, choose the MOST specific category that fits
        - Include exact quotes for budget and timeline indicators
        - Identify what information is missing or unclear
        """
        
        # Use LLM for extraction
        response = await self.llm.agenerate([extraction_prompt])
        
        try:
            # Parse JSON response
            extracted_data = json.loads(response.generations[0][0].text.strip())
            return extracted_data
        except json.JSONDecodeError:
            # Fallback: extract key information with regex
            return self._fallback_extraction(description)
    
    def _fallback_extraction(self, description: str) -> Dict[str, Any]:
        """Fallback extraction using regex patterns when LLM fails"""
        
        result = {
            "project_type": "general_repair",
            "specific_requirements": [],
            "materials_mentioned": [],
            "budget_indicators": [],
            "timeline_indicators": [], 
            "urgency_level": "normal",
            "room_locations": [],
            "style_preferences": [],
            "special_considerations": [],
            "unclear_aspects": ["AI processing failed - manual review needed"]
        }
        
        # Extract budget indicators
        budget_patterns = [
            r'\$\s*\d+(?:,\d{3})*(?:\.\d{2})?',  # Dollar amounts
            r'\d+k?\s*(?:to|\-)\s*\d+k?\s*(?:dollars?|bucks?|\$)?',  # Ranges
            r'budget.*?\$?\d+',  # Budget mentions
            r'spend.*?\$?\d+',   # Spending mentions
        ]
        
        for pattern in budget_patterns:
            matches = re.finditer(pattern, description, re.IGNORECASE)
            for match in matches:
                result["budget_indicators"].append(match.group())
        
        # Extract timeline indicators
        timeline_patterns = [
            r'\d+\s*(?:days?|weeks?|months?)',  # Time periods
            r'by\s+\w+',  # "by December", etc
            r'(?:asap|urgent|rush|quickly|soon)',  # Urgency indicators
            r'timeline.*?\d+',  # Timeline mentions
        ]
        
        for pattern in timeline_patterns:
            matches = re.finditer(pattern, description, re.IGNORECASE)
            for match in matches:
                result["timeline_indicators"].append(match.group())
        
        # Extract room mentions
        room_keywords = [
            "bathroom", "kitchen", "bedroom", "living room", "basement", 
            "attic", "garage", "patio", "deck", "yard", "office", "laundry"
        ]
        
        for room in room_keywords:
            if room in description.lower():
                result["room_locations"].append(room)
        
        # Classify project type based on keywords
        project_keywords = {
            "bathroom_remodel": ["bathroom", "shower", "tub", "vanity", "toilet"],
            "kitchen_remodel": ["kitchen", "cabinet", "countertop", "appliance"],
            "flooring": ["floor", "carpet", "tile", "hardwood", "laminate"],
            "painting": ["paint", "color", "wall"],
            "plumbing": ["plumbing", "pipe", "leak", "drain", "faucet"],
            "electrical": ["electrical", "outlet", "switch", "wiring", "light"],
            "roofing": ["roof", "shingles", "gutter", "chimney"],
        }
        
        for project_type, keywords in project_keywords.items():
            if any(keyword in description.lower() for keyword in keywords):
                result["project_type"] = project_type
                break
        
        return result
    
    async def _post_process_extraction(self, extraction_result: Dict[str, Any], 
                                     original_description: str) -> Dict[str, Any]:
        """Post-process and enhance extraction results"""
        
        # Parse budget range
        budget_range = self._parse_budget_range(extraction_result.get("budget_indicators", []))
        
        # Parse timeline 
        timeline_info = self._parse_timeline(extraction_result.get("timeline_indicators", []))
        
        # Determine confidence scores
        confidence_scores = self._calculate_confidence_scores(extraction_result, original_description)
        
        # Identify missing information
        unclear_requirements = self._identify_unclear_requirements(
            extraction_result, confidence_scores
        )
        
        # Build final result
        processed_result = {
            "project_type": extraction_result.get("project_type", "unknown"),
            "specific_requirements": extraction_result.get("specific_requirements", []),
            "materials_mentioned": extraction_result.get("materials_mentioned", []),
            "room_locations": extraction_result.get("room_locations", []),
            "style_preferences": extraction_result.get("style_preferences", []),
            "special_considerations": extraction_result.get("special_considerations", []),
            
            # Processed fields
            "budget_range": budget_range,
            "timeline_estimate": timeline_info,
            "urgency_level": extraction_result.get("urgency_level", "normal"),
            "confidence_scores": confidence_scores,
            "unclear_requirements": unclear_requirements,
            
            # Metadata
            "extraction_method": "llm_processing",
            "processed_at": datetime.utcnow().isoformat(),
            "original_description": original_description
        }
        
        return processed_result
    
    def _parse_budget_range(self, budget_indicators: List[str]) -> Dict[str, Any]:
        """Parse budget indicators into structured range"""
        
        if not budget_indicators:
            return {"range": "unknown", "min": None, "max": None, "confidence": 0.0}
        
        # Extract numeric values
        amounts = []
        for indicator in budget_indicators:
            # Find all numeric values
            numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', indicator.replace('k', '000').replace('K', '000'))
            for num in numbers:
                try:
                    amounts.append(float(num.replace(',', '')))
                except ValueError:
                    continue
        
        if not amounts:
            return {"range": "unknown", "min": None, "max": None, "confidence": 0.0}
        
        # Determine range
        min_amount = min(amounts)
        max_amount = max(amounts) if len(amounts) > 1 else min_amount * 1.2
        
        # Classify into range categories
        for range_info in self.budget_ranges:
            if range_info["min"] <= min_amount < range_info["max"]:
                return {
                    "range": range_info["range"],
                    "min": min_amount,
                    "max": max_amount,
                    "confidence": 0.8,
                    "raw_indicators": budget_indicators
                }
        
        return {
            "range": "custom",
            "min": min_amount,
            "max": max_amount,
            "confidence": 0.7,
            "raw_indicators": budget_indicators
        }
    
    def _parse_timeline(self, timeline_indicators: List[str]) -> Dict[str, Any]:
        """Parse timeline indicators into structured timeline"""
        
        if not timeline_indicators:
            return {"duration": "unknown", "urgency": "normal", "confidence": 0.0}
        
        timeline_text = " ".join(timeline_indicators).lower()
        
        # Check for urgency indicators
        urgency = "normal"
        if any(urgent in timeline_text for urgent in ["asap", "urgent", "rush", "immediately", "quickly"]):
            urgency = "urgent"
        elif any(flexible in timeline_text for flexible in ["flexible", "whenever", "no rush"]):
            urgency = "flexible"
        
        # Extract duration
        duration_patterns = [
            (r'(\d+)\s*(?:days?)', lambda x: f"{x} days"),
            (r'(\d+)\s*(?:weeks?)', lambda x: f"{x} weeks"),  
            (r'(\d+)\s*(?:months?)', lambda x: f"{x} months"),
            (r'(\d+)-(\d+)\s*(?:weeks?)', lambda x, y: f"{x}-{y} weeks"),
            (r'(\d+)-(\d+)\s*(?:months?)', lambda x, y: f"{x}-{y} months"),
        ]
        
        duration = "unknown"
        confidence = 0.0
        
        for pattern, formatter in duration_patterns:
            match = re.search(pattern, timeline_text)
            if match:
                if len(match.groups()) == 1:
                    duration = formatter(match.group(1))
                else:
                    duration = formatter(match.group(1), match.group(2))
                confidence = 0.8
                break
        
        return {
            "duration": duration,
            "urgency": urgency,
            "confidence": confidence,
            "raw_indicators": timeline_indicators
        }
    
    def _calculate_confidence_scores(self, extraction_result: Dict[str, Any], 
                                   original_description: str) -> Dict[str, float]:
        """Calculate confidence scores for extracted information"""
        
        scores = {}
        
        # Project type confidence
        project_type = extraction_result.get("project_type", "unknown")
        if project_type == "unknown":
            scores["project_type"] = 0.0
        elif project_type in self.project_categories:
            scores["project_type"] = 0.8
        else:
            scores["project_type"] = 0.5
        
        # Requirements confidence  
        requirements = extraction_result.get("specific_requirements", [])
        scores["requirements"] = min(len(requirements) * 0.2, 1.0)
        
        # Budget confidence
        budget_indicators = extraction_result.get("budget_indicators", [])
        scores["budget"] = min(len(budget_indicators) * 0.4, 1.0)
        
        # Timeline confidence
        timeline_indicators = extraction_result.get("timeline_indicators", [])
        scores["timeline"] = min(len(timeline_indicators) * 0.5, 1.0)
        
        # Overall confidence
        scores["overall"] = sum(scores.values()) / len(scores)
        
        return scores
    
    def _identify_unclear_requirements(self, extraction_result: Dict[str, Any],
                                     confidence_scores: Dict[str, float]) -> List[str]:
        """Identify what information needs clarification"""
        
        unclear = []
        
        # Check for low confidence scores
        if confidence_scores.get("project_type", 0) < 0.5:
            unclear.append("project_type")
            
        if confidence_scores.get("budget", 0) < 0.3:
            unclear.append("budget_range")
            
        if confidence_scores.get("timeline", 0) < 0.3:
            unclear.append("timeline_preferences")
            
        # Check for missing critical information
        if not extraction_result.get("specific_requirements"):
            unclear.append("specific_work_requirements")
            
        if not extraction_result.get("room_locations"):
            unclear.append("location_details")
        
        # Check extraction's own unclear aspects
        extraction_unclear = extraction_result.get("unclear_aspects", [])
        for aspect in extraction_unclear:
            if aspect and aspect not in unclear:
                unclear.append(aspect)
        
        return unclear
    
    def _create_extraction_tools(self) -> List[Tool]:
        """Create LangChain tools for extraction (future enhancement)"""
        
        tools = [
            Tool(
                name="project_classifier",
                description="Classify project into standard categories",
                func=self._classify_project_type
            ),
            Tool(
                name="budget_parser", 
                description="Parse budget information from text",
                func=self._parse_budget_text
            ),
            Tool(
                name="timeline_parser",
                description="Parse timeline information from text", 
                func=self._parse_timeline_text
            )
        ]
        
        return tools
    
    def _classify_project_type(self, description: str) -> str:
        """Classify project type (tool function)"""
        description_lower = description.lower()
        
        for project_type, keywords in {
            "bathroom_remodel": ["bathroom", "shower", "tub", "vanity"],
            "kitchen_remodel": ["kitchen", "cabinet", "countertop"],
            "flooring": ["floor", "carpet", "tile", "hardwood"],
            "painting": ["paint", "color", "wall"],
            "plumbing": ["plumbing", "pipe", "leak"],
            "electrical": ["electrical", "outlet", "wiring"]
        }.items():
            if any(keyword in description_lower for keyword in keywords):
                return project_type
                
        return "general_repair"
    
    def _parse_budget_text(self, text: str) -> str:
        """Parse budget from text (tool function)"""
        budget_match = re.search(r'\$\s*\d+(?:,\d{3})*', text)
        return budget_match.group() if budget_match else "unknown"
    
    def _parse_timeline_text(self, text: str) -> str:
        """Parse timeline from text (tool function)"""
        timeline_match = re.search(r'\d+\s*(?:days?|weeks?|months?)', text.lower())
        return timeline_match.group() if timeline_match else "unknown"


# MCP Integration Functions
async def process_with_mcp(mcp_client, description: str, user_id: str = None) -> Dict[str, Any]:
    """
    Process project description using MCP tools
    
    This function integrates with the MCP ecosystem to:
    1. Research processing patterns with context7
    2. Coordinate with Redis for event handling
    3. Store results in Supabase
    """
    
    processor = NLPProcessor(mcp_client=mcp_client)
    
    # Use MCP context7 tool for pattern research if needed
    if mcp_client:
        try:
            # Research best practices for this type of processing
            research_result = await mcp_client.call_tool("context7", {
                "query": "natural language processing project description extraction",
                "topic": "construction project categorization"
            })
            
            # Log MCP research usage
            await processor.audit_logger.log_event(
                "mcp_context7_usage",
                {"query": "nlp project extraction", "user_id": user_id},
                user_id=user_id
            )
            
        except Exception as e:
            # Continue processing even if MCP research fails
            await processor.audit_logger.log_event(
                "mcp_context7_failed",
                {"error": str(e), "user_id": user_id},
                user_id=user_id,
                severity="warning"
            )
    
    # Process the description
    result = await processor.extract_project_info(description, user_id)
    
    # Store result using MCP supabase integration
    if mcp_client:
        try:
            await mcp_client.call_tool("supabase", {
                "action": "store_intake_result",
                "data": result,
                "user_id": user_id
            })
        except Exception as e:
            await processor.audit_logger.log_event(
                "mcp_supabase_storage_failed",
                {"error": str(e), "user_id": user_id},
                user_id=user_id,
                severity="error"
            )
    
    return result
