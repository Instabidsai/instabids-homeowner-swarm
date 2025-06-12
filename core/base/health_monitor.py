"""
Health Monitor - Agent Health Tracking and System Monitoring

This module provides comprehensive health monitoring for individual agents
and the overall system, enabling proactive issue detection, performance
optimization, and reliable system operation.

💚 CRITICAL: This ensures system reliability and early detection of issues
before they impact business operations.
"""

import asyncio
import logging
import json
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

# MCP Integration for health monitoring
class MCPHealthMonitor:
    """MCP-integrated health monitoring for Codex agent usage"""
    
    async def call_mcp_tool(self, tool_name: str, operation: str, params: dict) -> dict:
        """MCP tool interface for health monitoring operations"""
        # This will be replaced by actual MCP calling mechanism
        if tool_name == "redis":
            return await self._redis_operation(operation, params)
        elif tool_name == "supabase":
            return await self._supabase_operation(operation, params)
        else:
            raise ValueError(f"Unsupported MCP tool: {tool_name}")
    
    async def _redis_operation(self, operation: str, params: dict) -> dict:
        """Handle Redis MCP operations for health data"""
        if operation == "store_health_metric":
            return {"status": "success", "stored": True}
        elif operation == "get_health_history":
            return {"status": "success", "metrics": []}
        elif operation == "publish_health_alert":
            return {"status": "success", "alert_sent": True}
        return {"status": "success"}
    
    async def _supabase_operation(self, operation: str, params: dict) -> dict:
        """Handle Supabase MCP operations for health storage"""
        if operation == "store_health_report":
            return {"status": "success", "report_id": f"health_{uuid.uuid4().hex[:8]}"}
        elif operation == "query_health_trends":
            return {"status": "success", "trends": []}
        return {"status": "success"}


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class HealthMetric:
    """Individual health metric data"""
    name: str
    value: float
    unit: str
    timestamp: str
    status: HealthStatus
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    description: Optional[str] = None


@dataclass
class HealthReport:
    """Comprehensive health report for an agent or system"""
    agent_id: str
    agent_type: str
    timestamp: str
    overall_status: HealthStatus
    metrics: List[HealthMetric]
    alerts: List[Dict[str, Any]]
    uptime_seconds: float
    last_activity: str
    error_count: int
    performance_score: float


class HealthThresholds:
    """Default health thresholds for various metrics"""
    
    DEFAULT_THRESHOLDS = {
        # System metrics
        "cpu_usage": {"warning": 70.0, "critical": 90.0},
        "memory_usage": {"warning": 80.0, "critical": 95.0},
        "disk_usage": {"warning": 85.0, "critical": 95.0},
        
        # Agent metrics
        "event_processing_rate": {"warning": 10.0, "critical": 5.0},  # events per minute
        "error_rate": {"warning": 5.0, "critical": 10.0},  # percentage
        "response_time": {"warning": 5000.0, "critical": 10000.0},  # milliseconds
        
        # Business metrics
        "cost_per_hour": {"warning": 50.0, "critical": 100.0},  # dollars
        "contact_violations": {"warning": 1.0, "critical": 3.0},  # count per hour
        
        # Infrastructure metrics
        "redis_connection_count": {"warning": 80.0, "critical": 95.0},  # percentage of max
        "database_connection_count": {"warning": 80.0, "critical": 95.0},
        "queue_depth": {"warning": 100.0, "critical": 500.0},  # number of pending items
    }
    
    @classmethod
    def get_threshold(cls, metric_name: str, threshold_type: str) -> Optional[float]:
        """Get threshold value for a metric"""
        return cls.DEFAULT_THRESHOLDS.get(metric_name, {}).get(threshold_type)


class HealthMonitor:
    """
    Comprehensive health monitoring system for agents and infrastructure
    
    Features:
    - Real-time health metrics collection
    - Configurable alerting thresholds
    - Historical trend analysis
    - Automated issue detection
    - Performance optimization insights
    - System reliability tracking
    """
    
    def __init__(self, agent_id: str, agent_type: str = "unknown"):
        self.agent_id = agent_id
        self.agent_type = agent_type
        
        # MCP integration
        self.mcp = MCPHealthMonitor()
        
        # Health tracking
        self.start_time = datetime.utcnow()
        self.last_health_check = None
        self.health_history: List[HealthReport] = []
        
        # Metrics tracking
        self.metrics: Dict[str, HealthMetric] = {}
        self.custom_collectors: List[Callable] = []
        
        # Alert tracking
        self.active_alerts: List[Dict[str, Any]] = []
        self.alert_callbacks: List[Callable] = []
        
        # Performance tracking
        self.operation_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        
        # Monitoring configuration
        self.monitoring_config = {
            "check_interval": 60,  # seconds
            "history_retention": 100,  # number of reports to keep
            "alert_cooldown": 300,  # seconds between repeat alerts
            "performance_window": 3600  # seconds for performance calculations
        }
        
        # Monitoring state
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # Logging
        self.logger = logging.getLogger(f"HealthMonitor_{agent_id}")
    
    async def start_monitoring(self) -> None:
        """Start continuous health monitoring"""
        if self.is_monitoring:
            self.logger.warning("Health monitoring already started")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info(f"Started health monitoring for {self.agent_id}")
    
    async def stop_monitoring(self) -> None:
        """Stop health monitoring gracefully"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped health monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main health monitoring loop"""
        while self.is_monitoring:
            try:
                # Perform health check
                health_report = await self.perform_health_check()
                
                # Store health report
                await self._store_health_report(health_report)
                
                # Check for alerts
                await self._check_alerts(health_report)
                
                # Update metrics
                await self._update_health_metrics(health_report)
                
                # Sleep until next check
                await asyncio.sleep(self.monitoring_config["check_interval"])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_config["check_interval"])
    
    async def perform_health_check(self) -> HealthReport:
        """Perform comprehensive health check"""
        timestamp = datetime.utcnow().isoformat()
        metrics = []
        alerts = []
        
        # Collect system metrics
        system_metrics = await self._collect_system_metrics()
        metrics.extend(system_metrics)
        
        # Collect agent-specific metrics
        agent_metrics = await self._collect_agent_metrics()
        metrics.extend(agent_metrics)
        
        # Collect custom metrics
        custom_metrics = await self._collect_custom_metrics()
        metrics.extend(custom_metrics)
        
        # Calculate overall status
        overall_status = self._calculate_overall_status(metrics)
        
        # Calculate performance score
        performance_score = await self._calculate_performance_score()
        
        # Calculate uptime
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        
        # Create health report
        health_report = HealthReport(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            timestamp=timestamp,
            overall_status=overall_status,
            metrics=metrics,
            alerts=alerts,
            uptime_seconds=uptime_seconds,
            last_activity=self.last_health_check or timestamp,
            error_count=self.error_count,
            performance_score=performance_score
        )
        
        # Update tracking
        self.last_health_check = timestamp
        self.health_history.append(health_report)
        
        # Trim history
        if len(self.health_history) > self.monitoring_config["history_retention"]:
            self.health_history = self.health_history[-self.monitoring_config["history_retention"]:]
        
        return health_report
    
    async def _collect_system_metrics(self) -> List[HealthMetric]:
        """Collect system-level health metrics"""
        metrics = []
        timestamp = datetime.utcnow().isoformat()
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(HealthMetric(
                name="cpu_usage",
                value=cpu_percent,
                unit="percent",
                timestamp=timestamp,
                status=self._get_metric_status("cpu_usage", cpu_percent),
                threshold_warning=HealthThresholds.get_threshold("cpu_usage", "warning"),
                threshold_critical=HealthThresholds.get_threshold("cpu_usage", "critical"),
                description="CPU utilization percentage"
            ))
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            metrics.append(HealthMetric(
                name="memory_usage",
                value=memory_percent,
                unit="percent",
                timestamp=timestamp,
                status=self._get_metric_status("memory_usage", memory_percent),
                threshold_warning=HealthThresholds.get_threshold("memory_usage", "warning"),
                threshold_critical=HealthThresholds.get_threshold("memory_usage", "critical"),
                description="Memory utilization percentage"
            ))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            metrics.append(HealthMetric(
                name="disk_usage",
                value=disk_percent,
                unit="percent",
                timestamp=timestamp,
                status=self._get_metric_status("disk_usage", disk_percent),
                threshold_warning=HealthThresholds.get_threshold("disk_usage", "warning"),
                threshold_critical=HealthThresholds.get_threshold("disk_usage", "critical"),
                description="Disk space utilization percentage"
            ))
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
        
        return metrics
    
    async def _collect_agent_metrics(self) -> List[HealthMetric]:
        """Collect agent-specific health metrics"""
        metrics = []
        timestamp = datetime.utcnow().isoformat()
        
        try:
            # Event processing rate
            processing_rate = await self._calculate_event_processing_rate()
            metrics.append(HealthMetric(
                name="event_processing_rate",
                value=processing_rate,
                unit="events_per_minute",
                timestamp=timestamp,
                status=self._get_metric_status("event_processing_rate", processing_rate, reverse=True),
                threshold_warning=HealthThresholds.get_threshold("event_processing_rate", "warning"),
                threshold_critical=HealthThresholds.get_threshold("event_processing_rate", "critical"),
                description="Rate of event processing"
            ))
            
            # Error rate
            error_rate = await self._calculate_error_rate()
            metrics.append(HealthMetric(
                name="error_rate",
                value=error_rate,
                unit="percent",
                timestamp=timestamp,
                status=self._get_metric_status("error_rate", error_rate),
                threshold_warning=HealthThresholds.get_threshold("error_rate", "warning"),
                threshold_critical=HealthThresholds.get_threshold("error_rate", "critical"),
                description="Percentage of operations that resulted in errors"
            ))
            
            # Average response time
            avg_response_time = await self._calculate_average_response_time()
            metrics.append(HealthMetric(
                name="response_time",
                value=avg_response_time,
                unit="milliseconds",
                timestamp=timestamp,
                status=self._get_metric_status("response_time", avg_response_time),
                threshold_warning=HealthThresholds.get_threshold("response_time", "warning"),
                threshold_critical=HealthThresholds.get_threshold("response_time", "critical"),
                description="Average response time for operations"
            ))
            
        except Exception as e:
            self.logger.error(f"Error collecting agent metrics: {e}")
        
        return metrics
    
    async def _collect_custom_metrics(self) -> List[HealthMetric]:
        """Collect custom metrics from registered collectors"""
        metrics = []
        
        for collector in self.custom_collectors:
            try:
                custom_metrics = await collector()
                if isinstance(custom_metrics, list):
                    metrics.extend(custom_metrics)
                elif isinstance(custom_metrics, HealthMetric):
                    metrics.append(custom_metrics)
            except Exception as e:
                self.logger.error(f"Error in custom metric collector: {e}")
        
        return metrics
    
    def _get_metric_status(
        self,
        metric_name: str,
        value: float,
        reverse: bool = False
    ) -> HealthStatus:
        """Determine health status for a metric value"""
        warning_threshold = HealthThresholds.get_threshold(metric_name, "warning")
        critical_threshold = HealthThresholds.get_threshold(metric_name, "critical")
        
        if warning_threshold is None or critical_threshold is None:
            return HealthStatus.UNKNOWN
        
        if reverse:
            # For metrics where lower values indicate problems
            if value <= critical_threshold:
                return HealthStatus.CRITICAL
            elif value <= warning_threshold:
                return HealthStatus.WARNING
            else:
                return HealthStatus.HEALTHY
        else:
            # For metrics where higher values indicate problems
            if value >= critical_threshold:
                return HealthStatus.CRITICAL
            elif value >= warning_threshold:
                return HealthStatus.WARNING
            else:
                return HealthStatus.HEALTHY
    
    def _calculate_overall_status(self, metrics: List[HealthMetric]) -> HealthStatus:
        """Calculate overall health status from individual metrics"""
        if not metrics:
            return HealthStatus.UNKNOWN
        
        # Check for any critical status
        if any(m.status == HealthStatus.CRITICAL for m in metrics):
            return HealthStatus.CRITICAL
        
        # Check for any warning status
        if any(m.status == HealthStatus.WARNING for m in metrics):
            return HealthStatus.WARNING
        
        # Check for unknown status
        if any(m.status == HealthStatus.UNKNOWN for m in metrics):
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    async def _calculate_event_processing_rate(self) -> float:
        """Calculate events processed per minute"""
        # This would integrate with the EventHandlerMixin
        # For now, return a placeholder
        return 45.0
    
    async def _calculate_error_rate(self) -> float:
        """Calculate error rate percentage"""
        if self.operation_count == 0:
            return 0.0
        return (self.error_count / self.operation_count) * 100
    
    async def _calculate_average_response_time(self) -> float:
        """Calculate average response time in milliseconds"""
        if self.operation_count == 0:
            return 0.0
        return self.total_response_time / self.operation_count
    
    async def _calculate_performance_score(self) -> float:
        """Calculate overall performance score (0-100)"""
        # Weighted scoring based on key metrics
        score = 100.0
        
        # Reduce score based on error rate
        error_rate = await self._calculate_error_rate()
        score -= min(error_rate * 2, 30)  # Max 30 point reduction
        
        # Reduce score based on response time
        avg_response_time = await self._calculate_average_response_time()
        if avg_response_time > 1000:  # More than 1 second
            score -= min((avg_response_time - 1000) / 100, 20)  # Max 20 point reduction
        
        # Reduce score based on system metrics
        try:
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            if cpu_percent > 70:
                score -= min((cpu_percent - 70) / 2, 15)  # Max 15 point reduction
            
            if memory_percent > 80:
                score -= min((memory_percent - 80) / 2, 15)  # Max 15 point reduction
        except:
            pass
        
        return max(0.0, score)
    
    async def _store_health_report(self, health_report: HealthReport) -> None:
        """Store health report for historical analysis"""
        try:
            # Store in Redis for real-time access
            await self.mcp.call_mcp_tool("redis", "store_health_metric", {
                "agent_id": self.agent_id,
                "report": asdict(health_report)
            })
            
            # Store in Supabase for long-term analysis
            await self.mcp.call_mcp_tool("supabase", "store_health_report", {
                "table": "health_reports",
                "data": asdict(health_report)
            })
            
        except Exception as e:
            self.logger.error(f"Error storing health report: {e}")
    
    async def _update_health_metrics(self, health_report: HealthReport) -> None:
        """Update internal health metrics tracking"""
        for metric in health_report.metrics:
            self.metrics[metric.name] = metric
    
    async def _check_alerts(self, health_report: HealthReport) -> None:
        """Check for alert conditions and send notifications"""
        for metric in health_report.metrics:
            if metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                await self._handle_alert(metric, health_report)
    
    async def _handle_alert(self, metric: HealthMetric, health_report: HealthReport) -> None:
        """Handle alert conditions"""
        alert_level = AlertLevel.CRITICAL if metric.status == HealthStatus.CRITICAL else AlertLevel.WARNING
        
        alert = {
            "alert_id": f"alert_{uuid.uuid4().hex[:8]}",
            "agent_id": self.agent_id,
            "metric_name": metric.name,
            "metric_value": metric.value,
            "alert_level": alert_level.value,
            "timestamp": metric.timestamp,
            "description": f"{metric.name} is {metric.status.value}: {metric.value} {metric.unit}"
        }
        
        # Add to active alerts
        self.active_alerts.append(alert)
        
        # Send alert notification
        await self._send_alert_notification(alert)
        
        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    async def _send_alert_notification(self, alert: Dict[str, Any]) -> None:
        """Send alert notification via Redis"""
        try:
            await self.mcp.call_mcp_tool("redis", "publish_health_alert", {
                "stream": "health:alerts",
                "alert": alert
            })
        except Exception as e:
            self.logger.error(f"Error sending alert notification: {e}")
    
    # Public API methods
    
    def record_operation(self, response_time_ms: float, success: bool = True) -> None:
        """Record an operation for performance tracking"""
        self.operation_count += 1
        self.total_response_time += response_time_ms
        
        if not success:
            self.error_count += 1
    
    def add_custom_metric_collector(self, collector: Callable) -> None:
        """Add a custom metric collector function"""
        self.custom_collectors.append(collector)
        self.logger.info("Added custom metric collector")
    
    def add_alert_callback(self, callback: Callable) -> None:
        """Add a callback function for alert notifications"""
        self.alert_callbacks.append(callback)
        self.logger.info("Added alert callback")
    
    def get_current_health(self) -> Dict[str, Any]:
        """Get current health status"""
        if not self.health_history:
            return {"status": "no_data", "message": "No health data available"}
        
        latest_report = self.health_history[-1]
        return {
            "overall_status": latest_report.overall_status.value,
            "performance_score": latest_report.performance_score,
            "uptime_seconds": latest_report.uptime_seconds,
            "error_count": latest_report.error_count,
            "active_alerts": len(self.active_alerts),
            "last_check": latest_report.timestamp
        }
    
    def get_health_trends(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get health trends for a specific metric"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        trends = []
        for report in self.health_history:
            report_time = datetime.fromisoformat(report.timestamp)
            if report_time >= cutoff_time:
                for metric in report.metrics:
                    if metric.name == metric_name:
                        trends.append({
                            "timestamp": metric.timestamp,
                            "value": metric.value,
                            "status": metric.status.value
                        })
        
        return trends


# Global health monitor for easy access
_health_monitors: Dict[str, HealthMonitor] = {}


def get_health_monitor(agent_id: str, agent_type: str = "unknown") -> HealthMonitor:
    """Get or create health monitor for an agent"""
    if agent_id not in _health_monitors:
        _health_monitors[agent_id] = HealthMonitor(agent_id, agent_type)
    return _health_monitors[agent_id]


def start_monitoring_all() -> None:
    """Start monitoring for all registered health monitors"""
    for monitor in _health_monitors.values():
        asyncio.create_task(monitor.start_monitoring())


def stop_monitoring_all() -> None:
    """Stop monitoring for all registered health monitors"""
    for monitor in _health_monitors.values():
        asyncio.create_task(monitor.stop_monitoring())
