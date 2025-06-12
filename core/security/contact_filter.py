"""
Multi-Layer Contact Protection Filter - BUSINESS MODEL CORE
Core Security Foundation - Agent 4 will build full implementation

This is the ABSOLUTE CRITICAL component for Instabids business model.
Contact information must NEVER leak until payment is confirmed.
100% violation detection rate required.
"""

import re
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from core import mcp


class ContactProtectionFilter:
    """
    Multi-layer contact information detection system
    
    CRITICAL: This protects the core business model.
    Contact info must be blocked with 100% accuracy.
    """
    
    def __init__(self):
        self.phone_patterns = self._initialize_phone_patterns()
        self.email_patterns = self._initialize_email_patterns()
        self.social_patterns = self._initialize_social_patterns()
        self.intent_patterns = self._initialize_intent_patterns()
        self.obfuscation_patterns = self._initialize_obfuscation_patterns()
        
    def _initialize_phone_patterns(self) -> List[str]:
        """Initialize comprehensive phone number detection patterns"""
        return [
            # Standard US formats
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',
            r'\b\d{3}\s+\d{3}\s+\d{4}\b',
            
            # International formats
            r'\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\+\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
            
            # Obfuscated formats (CRITICAL - users try to bypass)
            r'\b\d{3}[^\d\w]{1,3}\d{3}[^\d\w]{1,3}\d{4}\b',
            r'(?:call|text|phone)[\s:]*\d{3}',
            
            # Written out numbers
            r'(?:five|six|seven|eight|nine)[\s-]*(?:zero|one|two|three|four|five|six|seven|eight|nine)[\s-]*(?:zero|one|two|three|four|five|six|seven|eight|nine)',
            
            # Unicode/emoji obfuscation (advanced bypass attempts)
            r'[0-9️⃣]{3,}[-\s]*[0-9️⃣]{3,}[-\s]*[0-9️⃣]{3,}',
            
            # Spaced digits (common bypass)
            r'\d\s+\d\s+\d\s+[-\s]*\d\s+\d\s+\d\s+[-\s]*\d\s+\d\s+\d\s+\d',
            
            # With special characters
            r'\d{3}[^\w\s]\d{3}[^\w\s]\d{4}'
        ]
    
    def _initialize_email_patterns(self) -> List[str]:
        """Initialize comprehensive email detection patterns"""
        return [
            # Standard email
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            
            # Obfuscated emails (CRITICAL - common bypass)
            r'\b[A-Za-z0-9._%+-]+\s*\[?at\]?\s*[A-Za-z0-9.-]+\s*\[?dot\]?\s*[A-Z|a-z]{2,}\b',
            r'\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Z|a-z]{2,}\b',
            
            # Social media style
            r'(?:email|gmail|yahoo|hotmail|outlook)[\s:]*[A-Za-z0-9._%+-]+',
            
            # Spelled out
            r'\b[A-Za-z0-9._%+-]+\s+at\s+[A-Za-z0-9.-]+\s+dot\s+[A-Z|a-z]{2,}\b',
            
            # Alternative symbols
            r'\b[A-Za-z0-9._%+-]+\s*\[at\]\s*[A-Za-z0-9.-]+\s*\[dot\]\s*[A-Z|a-z]{2,}\b'
        ]
    
    def _initialize_social_patterns(self) -> List[str]:
        """Initialize social media handle detection"""
        return [
            r'@[A-Za-z0-9_]+',  # @username
            r'(?:instagram|facebook|twitter|linkedin|snapchat|tiktok)[\s:/@]*[A-Za-z0-9._]+',
            r'(?:find|follow|add|connect)\s+me\s+on\s+(?:instagram|facebook|twitter|linkedin)',
            r'(?:fb|ig|twitter|linkedin)[\s:]*[A-Za-z0-9._]+',
            r'(?:dm|message)\s+me\s+on'
        ]
    
    def _initialize_intent_patterns(self) -> List[str]:
        """Initialize contact sharing intent detection (CRITICAL)"""
        return [
            # Direct contact requests
            r'(?:call|text|email|contact|reach)\s+me\s+(?:at|on|directly)',
            r'(?:my|the)\s+(?:number|phone|cell|email|contact)',
            r'(?:give|send)\s+me\s+(?:your|a)\s+(?:call|text|email|number)',
            
            # Platform bypass attempts (BUSINESS CRITICAL)
            r'let[\'s]*\s+(?:talk|chat|discuss)\s+(?:offline|directly|outside|privately)',
            r'(?:bypass|skip|avoid)\s+(?:the\s+)?platform',
            r'(?:direct|personal|private)\s+(?:contact|communication)',
            r'(?:take\s+this\s+)?(?:offline|outside)',
            
            # Messaging app references
            r'(?:whatsapp|telegram|signal|discord|messenger)\s+me',
            r'(?:send|share)\s+(?:your|my)\s+(?:contact|info|details)',
            
            # Meeting requests outside platform
            r'(?:meet|talk)\s+(?:outside|away\s+from)\s+(?:here|platform)',
            r'(?:continue\s+)?(?:conversation|discussion)\s+(?:elsewhere|privately)'
        ]
    
    def _initialize_obfuscation_patterns(self) -> List[str]:
        """Initialize obfuscation detection patterns (CRITICAL for business)"""
        return [
            # Written numbers
            r'(?:zero|one|two|three|four|five|six|seven|eight|nine)[\s-]*(?:zero|one|two|three|four|five|six|seven|eight|nine)',
            
            # Spaced digits
            r'\d\s*[\-\.]*\s*\d\s*[\-\.]*\s*\d',
            
            # Digits with special chars
            r'[0-9]\s*[^\w\s]\s*[0-9]',
            
            # Domain obfuscation
            r'(?:gmail|yahoo|hotmail)\s+(?:dot|period)\s+(?:com|org|net)',
            
            # Phone number hints
            r'phone\s*(?:number\s*)?(?:is\s*)?[:]*\s*\d',
            r'(?:call|text)\s+(?:me\s+)?(?:at\s+)?\d',
            
            # Creative separators
            r'\d+[^\w\d\s]+\d+[^\w\d\s]+\d+'
        ]
    
    async def scan_content(self, content: str, user_id: str, 
                          context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        CRITICAL: Comprehensive content scanning for contact information
        
        This function MUST detect ALL contact sharing attempts.
        Business model depends on 100% accuracy.
        
        Args:
            content: Text content to scan
            user_id: User ID for violation tracking
            context: Additional context (event type, etc.)
            
        Returns:
            Dict with violation analysis
        """
        
        results = {
            "violations_found": False,
            "violation_types": [],
            "detected_patterns": [],
            "confidence_scores": {},
            "user_id": user_id,
            "content_original": content,
            "content_filtered": content,
            "risk_level": "low",
            "scan_timestamp": datetime.utcnow().isoformat()
        }
        
        content_lower = content.lower()
        all_violations = []
        
        # Layer 1: Direct pattern matching
        phone_violations = self._detect_phones(content)
        email_violations = self._detect_emails(content)
        social_violations = self._detect_social_media(content)
        
        # Layer 2: Intent analysis (CRITICAL)
        intent_violations = self._detect_contact_intent(content_lower)
        
        # Layer 3: Obfuscation detection
        obfuscation_violations = self._detect_obfuscation(content_lower)
        
        # Layer 4: Context analysis
        context_violations = await self._analyze_context(content, user_id, context)
        
        # Compile all violations
        all_violations = (
            phone_violations + email_violations + social_violations +
            intent_violations + obfuscation_violations + context_violations
        )
        
        if all_violations:
            results["violations_found"] = True
            results["violation_types"] = list(set([v["type"] for v in all_violations]))
            results["detected_patterns"] = all_violations
            results["risk_level"] = self._calculate_risk_level(all_violations)
            results["content_filtered"] = self._apply_content_filtering(content, all_violations)
            
            # Log violation for business intelligence
            await self._log_violation(user_id, results)
        
        return results
    
    def _detect_phones(self, content: str) -> List[Dict]:
        """Detect phone numbers with all patterns"""
        violations = []
        
        for pattern in self.phone_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                violations.append({
                    "type": "phone_number",
                    "pattern": pattern,
                    "match": match.group(),
                    "position": match.span(),
                    "confidence": 0.95
                })
        
        return violations
    
    def _detect_emails(self, content: str) -> List[Dict]:
        """Detect email addresses with all patterns"""
        violations = []
        
        for pattern in self.email_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                violations.append({
                    "type": "email_address",
                    "pattern": pattern,
                    "match": match.group(),
                    "position": match.span(),
                    "confidence": 0.90
                })
        
        return violations
    
    def _detect_contact_intent(self, content: str) -> List[Dict]:
        """Detect intent to share contact information (BUSINESS CRITICAL)"""
        violations = []
        
        for pattern in self.intent_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                violations.append({
                    "type": "contact_intent",
                    "pattern": pattern,
                    "match": match.group(),
                    "position": match.span(),
                    "confidence": 0.85
                })
        
        return violations
    
    async def _analyze_context(self, content: str, user_id: str, 
                             context: Optional[Dict]) -> List[Dict]:
        """Analyze contextual clues for contact sharing"""
        violations = []
        
        # Check for suspicious patterns in context
        sentences = content.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip().lower()
            
            # Imperative contact statements
            if any(intent in sentence for intent in ["call me", "text me", "email me", "contact me"]):
                violations.append({
                    "type": "contact_imperative",
                    "match": sentence,
                    "confidence": 0.85,
                    "analysis": "imperative_contact_request"
                })
            
            # Contact provision statements
            if any(provision in sentence for provision in ["my number is", "email me at", "reach me at"]):
                violations.append({
                    "type": "contact_provision",
                    "match": sentence,
                    "confidence": 0.90,
                    "analysis": "providing_contact_info"
                })
        
        return violations
    
    def _apply_content_filtering(self, content: str, violations: List[Dict]) -> str:
        """Apply filtering to remove/mask contact information"""
        filtered_content = content
        
        # Sort violations by position (reverse order to maintain positions)
        violations_sorted = sorted(
            [v for v in violations if "position" in v], 
            key=lambda x: x["position"][0], 
            reverse=True
        )
        
        for violation in violations_sorted:
            start, end = violation["position"]
            replacement = self._get_replacement_text(violation["type"])
            filtered_content = filtered_content[:start] + replacement + filtered_content[end:]
        
        return filtered_content
    
    def _get_replacement_text(self, violation_type: str) -> str:
        """Get appropriate replacement text for violation type"""
        replacements = {
            "phone_number": "[PHONE NUMBER BLOCKED]",
            "email_address": "[EMAIL BLOCKED]",
            "social_media": "[SOCIAL MEDIA BLOCKED]",
            "contact_intent": "[CONTACT REQUEST BLOCKED]",
            "contact_provision": "[CONTACT INFO BLOCKED]",
            "contact_imperative": "[CONTACT REQUEST BLOCKED]"
        }
        return replacements.get(violation_type, "[CONTACT INFO BLOCKED]")
    
    def _calculate_risk_level(self, violations: List[Dict]) -> str:
        """Calculate risk level based on violations"""
        if not violations:
            return "low"
        
        high_risk_types = ["phone_number", "email_address", "contact_provision"]
        medium_risk_types = ["contact_intent", "contact_imperative"]
        
        if any(v["type"] in high_risk_types for v in violations):
            return "high"
        elif any(v["type"] in medium_risk_types for v in violations):
            return "medium"
        else:
            return "low"
    
    async def _log_violation(self, user_id: str, results: Dict) -> None:
        """Log violation for business intelligence and enforcement"""
        
        try:
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO contact_violations (
                        user_id, violation_types, risk_level, 
                        detected_patterns_count, timestamp, content_hash
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                "params": [
                    user_id,
                    ",".join(results["violation_types"]),
                    results["risk_level"],
                    len(results["detected_patterns"]),
                    results["scan_timestamp"],
                    hash(results["content_original"])  # Don't store actual content for privacy
                ]
            })
            
            # Publish violation event for real-time enforcement
            await mcp.call_tool("redis", {
                "command": "xadd",
                "stream": "security:violations",
                "fields": {
                    "user_id": user_id,
                    "violation_types": ",".join(results["violation_types"]),
                    "risk_level": results["risk_level"],
                    "timestamp": results["scan_timestamp"]
                }
            })
            
        except Exception as e:
            print(f"Critical: Failed to log contact violation: {e}")


# Quick test patterns for validation
CONTACT_PROTECTION_TEST_CASES = [
    # Direct contact info
    "Call me at 555-123-4567",
    "Email john@example.com",
    "My number is (555) 123-4567",
    
    # Obfuscated
    "Text 555.123.4567",
    "Email john at gmail dot com",
    "Call five five five one two three four five six seven",
    
    # Intent-based
    "Let's take this offline",
    "Contact me directly",
    "Talk outside the platform",
    
    # Should NOT be blocked
    "I need bathroom renovation",
    "Budget is $15,000",
    "Timeline 4-6 weeks"
]


# TODO for Agent 4: Expand this into full multi-layer detection system
# with NLP analysis, machine learning, and advanced obfuscation detection
