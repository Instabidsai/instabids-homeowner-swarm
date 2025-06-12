"""
📊 DATA EXTRACTOR - Project Data Extraction and Structuring
==========================================================

Handles extraction and structuring of project data from various sources.
Converts unstructured homeowner input into standardized data formats
for downstream processing by other agents.

MCP Integration:
- Uses redis for event coordination and temporary storage
- Stores structured data in supabase via memory system
- Leverages context7 for research on data structuring patterns

Business Rules:
- Extract and normalize all project-related data
- Handle multiple input formats (text, forms, files)
- Validate data integrity and completeness
- Cost control: <$0.02 per extraction event
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

from core.base.base_agent import BaseAgent
from core.security.cost_breaker import CostCircuitBreaker
from core.security.audit_logger import AuditLogger


class ProjectType(Enum):
    """Standardized project type classifications"""
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


class UrgencyLevel(Enum):
    """Project urgency classifications"""
    URGENT = "urgent"          # Within 1-2 weeks
    NORMAL = "normal"          # 1-3 months
    FLEXIBLE = "flexible"      # 3+ months or whenever


class BudgetRange(Enum):
    """Budget range classifications"""
    UNDER_5K = "under_5k"
    RANGE_5K_15K = "5k_to_15k"
    RANGE_15K_30K = "15k_to_30k"
    RANGE_30K_50K = "30k_to_50k"
    RANGE_50K_100K = "50k_to_100k"
    OVER_100K = "over_100k"
    UNKNOWN = "unknown"


@dataclass
class ProjectData:
    """Standardized project data structure"""
    
    # Core identification
    project_id: str
    homeowner_id: str
    submission_timestamp: str
    
    # Project classification
    project_type: ProjectType
    project_subtype: Optional[str] = None
    
    # Basic information
    description: str
    specific_requirements: List[str] = None
    materials_mentioned: List[str] = None
    
    # Budget information
    budget_range: BudgetRange = BudgetRange.UNKNOWN
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    budget_flexibility: str = "negotiable"  # negotiable/firm/unknown
    
    # Timeline information
    timeline_duration: Optional[str] = None
    timeline_start_preference: Optional[str] = None
    urgency_level: UrgencyLevel = UrgencyLevel.NORMAL
    
    # Location information
    property_address: Optional[str] = None
    room_locations: List[str] = None
    property_type: str = "unknown"  # house/condo/apartment/commercial
    
    # Style and preferences
    style_preferences: List[str] = None
    color_preferences: List[str] = None
    brand_preferences: List[str] = None
    
    # Special considerations
    accessibility_needs: List[str] = None
    pet_considerations: List[str] = None
    family_considerations: List[str] = None
    environmental_preferences: List[str] = None
    
    # Data quality
    completeness_score: float = 0.0
    confidence_score: float = 0.0
    unclear_requirements: List[str] = None
    
    # Processing metadata
    extraction_method: str = "manual"
    processed_at: str = None
    processing_cost: float = 0.0
    
    def __post_init__(self):
        """Post-initialization processing"""
        if self.specific_requirements is None:
            self.specific_requirements = []
        if self.materials_mentioned is None:
            self.materials_mentioned = []
        if self.room_locations is None:
            self.room_locations = []
        if self.style_preferences is None:
            self.style_preferences = []
        if self.color_preferences is None:
            self.color_preferences = []
        if self.brand_preferences is None:
            self.brand_preferences = []
        if self.accessibility_needs is None:
            self.accessibility_needs = []
        if self.pet_considerations is None:
            self.pet_considerations = []
        if self.family_considerations is None:
            self.family_considerations = []
        if self.environmental_preferences is None:
            self.environmental_preferences = []
        if self.unclear_requirements is None:
            self.unclear_requirements = []
        if self.processed_at is None:
            self.processed_at = datetime.utcnow().isoformat()


class DataExtractor:
    """Project data extraction and structuring with MCP integration"""
    
    def __init__(self, mcp_client=None):
        """Initialize data extractor with MCP integration"""
        self.mcp_client = mcp_client
        self.cost_breaker = CostCircuitBreaker()
        self.audit_logger = AuditLogger()
        
        # Extraction patterns
        self.budget_patterns = self._initialize_budget_patterns()
        self.timeline_patterns = self._initialize_timeline_patterns()
        self.room_patterns = self._initialize_room_patterns()
        self.material_patterns = self._initialize_material_patterns()
        
    def _initialize_budget_patterns(self) -> Dict[str, Any]:
        """Initialize budget extraction patterns"""
        return {
            "currency_amounts": [
                r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,000.00
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*dollars?',  # 1000 dollars
                r'(\d+)k\s*(?:dollars?|\$)?',  # 5k dollars
                r'(\d+)K\s*(?:dollars?|\$)?',  # 5K dollars
            ],
            "range_patterns": [
                r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:to|\-)\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'between\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s+and\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'(\d+)k?\s*(?:to|\-)\s*(\d+)k?\s*(?:budget|dollars?|\$)?',
            ],
            "budget_keywords": [
                "budget", "spend", "cost", "price", "affordable", "expensive",
                "cheap", "investment", "financing", "loan", "cash"
            ]
        }
    
    def _initialize_timeline_patterns(self) -> Dict[str, Any]:
        """Initialize timeline extraction patterns"""
        return {
            "duration_patterns": [
                r'(\d+)\s*(?:days?)',  # 30 days
                r'(\d+)\s*(?:weeks?)',  # 2 weeks
                r'(\d+)\s*(?:months?)',  # 3 months
                r'(\d+)\s*(?:years?)',  # 1 year
                r'(\d+)\s*to\s*(\d+)\s*(?:weeks?|months?)',  # 2 to 4 weeks
            ],
            "urgency_patterns": [
                r'(?:asap|urgent|rush|emergency|immediately|quickly|soon)',
                r'(?:flexible|whenever|no\s+rush|no\s+hurry)',
                r'by\s+(\w+)',  # by December
                r'within\s+(\d+\s+\w+)',  # within 2 weeks
            ],
            "start_time_patterns": [
                r'start\s+(?:in\s+)?(\w+)',  # start in January
                r'begin\s+(?:in\s+)?(\w+)',  # begin in spring
                r'(?:next|this)\s+(\w+)',  # next month
            ]
        }
    
    def _initialize_room_patterns(self) -> Dict[str, Any]:
        """Initialize room/location extraction patterns"""
        return {
            "rooms": [
                "bathroom", "kitchen", "bedroom", "living room", "family room",
                "dining room", "office", "study", "basement", "attic", "garage",
                "laundry room", "mudroom", "pantry", "closet", "hallway",
                "entryway", "foyer", "sunroom", "porch", "deck", "patio"
            ],
            "room_modifiers": [
                "master", "guest", "main", "primary", "secondary", "upstairs",
                "downstairs", "first floor", "second floor", "finished", "unfinished"
            ],
            "outdoor_areas": [
                "yard", "garden", "lawn", "driveway", "walkway", "fence",
                "deck", "patio", "pool", "spa", "shed", "greenhouse"
            ]
        }
    
    def _initialize_material_patterns(self) -> Dict[str, Any]:
        """Initialize material/brand extraction patterns"""
        return {
            "materials": {
                "flooring": ["hardwood", "tile", "carpet", "laminate", "vinyl", "marble", "granite"],
                "countertops": ["granite", "quartz", "marble", "butcher block", "concrete"],
                "cabinets": ["wood", "oak", "maple", "cherry", "pine", "plywood", "MDF"],
                "fixtures": ["stainless steel", "bronze", "chrome", "brass", "copper"],
                "paint": ["latex", "oil", "primer", "semi-gloss", "satin", "eggshell"]
            },
            "brands": [
                "Home Depot", "Lowes", "IKEA", "Kohler", "Delta", "Moen",
                "Samsung", "GE", "Whirlpool", "KitchenAid", "Benjamin Moore",
                "Sherwin Williams", "Behr"
            ]
        }
    
    async def extract_project_data(self, raw_input: Dict[str, Any], 
                                 project_id: str, homeowner_id: str) -> ProjectData:
        """
        Extract and structure project data from raw input
        
        Args:
            raw_input: Raw input data (description, form fields, etc.)
            project_id: Unique project identifier
            homeowner_id: Homeowner identifier
            
        Returns:
            Structured ProjectData object
        """
        
        # Cost control check
        estimated_cost = 0.015  # Estimated cost per extraction
        if not await self.cost_breaker.check_cost_approval(estimated_cost):
            raise Exception("Cost limit exceeded for data extraction")
        
        try:
            # Log extraction start
            await self.audit_logger.log_event(
                "data_extraction_started",
                {
                    "project_id": project_id,
                    "homeowner_id": homeowner_id,
                    "input_size": len(str(raw_input))
                },
                user_id=homeowner_id
            )
            
            # Initialize project data structure
            project_data = ProjectData(
                project_id=project_id,
                homeowner_id=homeowner_id,
                submission_timestamp=datetime.utcnow().isoformat(),
                description=raw_input.get("description", ""),
                extraction_method="automated_extraction",
                processing_cost=estimated_cost
            )
            
            # Extract from different input sources
            if "description" in raw_input:
                await self._extract_from_description(project_data, raw_input["description"])
            
            if "form_data" in raw_input:
                await self._extract_from_form_data(project_data, raw_input["form_data"])
            
            if "nlp_results" in raw_input:
                await self._integrate_nlp_results(project_data, raw_input["nlp_results"])
            
            # Post-process and validate
            await self._post_process_data(project_data)
            
            # Calculate quality scores
            self._calculate_quality_scores(project_data)
            
            # Store extracted data using MCP
            if self.mcp_client:
                await self._store_with_mcp(project_data)
            
            # Log successful extraction
            await self.audit_logger.log_event(
                "data_extraction_completed",
                {
                    "project_id": project_id,
                    "completeness_score": project_data.completeness_score,
                    "confidence_score": project_data.confidence_score,
                    "processing_cost": estimated_cost
                },
                user_id=homeowner_id
            )
            
            return project_data
            
        except Exception as e:
            # Log extraction error
            await self.audit_logger.log_event(
                "data_extraction_failed",
                {
                    "project_id": project_id,
                    "homeowner_id": homeowner_id,
                    "error": str(e)
                },
                user_id=homeowner_id,
                severity="error"
            )
            raise
    
    async def _extract_from_description(self, project_data: ProjectData, description: str):
        """Extract data from free-text description"""
        
        # Extract budget information
        budget_info = self._extract_budget_info(description)
        if budget_info:
            project_data.budget_range = budget_info.get("range", BudgetRange.UNKNOWN)
            project_data.budget_min = budget_info.get("min")
            project_data.budget_max = budget_info.get("max")
            project_data.budget_flexibility = budget_info.get("flexibility", "negotiable")
        
        # Extract timeline information
        timeline_info = self._extract_timeline_info(description)
        if timeline_info:
            project_data.timeline_duration = timeline_info.get("duration")
            project_data.timeline_start_preference = timeline_info.get("start_preference")
            project_data.urgency_level = timeline_info.get("urgency", UrgencyLevel.NORMAL)
        
        # Extract room/location information
        room_info = self._extract_room_info(description)
        if room_info:
            project_data.room_locations.extend(room_info)
        
        # Extract materials and brands
        material_info = self._extract_material_info(description)
        if material_info:
            project_data.materials_mentioned.extend(material_info.get("materials", []))
            project_data.brand_preferences.extend(material_info.get("brands", []))
        
        # Extract project type
        project_type = self._extract_project_type(description)
        if project_type:
            project_data.project_type = project_type
        
        # Extract special considerations
        special_considerations = self._extract_special_considerations(description)
        if special_considerations:
            project_data.accessibility_needs.extend(special_considerations.get("accessibility", []))
            project_data.pet_considerations.extend(special_considerations.get("pets", []))
            project_data.family_considerations.extend(special_considerations.get("family", []))
            project_data.environmental_preferences.extend(special_considerations.get("environmental", []))
    
    def _extract_budget_info(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract budget information from text"""
        
        budget_info = {"amounts": [], "flexibility": "negotiable"}
        
        # Extract currency amounts
        for pattern in self.budget_patterns["currency_amounts"]:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1).replace(',', '')
                try:
                    # Handle 'k' suffix
                    if 'k' in match.group(0).lower():
                        amount = float(amount_str) * 1000
                    else:
                        amount = float(amount_str)
                    budget_info["amounts"].append(amount)
                except (ValueError, IndexError):
                    continue
        
        # Extract range patterns
        for pattern in self.budget_patterns["range_patterns"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    min_amount = float(match.group(1).replace(',', ''))
                    max_amount = float(match.group(2).replace(',', ''))
                    
                    # Handle 'k' suffix
                    if 'k' in match.group(0).lower():
                        min_amount *= 1000
                        max_amount *= 1000
                    
                    budget_info["min"] = min_amount
                    budget_info["max"] = max_amount
                    break
                except (ValueError, IndexError):
                    continue
        
        # Determine range classification
        if "min" in budget_info and "max" in budget_info:
            avg_budget = (budget_info["min"] + budget_info["max"]) / 2
        elif budget_info["amounts"]:
            avg_budget = sum(budget_info["amounts"]) / len(budget_info["amounts"])
            budget_info["min"] = avg_budget * 0.8
            budget_info["max"] = avg_budget * 1.2
        else:
            return None
        
        # Classify budget range
        if avg_budget < 5000:
            budget_info["range"] = BudgetRange.UNDER_5K
        elif avg_budget < 15000:
            budget_info["range"] = BudgetRange.RANGE_5K_15K
        elif avg_budget < 30000:
            budget_info["range"] = BudgetRange.RANGE_15K_30K
        elif avg_budget < 50000:
            budget_info["range"] = BudgetRange.RANGE_30K_50K
        elif avg_budget < 100000:
            budget_info["range"] = BudgetRange.RANGE_50K_100K
        else:
            budget_info["range"] = BudgetRange.OVER_100K
        
        # Check for flexibility indicators
        if any(word in text.lower() for word in ["firm", "fixed", "exactly", "must be"]):
            budget_info["flexibility"] = "firm"
        elif any(word in text.lower() for word in ["flexible", "around", "approximately", "roughly"]):
            budget_info["flexibility"] = "flexible"
        
        return budget_info if budget_info["amounts"] or "min" in budget_info else None
    
    def _extract_timeline_info(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract timeline information from text"""
        
        timeline_info = {}
        
        # Extract duration patterns
        for pattern in self.timeline_patterns["duration_patterns"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 1:
                    timeline_info["duration"] = match.group(0)
                else:
                    timeline_info["duration"] = f"{match.group(1)}-{match.group(2)} {match.group(0).split()[-1]}"
                break
        
        # Extract urgency indicators
        for pattern in self.timeline_patterns["urgency_patterns"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                urgency_text = match.group(0).lower()
                if any(urgent in urgency_text for urgent in ["asap", "urgent", "rush", "emergency", "immediately"]):
                    timeline_info["urgency"] = UrgencyLevel.URGENT
                elif any(flexible in urgency_text for flexible in ["flexible", "whenever", "no rush"]):
                    timeline_info["urgency"] = UrgencyLevel.FLEXIBLE
                else:
                    timeline_info["urgency"] = UrgencyLevel.NORMAL
                break
        
        # Extract start time preferences
        for pattern in self.timeline_patterns["start_time_patterns"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                timeline_info["start_preference"] = match.group(1)
                break
        
        return timeline_info if timeline_info else None
    
    def _extract_room_info(self, text: str) -> List[str]:
        """Extract room/location information from text"""
        
        found_rooms = []
        text_lower = text.lower()
        
        # Check for room keywords
        for room in self.room_patterns["rooms"]:
            if room in text_lower:
                # Check for modifiers
                for modifier in self.room_patterns["room_modifiers"]:
                    modifier_pattern = f"{modifier}\\s+{room}"
                    if re.search(modifier_pattern, text_lower):
                        found_rooms.append(f"{modifier} {room}")
                        break
                else:
                    found_rooms.append(room)
        
        # Check for outdoor areas
        for area in self.room_patterns["outdoor_areas"]:
            if area in text_lower:
                found_rooms.append(area)
        
        return list(set(found_rooms))  # Remove duplicates
    
    def _extract_material_info(self, text: str) -> Dict[str, List[str]]:
        """Extract materials and brands from text"""
        
        material_info = {"materials": [], "brands": []}
        text_lower = text.lower()
        
        # Extract materials by category
        for category, materials in self.material_patterns["materials"].items():
            for material in materials:
                if material in text_lower:
                    material_info["materials"].append(material)
        
        # Extract brand mentions
        for brand in self.material_patterns["brands"]:
            if brand.lower() in text_lower:
                material_info["brands"].append(brand)
        
        return material_info
    
    def _extract_project_type(self, text: str) -> Optional[ProjectType]:
        """Extract project type from text"""
        
        text_lower = text.lower()
        
        # Project type keywords mapping
        type_keywords = {
            ProjectType.BATHROOM_REMODEL: ["bathroom", "shower", "tub", "vanity", "toilet"],
            ProjectType.KITCHEN_REMODEL: ["kitchen", "cabinet", "countertop", "appliance"],
            ProjectType.FLOORING: ["floor", "carpet", "tile", "hardwood", "laminate"],
            ProjectType.PAINTING: ["paint", "color", "wall", "ceiling"],
            ProjectType.PLUMBING: ["plumbing", "pipe", "leak", "drain", "faucet", "water"],
            ProjectType.ELECTRICAL: ["electrical", "outlet", "switch", "wiring", "light"],
            ProjectType.HVAC: ["hvac", "heating", "cooling", "air conditioning", "furnace"],
            ProjectType.ROOFING: ["roof", "shingles", "gutter", "chimney"],
            ProjectType.LANDSCAPING: ["landscape", "garden", "lawn", "plants", "trees"],
            ProjectType.DECK_PATIO: ["deck", "patio", "outdoor living"],
        }
        
        # Score each project type
        type_scores = {}
        for project_type, keywords in type_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                type_scores[project_type] = score
        
        # Return highest scoring type
        if type_scores:
            return max(type_scores.items(), key=lambda x: x[1])[0]
        
        return ProjectType.GENERAL_REPAIR  # Default fallback
    
    def _extract_special_considerations(self, text: str) -> Dict[str, List[str]]:
        """Extract special considerations from text"""
        
        considerations = {"accessibility": [], "pets": [], "family": [], "environmental": []}
        text_lower = text.lower()
        
        # Accessibility keywords
        accessibility_keywords = ["wheelchair", "accessible", "handicap", "mobility", "ramp", "grab bars"]
        for keyword in accessibility_keywords:
            if keyword in text_lower:
                considerations["accessibility"].append(keyword)
        
        # Pet considerations
        pet_keywords = ["dog", "cat", "pet", "animal", "litter box", "pet door"]
        for keyword in pet_keywords:
            if keyword in text_lower:
                considerations["pets"].append(keyword)
        
        # Family considerations
        family_keywords = ["children", "kids", "baby", "elderly", "senior", "family"]
        for keyword in family_keywords:
            if keyword in text_lower:
                considerations["family"].append(keyword)
        
        # Environmental preferences
        env_keywords = ["eco-friendly", "green", "sustainable", "organic", "low VOC", "energy efficient"]
        for keyword in env_keywords:
            if keyword in text_lower:
                considerations["environmental"].append(keyword)
        
        return considerations
    
    async def _extract_from_form_data(self, project_data: ProjectData, form_data: Dict[str, Any]):
        """Extract data from structured form input"""
        
        # Direct field mappings
        field_mappings = {
            "budget_min": "budget_min",
            "budget_max": "budget_max", 
            "timeline": "timeline_duration",
            "urgency": "urgency_level",
            "rooms": "room_locations",
            "materials": "materials_mentioned",
            "address": "property_address",
            "property_type": "property_type"
        }
        
        for form_field, data_field in field_mappings.items():
            if form_field in form_data and form_data[form_field]:
                setattr(project_data, data_field, form_data[form_field])
        
        # Handle enum conversions
        if "urgency" in form_data:
            try:
                project_data.urgency_level = UrgencyLevel(form_data["urgency"])
            except ValueError:
                pass  # Keep default
        
        if "project_type" in form_data:
            try:
                project_data.project_type = ProjectType(form_data["project_type"])
            except ValueError:
                pass  # Keep extracted value
    
    async def _integrate_nlp_results(self, project_data: ProjectData, nlp_results: Dict[str, Any]):
        """Integrate results from NLP processing"""
        
        # Map NLP results to project data
        if "project_type" in nlp_results and not hasattr(project_data, 'project_type'):
            try:
                project_data.project_type = ProjectType(nlp_results["project_type"])
            except ValueError:
                project_data.project_type = ProjectType.GENERAL_REPAIR
        
        if "specific_requirements" in nlp_results:
            project_data.specific_requirements.extend(nlp_results["specific_requirements"])
        
        if "materials_mentioned" in nlp_results:
            project_data.materials_mentioned.extend(nlp_results["materials_mentioned"])
        
        if "room_locations" in nlp_results:
            project_data.room_locations.extend(nlp_results["room_locations"])
        
        if "unclear_requirements" in nlp_results:
            project_data.unclear_requirements.extend(nlp_results["unclear_requirements"])
        
        # Integrate budget information
        if "budget_range" in nlp_results and nlp_results["budget_range"]:
            budget_data = nlp_results["budget_range"]
            if "min" in budget_data:
                project_data.budget_min = budget_data["min"]
            if "max" in budget_data:
                project_data.budget_max = budget_data["max"]
        
        # Integrate timeline information
        if "timeline_estimate" in nlp_results and nlp_results["timeline_estimate"]:
            timeline_data = nlp_results["timeline_estimate"]
            if "duration" in timeline_data:
                project_data.timeline_duration = timeline_data["duration"]
            if "urgency" in timeline_data:
                try:
                    project_data.urgency_level = UrgencyLevel(timeline_data["urgency"])
                except ValueError:
                    pass
    
    async def _post_process_data(self, project_data: ProjectData):
        """Post-process and normalize extracted data"""
        
        # Remove duplicates from lists
        project_data.specific_requirements = list(set(project_data.specific_requirements))
        project_data.materials_mentioned = list(set(project_data.materials_mentioned))
        project_data.room_locations = list(set(project_data.room_locations))
        project_data.unclear_requirements = list(set(project_data.unclear_requirements))
        
        # Normalize budget range if min/max are available
        if project_data.budget_min and project_data.budget_max:
            avg_budget = (project_data.budget_min + project_data.budget_max) / 2
            
            if avg_budget < 5000:
                project_data.budget_range = BudgetRange.UNDER_5K
            elif avg_budget < 15000:
                project_data.budget_range = BudgetRange.RANGE_5K_15K
            elif avg_budget < 30000:
                project_data.budget_range = BudgetRange.RANGE_15K_30K
            elif avg_budget < 50000:
                project_data.budget_range = BudgetRange.RANGE_30K_50K
            elif avg_budget < 100000:
                project_data.budget_range = BudgetRange.RANGE_50K_100K
            else:
                project_data.budget_range = BudgetRange.OVER_100K
        
        # Validate required fields
        if not hasattr(project_data, 'project_type') or not project_data.project_type:
            project_data.project_type = ProjectType.GENERAL_REPAIR
            project_data.unclear_requirements.append("project_type_unclear")
    
    def _calculate_quality_scores(self, project_data: ProjectData):
        """Calculate completeness and confidence scores"""
        
        # Define scoring weights
        field_weights = {
            "project_type": 0.20,
            "specific_requirements": 0.15,
            "budget_info": 0.15,
            "timeline_info": 0.15,
            "room_locations": 0.10,
            "materials_mentioned": 0.10,
            "description": 0.15
        }
        
        # Calculate completeness score
        completeness_scores = {}
        
        # Project type score
        completeness_scores["project_type"] = 1.0 if project_data.project_type != ProjectType.GENERAL_REPAIR else 0.5
        
        # Requirements score
        completeness_scores["specific_requirements"] = min(len(project_data.specific_requirements) * 0.2, 1.0)
        
        # Budget score
        budget_score = 0.0
        if project_data.budget_min and project_data.budget_max:
            budget_score = 1.0
        elif project_data.budget_range != BudgetRange.UNKNOWN:
            budget_score = 0.7
        completeness_scores["budget_info"] = budget_score
        
        # Timeline score
        timeline_score = 0.0
        if project_data.timeline_duration:
            timeline_score += 0.5
        if project_data.urgency_level != UrgencyLevel.NORMAL:
            timeline_score += 0.5
        completeness_scores["timeline_info"] = min(timeline_score, 1.0)
        
        # Room locations score
        completeness_scores["room_locations"] = min(len(project_data.room_locations) * 0.3, 1.0)
        
        # Materials score
        completeness_scores["materials_mentioned"] = min(len(project_data.materials_mentioned) * 0.2, 1.0)
        
        # Description score
        completeness_scores["description"] = min(len(project_data.description) / 100, 1.0)
        
        # Calculate weighted completeness score
        project_data.completeness_score = sum(
            score * field_weights[field] 
            for field, score in completeness_scores.items()
        )
        
        # Calculate confidence score (inverse of unclear requirements)
        max_unclear = len(field_weights)  # Maximum possible unclear requirements
        unclear_ratio = len(project_data.unclear_requirements) / max_unclear
        project_data.confidence_score = max(0.0, 1.0 - unclear_ratio)
    
    async def _store_with_mcp(self, project_data: ProjectData):
        """Store extracted data using MCP supabase integration"""
        
        if not self.mcp_client:
            return
        
        try:
            # Convert to dictionary for storage
            data_dict = asdict(project_data)
            
            # Convert enums to strings for JSON serialization
            data_dict["project_type"] = project_data.project_type.value
            data_dict["urgency_level"] = project_data.urgency_level.value
            data_dict["budget_range"] = project_data.budget_range.value
            
            # Store using MCP supabase tool
            await self.mcp_client.call_tool("supabase", {
                "action": "store_project_data",
                "table": "project_extractions",
                "data": data_dict
            })
            
            # Also cache in Redis for quick access
            await self.mcp_client.call_tool("redis", {
                "command": "set",
                "key": f"project_data:{project_data.project_id}",
                "value": json.dumps(data_dict),
                "expiration": 3600  # 1 hour cache
            })
            
        except Exception as e:
            await self.audit_logger.log_event(
                "mcp_storage_failed",
                {"error": str(e), "project_id": project_data.project_id},
                user_id=project_data.homeowner_id,
                severity="error"
            )


# Utility functions for MCP integration
async def extract_with_mcp(mcp_client, raw_input: Dict[str, Any], 
                          project_id: str, homeowner_id: str) -> ProjectData:
    """
    Extract project data using MCP tools
    
    This function integrates with the MCP ecosystem to:
    1. Research extraction patterns with context7
    2. Coordinate with Redis for event handling
    3. Store results in Supabase
    """
    
    extractor = DataExtractor(mcp_client=mcp_client)
    
    # Use MCP context7 tool for extraction pattern research if needed
    if mcp_client:
        try:
            # Research best practices for data extraction
            research_result = await mcp_client.call_tool("context7", {
                "query": "project data extraction construction industry",
                "topic": "structured data conversion"
            })
            
        except Exception as e:
            # Continue processing even if MCP research fails
            pass
    
    # Extract the project data
    project_data = await extractor.extract_project_data(raw_input, project_id, homeowner_id)
    
    return project_data


def convert_to_dict(project_data: ProjectData) -> Dict[str, Any]:
    """Convert ProjectData to dictionary for serialization"""
    data_dict = asdict(project_data)
    
    # Convert enums to strings
    data_dict["project_type"] = project_data.project_type.value
    data_dict["urgency_level"] = project_data.urgency_level.value  
    data_dict["budget_range"] = project_data.budget_range.value
    
    return data_dict


def create_from_dict(data_dict: Dict[str, Any]) -> ProjectData:
    """Create ProjectData from dictionary"""
    
    # Convert string values back to enums
    if "project_type" in data_dict:
        data_dict["project_type"] = ProjectType(data_dict["project_type"])
    if "urgency_level" in data_dict:
        data_dict["urgency_level"] = UrgencyLevel(data_dict["urgency_level"])
    if "budget_range" in data_dict:
        data_dict["budget_range"] = BudgetRange(data_dict["budget_range"])
    
    return ProjectData(**data_dict)
