import re
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from models import Alert, AlertSeverity, ActionType, DatabaseManager
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityAgent:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.threat_patterns = {
            'malware_indicators': [
                r'\.exe.*\.tmp',
                r'powershell.*hidden',
                r'cmd.*\/c.*echo',
                r'reg.*add.*HKEY',
                r'net.*user.*add'
            ],
            'suspicious_commands': [
                r'rm\s+-rf',
                r'del\s+\/f\s+\/s',
                r'format\s+[a-z]:',
                r'shutdown\s+\/s',
                r'taskkill\s+\/f',
                r'net\s+user',
                r'reg\s+add'
            ],
            'network_anomalies': [
                r'netstat.*established',
                r'netsh.*firewall',
                r'ipconfig.*release'
            ]
        }

        self.severity_mapping = {
            'malware_indicators': AlertSeverity.CRITICAL,
            'suspicious_commands': AlertSeverity.HIGH,
            'network_anomalies': AlertSeverity.MEDIUM
        }

    def analyze_threat_level(self, task_command: str, system_metrics: Optional[Dict] = None) -> Tuple[float, str]:
        """
        Analyze threat level of a task
        Returns: (threat_score, threat_type)
        """
        threat_score = 0.0
        threat_type = "Unknown"

        # Check against threat patterns
        for pattern_type, patterns in self.threat_patterns.items():
            for pattern in patterns:
                if re.search(pattern, task_command, re.IGNORECASE):
                    threat_score += 0.3
                    threat_type = pattern_type
                    break

        # Check for system resource abuse
        if system_metrics:
            if system_metrics.get('cpu_usage', 0) > 90:
                threat_score += 0.2
            if system_metrics.get('memory_usage', 0) > 90:
                threat_score += 0.2

        # Check for privilege escalation attempts
        privilege_patterns = ['sudo', 'runas', 'su ', 'admin', 'root']
        for pattern in privilege_patterns:
            if pattern in task_command.lower():
                threat_score += 0.4
                threat_type = "privilege_escalation"

        # Check for data exfiltration patterns
        exfil_patterns = ['copy', 'move', 'xcopy', 'robocopy', 'scp', 'ftp']
        for pattern in exfil_patterns:
            if pattern in task_command.lower():
                threat_score += 0.2
                if threat_type == "Unknown":
                    threat_type = "data_exfiltration"

        return min(threat_score, 1.0), threat_type

    def make_security_decision(self, alert: Alert, context: Optional[Dict] = None) -> Dict:
        """
        Make security decision based on alert and context
        Returns decision with action and reasoning
        """
        decision = {
            'alert_id': alert.id,
            'action': ActionType.ALLOW,
            'reasoning': '',
            'confidence': 0.0,
            'timestamp': datetime.utcnow()
        }

        # Get the actual value of the enum for comparison
        severity_value = alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity)
        
        # Analyze alert severity and type
        if severity_value == AlertSeverity.CRITICAL.value:
            decision['action'] = ActionType.BLOCK
            decision['reasoning'] = f"Critical alert detected: {alert.message}. Immediate blocking required."
            decision['confidence'] = 0.95
        elif severity_value == AlertSeverity.HIGH.value:
            if alert.alert_type in ['High CPU Usage', 'High Memory Usage']:
                decision['action'] = ActionType.WARN
                decision['reasoning'] = f"High resource usage detected. Monitoring and warning issued."
                decision['confidence'] = 0.85
            else:
                decision['action'] = ActionType.BLOCK
                decision['reasoning'] = f"High severity alert: {alert.message}. Blocking for safety."
                decision['confidence'] = 0.90
        elif severity_value == AlertSeverity.MEDIUM.value:
            decision['action'] = ActionType.WARN
            decision['reasoning'] = f"Medium severity alert: {alert.message}. Warning issued, monitoring continued."
            decision['confidence'] = 0.75
        else:  # LOW severity
            decision['action'] = ActionType.ALLOW
            decision['reasoning'] = f"Low severity alert: {alert.message}. Allowing with monitoring."
            decision['confidence'] = 0.60

        # Apply context-based adjustments
        if context:
            if context.get('repeated_alerts', 0) > 3:
                decision['action'] = ActionType.ESCALATE
                decision['reasoning'] += " Multiple repeated alerts detected. Escalating to human review."
                decision['confidence'] = min(decision['confidence'] + 0.1, 1.0)

            if context.get('system_stress', False) and decision['action'] == ActionType.ALLOW:
                decision['action'] = ActionType.WARN
                decision['reasoning'] += " System under stress. Converting allow to warning."

        return decision

    def execute_security_action(self, decision: Dict) -> bool:
        """Execute the security decision with proper error handling"""
        session = None
        try:
            session = self.db_manager.get_session()

            # Update alert with action taken (simplified since we removed action_taken and status columns)
            alert = session.query(Alert).filter(Alert.id == decision['alert_id']).first()
            if alert:
                session.commit()
                logger.info(f"Alert {decision['alert_id']} processed with action {decision['action']}")

            # Log the action
            self._log_security_action(decision)

            # Execute specific actions
            action_value = decision['action'].value if hasattr(decision['action'], 'value') else str(decision['action'])
            if action_value == ActionType.BLOCK.value:
                self._execute_block_action(alert)
            elif action_value == ActionType.WARN.value:
                self._execute_warn_action(alert)
            elif action_value == ActionType.ESCALATE.value:
                self._execute_escalate_action(alert)

            return True

        except Exception as e:
            logger.error(f"Error executing security action: {e}")
            return False
        finally:
            if session:
                self.db_manager.close_session(session)

    def _execute_block_action(self, alert: Alert):
        """Execute blocking action"""
        logger.info(f"BLOCKING: {alert.alert_type} - {alert.message}")
        # Here you would implement actual blocking logic
        # For example, killing processes, blocking network connections, etc.

    def _execute_warn_action(self, alert: Alert):
        """Execute warning action"""
        logger.info(f"WARNING: {alert.alert_type} - {alert.message}")
        # Here you would implement warning logic
        # For example, sending notifications, logging warnings, etc.

    def _execute_escalate_action(self, alert: Alert):
        """Execute escalation action"""
        logger.info(f"ESCALATING: {alert.alert_type} - {alert.message}")
        # Here you would implement escalation logic
        # For example, sending to admin, creating high-priority tickets, etc.

    def _log_security_action(self, decision: Dict):
        """Log security action for audit trail"""
        try:
            log_entry = {
                'timestamp': decision['timestamp'].isoformat(),
                'alert_id': decision['alert_id'],
                'action': decision['action'].value if hasattr(decision['action'], 'value') else str(decision['action']),
                'reasoning': decision['reasoning'],
                'confidence': decision['confidence']
            }

            # Write to security log file
            with open('security_actions.log', 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            logger.info(f"Security action logged: {decision['action'].value if hasattr(decision['action'], 'value') else str(decision['action'])}")
        except Exception as e:
            logger.error(f"Error logging security action: {e}")

    def get_security_statistics(self) -> Dict:
        """Get security statistics with error handling"""
        session = self.db_manager.get_session()
        try:
            stats = {
                'total_alerts': session.query(Alert).count(),
                'recent_alerts': session.query(Alert).filter(Alert.created_at >= datetime.utcnow() - timedelta(hours=24)).count()
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting security statistics: {e}")
            return {}
        finally:
            self.db_manager.close_session(session)

    def analyze_alert_patterns(self, hours: int = 24) -> Dict:
        """Analyze alert patterns for threat intelligence with error handling"""
        session = self.db_manager.get_session()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            recent_alerts = session.query(Alert).filter(
                Alert.created_at >= cutoff_time
            ).all()

            patterns = {
                'alert_types': {},
                'severity_distribution': {},
                'time_patterns': {},
                'source_patterns': {}
            }

            for alert in recent_alerts:
                try:
                    # Count alert types
                    alert_type = alert.alert_type
                    patterns['alert_types'][alert_type] = patterns['alert_types'].get(alert_type, 0) + 1

                    # Count severity levels
                    severity_value = alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity)
                    patterns['severity_distribution'][severity_value] = patterns['severity_distribution'].get(severity_value, 0) + 1

                    # Count by hour
                    hour = alert.created_at.hour
                    patterns['time_patterns'][hour] = patterns['time_patterns'].get(hour, 0) + 1

                    # Count by source
                    source = alert.source
                    patterns['source_patterns'][source] = patterns['source_patterns'].get(source, 0) + 1
                except Exception as e:
                    logger.warning(f"Error processing alert {alert.id}: {e}")
                    continue

            return patterns
        except Exception as e:
            logger.error(f"Error analyzing alert patterns: {e}")
            return {}
        finally:
            self.db_manager.close_session(session)
