"""
Security Violation Tracker for Instabids Agent Swarm
Manages user violation escalation and enforcement actions.
CRITICAL: This protects the core business model by preventing contact information sharing.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

# MCP Integration Pattern
class MCPClient:
    """MCP Tool wrapper for operations"""
    async def call_tool(self, tool_name: str, args: dict):
        """
        Wrapper for MCP tool calls - will be replaced by actual MCP implementation
        """
        # TODO: Replace with actual MCP calling mechanism in Codex environment
        pass

# Global MCP client instance
mcp = MCPClient()

class ViolationSeverity(Enum):
    """Violation severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class EnforcementAction(Enum):
    """Available enforcement actions"""
    WARNING = "warning"
    CONTENT_BLOCK = "content_block"
    MESSAGING_RESTRICTION = "messaging_restriction"
    ACCOUNT_SUSPENSION = "account_suspension"
    PERMANENT_BAN = "permanent_ban"
    ADMIN_ALERT = "admin_alert"

@dataclass
class ViolationRecord:
    """Individual violation record"""
    id: str
    user_id: str
    violation_type: str
    severity: ViolationSeverity
    content: str
    detection_method: str
    timestamp: datetime
    action_taken: EnforcementAction
    escalation_level: int
    resolved: bool = False

@dataclass
class UserViolationProfile:
    """User's complete violation profile"""
    user_id: str
    total_violations: int
    escalation_level: int
    last_violation: Optional[datetime]
    account_status: str  # active, restricted, suspended, banned
    violations: List[ViolationRecord]

class ViolationTracker:
    """
    Tracks security violations and manages user escalation
    Implements progressive enforcement to protect business model
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Escalation configuration
        self.escalation_rules = {
            1: {
                "action": EnforcementAction.WARNING,
                "duration_hours": None,  # Permanent warning record
                "description": "First violation - warning issued"
            },
            2: {
                "action": EnforcementAction.MESSAGING_RESTRICTION,
                "duration_hours": 24,
                "description": "Second violation - 24h messaging restriction"
            },
            3: {
                "action": EnforcementAction.ACCOUNT_SUSPENSION,
                "duration_hours": 168,  # 1 week
                "description": "Third violation - 1 week account suspension"
            },
            4: {
                "action": EnforcementAction.PERMANENT_BAN,
                "duration_hours": None,  # Permanent
                "description": "Fourth violation - permanent ban"
            }
        }
        
        # Severity multipliers for escalation
        self.severity_multipliers = {
            ViolationSeverity.LOW: 1,
            ViolationSeverity.MEDIUM: 2,
            ViolationSeverity.HIGH: 3,
            ViolationSeverity.CRITICAL: 5  # Critical violations skip levels
        }
        
        # Performance tracking
        self.tracker_metrics = {
            "violations_processed": 0,
            "users_warned": 0,
            "users_restricted": 0,
            "users_suspended": 0,
            "users_banned": 0,
            "false_positives": 0
        }
    
    async def process_violation(self, user_id: str, violation_type: str,
                               content: str, severity: ViolationSeverity,
                               detection_method: str = "automated") -> ViolationRecord:
        """
        Process a security violation and apply appropriate enforcement
        Returns: ViolationRecord with action taken
        """
        import uuid
        
        try:
            # Get user's violation history
            user_profile = await self.get_user_violation_profile(user_id)
            
            # Calculate new escalation level
            severity_points = self.severity_multipliers[severity]
            new_escalation_level = user_profile.escalation_level + severity_points
            
            # Cap at maximum escalation level
            new_escalation_level = min(new_escalation_level, max(self.escalation_rules.keys()))
            
            # Create violation record
            violation_record = ViolationRecord(
                id=str(uuid.uuid4()),
                user_id=user_id,
                violation_type=violation_type,
                severity=severity,
                content=content[:500],  # Limit content length for storage
                detection_method=detection_method,
                timestamp=datetime.utcnow(),
                action_taken=self.escalation_rules[new_escalation_level]["action"],
                escalation_level=new_escalation_level
            )
            
            # Store violation in database
            await self._store_violation_record(violation_record)
            
            # Apply enforcement action
            await self._apply_enforcement_action(violation_record, user_profile)
            
            # Update user's escalation level
            await self._update_user_escalation_level(user_id, new_escalation_level)
            
            # Send alerts for serious violations
            if severity in [ViolationSeverity.HIGH, ViolationSeverity.CRITICAL]:
                await self._send_admin_alert(violation_record)
            
            # Update metrics
            self.tracker_metrics["violations_processed"] += 1
            self._update_action_metrics(violation_record.action_taken)
            
            self.logger.warning(
                f"Violation processed: User {user_id}, Type: {violation_type}, "
                f"Level: {new_escalation_level}, Action: {violation_record.action_taken.value}"
            )
            
            return violation_record
            
        except Exception as e:
            self.logger.error(f"Failed to process violation for user {user_id}: {e}")
            raise
    
    async def get_user_violation_profile(self, user_id: str) -> UserViolationProfile:
        """Get complete violation profile for user"""
        try:
            # Get violation history from Supabase
            result = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    SELECT id, violation_type, severity, action_taken, 
                           escalation_level, timestamp, resolved
                    FROM security_violations 
                    WHERE user_id = %(user_id)s
                    ORDER BY timestamp DESC
                    LIMIT 50
                """,
                "params": {"user_id": user_id}
            })
            
            violations = []
            current_escalation_level = 0
            last_violation = None
            
            if result:
                for row in result:
                    violation = ViolationRecord(
                        id=row["id"],
                        user_id=user_id,
                        violation_type=row["violation_type"],
                        severity=ViolationSeverity(row["severity"]),
                        content="[STORED_CONTENT]",  # Don't reload content
                        detection_method="stored",
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        action_taken=EnforcementAction(row["action_taken"]),
                        escalation_level=row["escalation_level"],
                        resolved=row["resolved"]
                    )
                    violations.append(violation)
                    
                    # Track highest escalation level
                    if violation.escalation_level > current_escalation_level:
                        current_escalation_level = violation.escalation_level
                    
                    # Track most recent violation
                    if not last_violation or violation.timestamp > last_violation:
                        last_violation = violation.timestamp
            
            # Determine current account status
            account_status = await self._get_account_status(user_id, current_escalation_level)
            
            return UserViolationProfile(
                user_id=user_id,
                total_violations=len(violations),
                escalation_level=current_escalation_level,
                last_violation=last_violation,
                account_status=account_status,
                violations=violations
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get user violation profile: {e}")
            return UserViolationProfile(
                user_id=user_id,
                total_violations=0,
                escalation_level=0,
                last_violation=None,
                account_status="active",
                violations=[]
            )
    
    async def _store_violation_record(self, violation: ViolationRecord) -> bool:
        """Store violation record in database"""
        try:
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO security_violations 
                    (id, user_id, violation_type, violation_data, severity, 
                     action_taken, escalation_level, timestamp)
                    VALUES (%(id)s, %(user_id)s, %(violation_type)s, %(violation_data)s,
                           %(severity)s, %(action_taken)s, %(escalation_level)s, %(timestamp)s)
                """,
                "params": {
                    "id": violation.id,
                    "user_id": violation.user_id,
                    "violation_type": violation.violation_type,
                    "violation_data": {
                        "content": violation.content,
                        "detection_method": violation.detection_method
                    },
                    "severity": violation.severity.value,
                    "action_taken": violation.action_taken.value,
                    "escalation_level": violation.escalation_level,
                    "timestamp": violation.timestamp.isoformat()
                }
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store violation record: {e}")
            return False
    
    async def _apply_enforcement_action(self, violation: ViolationRecord, 
                                       user_profile: UserViolationProfile) -> bool:
        """Apply the determined enforcement action"""
        try:
            action = violation.action_taken
            duration_hours = self.escalation_rules[violation.escalation_level].get("duration_hours")
            
            if action == EnforcementAction.WARNING:
                await self._send_warning_message(violation)
                
            elif action == EnforcementAction.CONTENT_BLOCK:
                await self._block_content(violation)
                
            elif action == EnforcementAction.MESSAGING_RESTRICTION:
                await self._restrict_messaging(violation.user_id, duration_hours)
                
            elif action == EnforcementAction.ACCOUNT_SUSPENSION:
                await self._suspend_account(violation.user_id, duration_hours)
                
            elif action == EnforcementAction.PERMANENT_BAN:
                await self._ban_account_permanently(violation.user_id)
            
            # Always log the action in audit trail
            await self._log_enforcement_action(violation, action)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to apply enforcement action: {e}")
            return False
    
    async def _send_warning_message(self, violation: ViolationRecord) -> bool:
        """Send warning message to user"""
        try:
            warning_message = {
                "type": "security_warning",
                "user_id": violation.user_id,
                "title": "Content Policy Violation Detected",
                "message": f"""
                We detected a potential violation of our contact sharing policy in your recent activity.
                
                Violation Type: {violation.violation_type}
                Detected: {violation.timestamp.strftime('%Y-%m-%d %H:%M UTC')}
                
                Please remember that sharing contact information directly is not allowed.
                Continue to follow our guidelines to maintain your account in good standing.
                
                This is violation #{violation.escalation_level} on your account.
                """,
                "severity": "warning"
            }
            
            # Send warning via notification system
            await mcp.call_tool("redis", {
                "command": "xadd",
                "stream": "notifications:user_warnings",
                "fields": warning_message
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send warning message: {e}")
            return False
    
    async def _restrict_messaging(self, user_id: str, duration_hours: Optional[int]) -> bool:
        """Restrict user's messaging capabilities"""
        try:
            expiry_time = None
            if duration_hours:
                expiry_time = datetime.utcnow() + timedelta(hours=duration_hours)
            
            # Set messaging restriction in Redis
            restriction_data = {
                "restricted": True,
                "reason": "contact_policy_violation",
                "expires_at": expiry_time.isoformat() if expiry_time else None,
                "restricted_at": datetime.utcnow().isoformat()
            }
            
            await mcp.call_tool("redis", {
                "command": "hset",
                "key": f"user:restrictions:{user_id}",
                "fields": restriction_data
            })
            
            # Set expiry if temporary restriction
            if duration_hours:
                await mcp.call_tool("redis", {
                    "command": "expire",
                    "key": f"user:restrictions:{user_id}",
                    "seconds": duration_hours * 3600
                })
            
            self.logger.warning(f"Messaging restricted for user {user_id} for {duration_hours} hours")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restrict messaging for user {user_id}: {e}")
            return False
    
    async def _suspend_account(self, user_id: str, duration_hours: Optional[int]) -> bool:
        """Suspend user account"""
        try:
            expiry_time = None
            if duration_hours:
                expiry_time = datetime.utcnow() + timedelta(hours=duration_hours)
            
            suspension_data = {
                "suspended": True,
                "reason": "repeated_contact_policy_violations",
                "expires_at": expiry_time.isoformat() if expiry_time else None,
                "suspended_at": datetime.utcnow().isoformat()
            }
            
            await mcp.call_tool("redis", {
                "command": "hset",
                "key": f"user:suspension:{user_id}",
                "fields": suspension_data
            })
            
            if duration_hours:
                await mcp.call_tool("redis", {
                    "command": "expire",
                    "key": f"user:suspension:{user_id}",
                    "seconds": duration_hours * 3600
                })
            
            self.logger.warning(f"Account suspended for user {user_id} for {duration_hours} hours")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to suspend account for user {user_id}: {e}")
            return False
    
    async def _ban_account_permanently(self, user_id: str) -> bool:
        """Permanently ban user account"""
        try:
            ban_data = {
                "banned": True,
                "reason": "repeated_severe_contact_policy_violations",
                "banned_at": datetime.utcnow().isoformat(),
                "permanent": True
            }
            
            await mcp.call_tool("redis", {
                "command": "hset",
                "key": f"user:ban:{user_id}",
                "fields": ban_data
            })
            
            # Also update in Supabase for permanent record
            await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    INSERT INTO user_bans (user_id, reason, banned_at, permanent)
                    VALUES (%(user_id)s, %(reason)s, %(banned_at)s, %(permanent)s)
                    ON CONFLICT (user_id) DO UPDATE SET
                    banned_at = %(banned_at)s, permanent = %(permanent)s
                """,
                "params": {
                    "user_id": user_id,
                    "reason": ban_data["reason"],
                    "banned_at": ban_data["banned_at"],
                    "permanent": True
                }
            })
            
            self.logger.critical(f"Account permanently banned for user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to ban account for user {user_id}: {e}")
            return False
    
    async def _send_admin_alert(self, violation: ViolationRecord) -> bool:
        """Send alert to administrators for serious violations"""
        try:
            alert_data = {
                "type": "high_severity_violation",
                "user_id": violation.user_id,
                "violation_type": violation.violation_type,
                "severity": violation.severity.value,
                "escalation_level": violation.escalation_level,
                "action_taken": violation.action_taken.value,
                "timestamp": violation.timestamp.isoformat(),
                "requires_review": violation.severity == ViolationSeverity.CRITICAL
            }
            
            await mcp.call_tool("redis", {
                "command": "xadd",
                "stream": "admin:security_alerts",
                "fields": alert_data
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send admin alert: {e}")
            return False
    
    async def _get_account_status(self, user_id: str, escalation_level: int) -> str:
        """Determine current account status"""
        try:
            # Check for active restrictions
            restriction = await mcp.call_tool("redis", {
                "command": "hgetall",
                "key": f"user:restrictions:{user_id}"
            })
            
            if restriction and restriction.get("restricted"):
                return "restricted"
            
            # Check for suspension
            suspension = await mcp.call_tool("redis", {
                "command": "hgetall", 
                "key": f"user:suspension:{user_id}"
            })
            
            if suspension and suspension.get("suspended"):
                return "suspended"
            
            # Check for ban
            ban = await mcp.call_tool("redis", {
                "command": "hgetall",
                "key": f"user:ban:{user_id}"
            })
            
            if ban and ban.get("banned"):
                return "banned"
            
            return "active"
            
        except Exception as e:
            self.logger.error(f"Failed to get account status: {e}")
            return "unknown"
    
    def _update_action_metrics(self, action: EnforcementAction):
        """Update metrics based on action taken"""
        if action == EnforcementAction.WARNING:
            self.tracker_metrics["users_warned"] += 1
        elif action == EnforcementAction.MESSAGING_RESTRICTION:
            self.tracker_metrics["users_restricted"] += 1
        elif action == EnforcementAction.ACCOUNT_SUSPENSION:
            self.tracker_metrics["users_suspended"] += 1
        elif action == EnforcementAction.PERMANENT_BAN:
            self.tracker_metrics["users_banned"] += 1
    
    async def get_violation_statistics(self) -> Dict[str, Any]:
        """Get comprehensive violation statistics"""
        try:
            # Get recent violation trends
            recent_violations = await mcp.call_tool("supabase", {
                "action": "execute_sql",
                "query": """
                    SELECT 
                        violation_type,
                        severity,
                        COUNT(*) as count,
                        DATE(timestamp) as violation_date
                    FROM security_violations 
                    WHERE timestamp > NOW() - INTERVAL '30 days'
                    GROUP BY violation_type, severity, DATE(timestamp)
                    ORDER BY violation_date DESC
                """
            })
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "tracker_metrics": self.tracker_metrics,
                "recent_trends": recent_violations or [],
                "escalation_rules": {
                    level: {
                        "action": rule["action"].value,
                        "duration_hours": rule["duration_hours"],
                        "description": rule["description"]
                    }
                    for level, rule in self.escalation_rules.items()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get violation statistics: {e}")
            return {"error": str(e)}

# Global violation tracker instance
violation_tracker = ViolationTracker()