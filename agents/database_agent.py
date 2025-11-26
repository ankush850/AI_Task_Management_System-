import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from models import DatabaseManager, Task, Alert, SystemMetrics, TaskCategory, AlertSeverity
from sqlalchemy import func, desc, and_

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseAgent:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def create_tables(self):
        """Create all database tables"""
        self.db_manager.create_tables()

    def get_task_analytics(self, days: int = 30) -> Dict:
        """Get comprehensive task analytics with error handling"""
        session = self.db_manager.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Task statistics by category
            category_stats = {}
            for category in TaskCategory:
                count = session.query(Task).filter(
                    and_(Task.category == category, Task.created_at >= cutoff_date)
                ).count()
                category_stats[category.value] = count

            # Risk score distribution
            risk_stats = session.query(
                func.avg(Task.risk_score).label('avg_risk'),
                func.min(Task.risk_score).label('min_risk'),
                func.max(Task.risk_score).label('max_risk')
            ).filter(Task.created_at >= cutoff_date).first()

            # Success rate by category
            success_rates = {}
            for category in TaskCategory:
                tasks = session.query(Task).filter(
                    and_(Task.category == category, Task.created_at >= cutoff_date)
                ).all()
                if tasks:
                    avg_success = sum(task.success_rate for task in tasks) / len(tasks)
                    success_rates[category.value] = avg_success
                else:
                    success_rates[category.value] = 0.0

            return {
                'category_distribution': category_stats,
                'risk_statistics': {
                    'average': float(getattr(risk_stats, 'avg_risk', 0) or 0),
                    'minimum': float(getattr(risk_stats, 'min_risk', 0) or 0),
                    'maximum': float(getattr(risk_stats, 'max_risk', 0) or 0)
                },
                'success_rates': success_rates,
                'total_tasks': sum(category_stats.values()),
                'period_days': days
            }
        except Exception as e:
            logger.error(f"Error getting task analytics: {e}")
            return {}
        finally:
            self.db_manager.close_session(session)

    def get_alert_analytics(self, days: int = 30) -> Dict:
        """Get comprehensive alert analytics with error handling"""
        session = self.db_manager.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Alert statistics by severity
            severity_stats = {}
            for severity in AlertSeverity:
                count = session.query(Alert).filter(
                    and_(Alert.severity == severity, Alert.created_at >= cutoff_date)
                ).count()
                severity_stats[severity.value] = count

            # Alert statistics by type
            alert_types = session.query(
                Alert.alert_type,
                func.count(Alert.id).label('count')
            ).filter(Alert.created_at >= cutoff_date).group_by(Alert.alert_type).all()

            type_stats = {}
            try:
                for alert_type, count in list(alert_types):
                    type_stats[alert_type] = count
            except Exception:
                # If mocked results are not directly iterable pairs
                for row in alert_types or []:
                    at = getattr(row, 'alert_type', None)
                    cnt = getattr(row, 'count', 0)
                    if at is not None:
                        type_stats[at] = cnt

            # Since we removed status and resolved_at columns, we'll provide simplified analytics
            return {
                'severity_distribution': severity_stats,
                'type_distribution': type_stats,
                'total_alerts': sum(severity_stats.values()),
                'period_days': days
            }
        except Exception as e:
            logger.error(f"Error getting alert analytics: {e}")
            return {}
        finally:
            self.db_manager.close_session(session)

    def get_system_performance_metrics(self, hours: int = 24) -> Dict:
        """Get system performance metrics with error handling"""
        session = self.db_manager.get_session()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            # Get recent metrics
            metrics = session.query(SystemMetrics).filter(
                SystemMetrics.timestamp >= cutoff_time
            ).order_by(SystemMetrics.timestamp.desc()).all()

            if not metrics:
                return {'error': 'No metrics available'}

            # Calculate statistics
            cpu_values = [getattr(m, 'cpu_usage') for m in metrics if getattr(m, 'cpu_usage') is not None]
            memory_values = [getattr(m, 'memory_usage') for m in metrics if getattr(m, 'memory_usage') is not None]
            disk_values = [getattr(m, 'disk_usage') for m in metrics if getattr(m, 'disk_usage') is not None]

            return {
                'cpu_stats': {
                    'current': cpu_values[0] if cpu_values else 0,
                    'average': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    'maximum': max(cpu_values) if cpu_values else 0,
                    'minimum': min(cpu_values) if cpu_values else 0
                },
                'memory_stats': {
                    'current': memory_values[0] if memory_values else 0,
                    'average': sum(memory_values) / len(memory_values) if memory_values else 0,
                    'maximum': max(memory_values) if memory_values else 0,
                    'minimum': min(memory_values) if memory_values else 0
                },
                'data_points': len(metrics),
                'time_range_hours': hours,
                'last_timestamp': getattr(metrics[0], 'timestamp').isoformat() if metrics else None
            }
        except Exception as e:
            logger.error(f"Error getting system performance metrics: {e}")
            return {'error': 'Failed to retrieve metrics'}
        finally:
            self.db_manager.close_session(session)

    def get_learning_progress(self) -> Dict:
        """Get learning agent progress statistics with error handling"""
        # Q-learning functionality has been removed
        return {
            'total_states': 0,
            'total_visits': 0,
            'recent_activity': 0,
            'top_states': []
        }

    def search_tasks(self, query: str, category: Optional[TaskCategory] = None,
                    limit: int = 50, offset: int = 0) -> List[Task]:
        """Search tasks by name, description, or command with error handling"""
        session = self.db_manager.get_session()
        try:
            search_filter = (
                Task.task_name.contains(query) |
                Task.task_description.contains(query) |
                Task.task_command.contains(query)
            )

            if category:
                search_filter = and_(search_filter, Task.category == category)

            return session.query(Task).filter(search_filter).limit(limit).offset(offset).all()
        except Exception as e:
            logger.error(f"Error searching tasks: {e}")
            return []
        finally:
            self.db_manager.close_session(session)

    def get_recent_activity(self, hours: int = 24, limit: int = 10) -> Dict:
        """Get recent system activity with error handling"""
        session = self.db_manager.get_session()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            # Recent tasks
            recent_tasks = session.query(Task).filter(
                Task.created_at >= cutoff_time
            ).order_by(desc(Task.created_at)).limit(limit).all()

            # Recent alerts
            recent_alerts = session.query(Alert).filter(
                Alert.created_at >= cutoff_time
            ).order_by(desc(Alert.created_at)).limit(limit).all()

            # Recent metrics
            recent_metrics = session.query(SystemMetrics).filter(
                SystemMetrics.timestamp >= cutoff_time
            ).order_by(desc(SystemMetrics.timestamp)).limit(5).all()

            return {
                'recent_tasks': [
                    {
                        'id': getattr(task, 'id'),
                        'name': getattr(task, 'task_name'),
                        'category': getattr(task, 'category').value,
                        'risk_score': getattr(task, 'risk_score'),
                        'created_at': getattr(task, 'created_at').isoformat()
                    }
                    for task in recent_tasks
                ],
                'recent_alerts': [
                    {
                        'id': getattr(alert, 'id'),
                        'type': getattr(alert, 'alert_type'),
                        'severity': getattr(alert, 'severity').value,
                        'message': getattr(alert, 'message'),
                        'created_at': getattr(alert, 'created_at').isoformat()
                    }
                    for alert in recent_alerts
                ],
                'recent_metrics': [
                    {
                        'cpu_usage': getattr(metric, 'cpu_usage'),
                        'memory_usage': getattr(metric, 'memory_usage'),
                        'timestamp': getattr(metric, 'timestamp').isoformat()
                    }
                    for metric in recent_metrics
                ]
            }
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            return {}
        finally:
            self.db_manager.close_session(session)

    def cleanup_old_data(self, days: int = 90):
        """Clean up old data to maintain database performance with error handling"""
        session = self.db_manager.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Clean old system metrics (keep only recent ones)
            old_metrics = session.query(SystemMetrics).filter(
                SystemMetrics.timestamp < cutoff_date
            ).delete()

            # Clean old alerts (simplified since we removed status column)
            old_alerts = session.query(Alert).filter(
                Alert.created_at < cutoff_date
            ).delete()

            session.commit()

            return {
                'deleted_metrics': old_metrics,
                'deleted_alerts': old_alerts,
                'cutoff_date': cutoff_date.isoformat()
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Error cleaning up old data: {e}")
            raise
        finally:
            self.db_manager.close_session(session)

    def export_data(self, table_name: str, format: str = 'json', limit: int = 1000) -> Any:
        """Export data from specific table with error handling"""
        session = self.db_manager.get_session()
        try:
            if table_name == 'tasks':
                data = session.query(Task).limit(limit).all()
                if format == 'json':
                    return [
                        {
                            'id': getattr(task, 'id'),
                            'task_name': getattr(task, 'task_name'),
                            'task_description': getattr(task, 'task_description'),
                            'task_command': getattr(task, 'task_command'),
                            'category': getattr(task, 'category').value,
                            'risk_score': getattr(task, 'risk_score'),
                            'status': getattr(task, 'status'),
                            'created_at': getattr(task, 'created_at').isoformat()
                        }
                        for task in data
                    ]
            elif table_name == 'alerts':
                data = session.query(Alert).limit(limit).all()
                if format == 'json':
                    return [
                        {
                            'id': getattr(alert, 'id'),
                            'alert_type': getattr(alert, 'alert_type'),
                            'severity': (getattr(alert, 'severity').value if getattr(alert, 'severity', None) is not None and hasattr(getattr(alert, 'severity'), 'value') else str(getattr(alert, 'severity', ''))),
                            'message': getattr(alert, 'message'),
                            'source': getattr(alert, 'source'),
                            'created_at': (getattr(alert, 'created_at').isoformat() if getattr(alert, 'created_at', None) else None)
                        }
                        for alert in data
                    ]
            else:
                raise ValueError(f"Unknown table: {table_name}")
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            raise
        finally:
            self.db_manager.close_session(session)
