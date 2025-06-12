"""
Core Security Module - Business Model Protection

This module contains the critical security components that protect the Instabids
business model by preventing contact information leakage and controlling costs.

🛡️ CRITICAL: These components are essential for business viability:
- ContactProtectionFilter: Prevents contact info sharing before payment
- ViolationTracker: Escalates security violations 
- CostCircuitBreaker: Prevents runaway AI costs
- AuditLogger: Ensures compliance and security logging

All security components integrate with MCP tools for Codex agent usage.
"""

from .contact_filter import ContactProtectionFilter, MultiLayerContactDetector
from .violation_tracker import ViolationHandler, SecurityViolationTracker
from .cost_breaker import (
    CostCircuitBreaker, 
    CostTier, 
    CostViolationType,
    check_operation_cost,
    record_operation_cost,
    get_cost_status,
    get_cost_for_tier
)
from .audit_logger import (
    AuditLogger,
    AuditEventType,
    AuditSeverity,
    AuditEvent,
    log_security_event,
    log_business_event,
    log_data_access_event,
    log_agent_event
)

# Global instances for easy access
contact_filter = ContactProtectionFilter()
cost_breaker = CostCircuitBreaker()
audit_logger = AuditLogger()

__all__ = [
    # Contact Protection
    'ContactProtectionFilter',
    'MultiLayerContactDetector',
    'contact_filter',
    
    # Violation Tracking
    'ViolationHandler', 
    'SecurityViolationTracker',
    
    # Cost Protection
    'CostCircuitBreaker',
    'CostTier',
    'CostViolationType', 
    'cost_breaker',
    'check_operation_cost',
    'record_operation_cost',
    'get_cost_status',
    'get_cost_for_tier',
    
    # Audit Logging
    'AuditLogger',
    'AuditEventType',
    'AuditSeverity', 
    'AuditEvent',
    'audit_logger',
    'log_security_event',
    'log_business_event',
    'log_data_access_event',
    'log_agent_event'
]

# Security configuration
SECURITY_CONFIG = {
    "contact_protection_enabled": True,
    "cost_limits_enabled": True,
    "audit_logging_enabled": True,
    "violation_tracking_enabled": True,
    
    # Default limits
    "default_daily_cost_limit": 1000.0,
    "default_per_event_cost_limit": 0.05,
    "emergency_cost_threshold": 2000.0,
    
    # Contact protection settings
    "max_violations_per_user": 3,
    "violation_escalation_enabled": True,
    "auto_ban_enabled": True,
    
    # Audit settings
    "audit_retention_days": 2555,  # 7 years for compliance
    "real_time_monitoring": True,
    "compliance_reporting": True
}


async def initialize_security_system() -> dict:
    """
    Initialize the complete security system
    
    Returns:
        dict: Initialization status for all components
    """
    results = {}
    
    try:
        # Initialize contact protection
        # Contact filter is ready to use immediately
        results["contact_protection"] = "initialized"
        
        # Initialize cost protection
        # Cost breaker is ready to use immediately  
        results["cost_protection"] = "initialized"
        
        # Initialize audit logging
        # Audit logger is ready to use immediately
        results["audit_logging"] = "initialized"
        
        # Initialize violation tracking
        # Violation tracker is ready to use immediately
        results["violation_tracking"] = "initialized"
        
        results["overall_status"] = "success"
        results["message"] = "All security systems initialized successfully"
        
    except Exception as e:
        results["overall_status"] = "error" 
        results["error"] = str(e)
        results["message"] = f"Security system initialization failed: {e}"
    
    return results


async def get_security_status() -> dict:
    """
    Get comprehensive security system status
    
    Returns:
        dict: Status of all security components
    """
    return {
        "contact_protection": {
            "enabled": SECURITY_CONFIG["contact_protection_enabled"],
            "status": "operational",
            "patterns_loaded": True
        },
        "cost_protection": {
            "enabled": SECURITY_CONFIG["cost_limits_enabled"],
            "status": "operational", 
            "daily_limit": SECURITY_CONFIG["default_daily_cost_limit"],
            "per_event_limit": SECURITY_CONFIG["default_per_event_cost_limit"]
        },
        "audit_logging": {
            "enabled": SECURITY_CONFIG["audit_logging_enabled"],
            "status": "operational",
            "retention_days": SECURITY_CONFIG["audit_retention_days"]
        },
        "violation_tracking": {
            "enabled": SECURITY_CONFIG["violation_tracking_enabled"], 
            "status": "operational",
            "escalation_enabled": SECURITY_CONFIG["violation_escalation_enabled"]
        }
    }


# Critical business model protection functions
async def protect_contact_sharing(content: str, user_id: str) -> dict:
    """
    CRITICAL: Protect against contact information sharing
    
    This is the core business model protection - contact info can only
    be shared after payment is confirmed.
    
    Args:
        content: Content to scan for contact information
        user_id: User ID for violation tracking
        
    Returns:
        dict: Protection result with violations found
    """
    # Scan for contact violations
    violations = contact_filter.scan_content(content)
    
    if violations["violations_found"]:
        # Log security violation
        await log_security_event(
            "contact_sharing_attempt",
            {
                "user_id": user_id,
                "violations": violations,
                "content_length": len(content)
            },
            user_id
        )
        
        # Record cost if this required AI processing
        await record_operation_cost(0.01, "contact_protection")
        
        return {
            "blocked": True,
            "violations": violations,
            "reason": "Contact information detected and blocked"
        }
    
    return {
        "blocked": False,
        "violations": None,
        "reason": "Content approved"
    }


async def check_and_record_cost(
    estimated_cost: float,
    operation_type: str,
    context: dict = None
) -> dict:
    """
    CRITICAL: Check cost approval and record actual usage
    
    This prevents runaway AI costs that could bankrupt the business.
    
    Args:
        estimated_cost: Estimated cost of operation
        operation_type: Type of operation for tracking
        context: Additional context for logging
        
    Returns:
        dict: Cost approval result
    """
    # Check if operation should proceed
    approval = await check_operation_cost(estimated_cost, operation_type, context)
    
    # Log the cost check
    await log_agent_event(
        "cost_system",
        "cost_check_performed",
        {
            "estimated_cost": estimated_cost,
            "operation_type": operation_type,
            "approved": approval["approved"],
            "reason": approval["reason"]
        }
    )
    
    return approval


# Module validation
def validate_security_module() -> bool:
    """Validate that all security components are properly loaded"""
    required_components = [
        'contact_filter',
        'cost_breaker', 
        'audit_logger'
    ]
    
    for component in required_components:
        if component not in globals():
            return False
    
    return True


# Initialize on import
if not validate_security_module():
    raise ImportError("Critical security components failed to load")
