import os
import threading
import logging
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from watchdog.observers import Observer
try:
    from watchdog.observers.polling import PollingObserver
except Exception:
    PollingObserver = None
from watchdog.events import FileSystemEventHandler
import eventlet
from sqlalchemy import text

# Set up logging`
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config import Config
from models import DatabaseManager, Task, SystemMetrics, ApplicationHistory, Alert, Notification
from agents.task_manager import TaskManagerAgent
from agents.system_monitor import SystemMonitorAgent
from agents.security_agent import SecurityAgent
from agents.learning_agent import QLearningAgent
from agents.database_agent import DatabaseAgent

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Initialize database and agents
db_manager = DatabaseManager(Config)
db_manager.create_tables()

# Initialize separate database manager for application history
app_history_db_manager = DatabaseManager(Config, db_url='sqlite:///app_history.db')
# Create tables for application history database
from models import ApplicationHistory
ApplicationHistory.metadata.create_all(bind=app_history_db_manager.engine)

# Initialize all agents
task_manager = TaskManagerAgent(db_manager)
system_monitor = SystemMonitorAgent(db_manager)
security_agent = SecurityAgent(db_manager)
learning_agent = QLearningAgent(db_manager)
database_agent = DatabaseAgent(db_manager)

# =============================================================================
# GLOBAL STATE
# =============================================================================
system_running = False
monitoring_thread = None
monitoring_session_id = None
app_start_time = datetime.now(timezone.utc)

# =============================================================================
# MAIN ROUTES
# =============================================================================

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')


# =============================================================================
# SYSTEM STATUS & CONTROL API ROUTES
# =============================================================================

@app.route('/api/status')
def get_status():
    """Get system status"""
    return jsonify({
        'system_running': system_running,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'agents': {
            'task_manager': 'active',
            'system_monitor': 'active' if system_running else 'inactive',
            'security_agent': 'active',
            'learning_agent': 'active',
            'database_agent': 'active'
        }
    })


# =============================================================================
# SYSTEM MONITORING API ROUTES
# =============================================================================

@app.route('/api/alerts')
def get_alerts():
    """Get system alerts"""
    try:
        alerts = system_monitor.get_active_alerts()
        return jsonify({
            'success': True,
            'alerts': [
                {
                    'id': alert.id,
                    'type': alert.alert_type,
                    'severity': alert.severity.value,
                    'message': alert.message,
                    'source': alert.source,
                    'created_at': alert.created_at.isoformat()
                }
                for alert in alerts
            ]
        })
    except Exception as e:
        logger.error(f"/api/alerts error: {e}")
        return jsonify({'success': True, 'alerts': [], 'message': 'No alerts available'}), 200


@app.route('/api/notifications')
def get_notifications():
    """Get system notifications"""
    try:
        session = db_manager.get_session()
        try:
            # Get all notifications ordered by timestamp (newest first)
            notifications = session.query(Notification).order_by(Notification.timestamp.desc()).all()
            return jsonify({
                'success': True,
                'notifications': [
                    {
                        'id': notification.id,
                        'severity': notification.severity.value,
                        'category': notification.category,
                        'message': notification.message,
                        'timestamp': notification.timestamp.isoformat(),
                        'isRead': bool(notification.is_read)
                    }
                    for notification in notifications
                ]
            })
        finally:
            db_manager.close_session(session)
    except Exception as e:
        logger.error(f"/api/notifications error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_as_read(notification_id):
    """Mark a notification as read"""
    try:
        session = db_manager.get_session()
        try:
            notification = session.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                return jsonify({'success': False, 'error': 'Notification not found'}), 404
            
            notification.is_read = 1
            session.commit()
            
            return jsonify({'success': True, 'message': 'Notification marked as read'})
        finally:
            db_manager.close_session(session)
    except Exception as e:
        logger.error(f"/api/notifications/{notification_id}/read error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/notifications/mark_all_read', methods=['POST'])
def mark_all_notifications_as_read():
    """Mark all notifications as read"""
    try:
        session = db_manager.get_session()
        try:
            # Update all unread notifications
            session.query(Notification).filter(Notification.is_read == 0).update({Notification.is_read: 1})
            session.commit()
            
            return jsonify({'success': True, 'message': 'All notifications marked as read'})
        finally:
            db_manager.close_session(session)
    except Exception as e:
        logger.error(f"/api/notifications/mark_all_read error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/metrics')
def get_metrics():
    """Get system metrics"""
    try:
        # If monitoring is off, return zeroed counters
        if not system_running:
            return jsonify({
                'success': True,
                'metrics': {
                    'cpu_stats': {'current': 0, 'average': 0, 'peak': 0},
                    'memory_stats': {'current': 0, 'average': 0, 'peak': 0},
                    'data_points': 0,
                    'last_timestamp': datetime.now(timezone.utc).isoformat(),
                    'active_processes': 0,
                    'historical': []
                }
            })

        # Get current real-time system metrics first
        current_metrics = system_monitor.get_system_metrics()
        
        if current_metrics:
            # Get historical metrics for additional context
            # Safely parse hours
            try:
                hours = int(request.args.get('hours', 24))
            except Exception:
                hours = 24
            hours = max(1, min(hours, 168))
            historical_metrics = []  # keep list form to match frontend expectations
            
            # Create properly formatted response for frontend
            metrics_response = {
                'success': True,
                'metrics': {
                    'cpu_stats': {
                        'current': current_metrics['cpu_usage'],
                        'average': current_metrics['cpu_usage'],  # Use current as average for now
                        'peak': current_metrics['cpu_usage']
                    },
                    'memory_stats': {
                        'current': current_metrics['memory_usage'],
                        'average': current_metrics['memory_usage'],  # Use current as average for now
                        'peak': current_metrics['memory_usage']
                    },
                    'data_points': 1,  # Current data point
                    'last_timestamp': current_metrics['timestamp'].isoformat(),
                    'active_processes': current_metrics['active_processes'],
                    'historical': historical_metrics
                }
            }
            
            return jsonify(metrics_response)
        else:
            # Fallback if no current metrics available
            return jsonify({
                'success': True,
                'metrics': {
                    'cpu_stats': {'current': 0, 'average': 0, 'peak': 0},
                    'memory_stats': {'current': 0, 'average': 0, 'peak': 0},
                    'data_points': 0,
                    'last_timestamp': datetime.now(timezone.utc).isoformat(),
                    'active_processes': 0,
                    'historical': []
                }
            })
    except Exception as e:
        logger.error(f"Metrics API error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 200


@app.route('/api/analytics')
def get_analytics():
    """Get system analytics"""
    try:
        days = int(request.args.get('days', 30))
        task_analytics = database_agent.get_task_analytics(days)
        alert_analytics = database_agent.get_alert_analytics(days)
        learning_stats = database_agent.get_learning_progress()

        return jsonify({
            'success': True,
            'analytics': {
                'tasks': task_analytics,
                'alerts': alert_analytics,
                'learning': learning_stats
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/learning/stats')
def get_learning_stats():
    """Learning stats endpoint"""
    try:
        stats = database_agent.get_learning_progress()
        return jsonify({'success': True, 'learning': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/security/stats')
def get_security_stats():
    """Security stats endpoint"""
    try:
        stats = security_agent.get_security_statistics()
        return jsonify({'success': True, 'security': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/task/stats')
def get_task_stats():
    """Task stats endpoint"""
    try:
        stats = task_manager.get_task_statistics()
        return jsonify({'success': True, 'tasks': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    """List recent tasks"""
    try:
        try:
            limit = int(request.args.get('limit', 50))
        except Exception:
            limit = 50
        limit = max(1, min(limit, 1000))
        session = db_manager.get_session()
        try:
            tasks = session.query(Task).order_by(Task.created_at.desc()).limit(limit).all()
            return jsonify({
                'success': True,
                'tasks': [
                    {
                        'id': t.id,
                        'name': t.task_name,
                        'description': t.task_description,
                        'command': t.task_command,
                        'category': (t.category.value if hasattr(t.category, 'value') else str(t.category)),
                        'risk_score': t.risk_score,
                        'status': getattr(t, 'status', 'pending'),
                        'created_at': (t.created_at.isoformat() if getattr(t, 'created_at', None) else None)
                    } for t in tasks
                ]
            })
        finally:
            db_manager.close_session(session)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/tasks', methods=['POST'])
def create_task_api():
    """Create a new task"""
    try:
        payload = request.get_json(force=True) or {}
        name = (payload.get('name') or '').strip()
        description = payload.get('description') or ''
        command = payload.get('command') or ''
        if not name:
            return jsonify({'success': False, 'error': 'Task name is required'}), 400
        task = task_manager.create_task(task_name=name, task_description=description, task_command=command)
        return jsonify({
            'success': True,
            'task': {
                'id': task.id,
                'name': task.task_name,
                'description': task.task_description,
                'command': task.task_command,
                'category': (task.category.value if hasattr(task.category, 'value') else str(task.category)),
                'risk_score': task.risk_score,
                'status': getattr(task, 'status', 'pending'),
                'created_at': (task.created_at.isoformat() if getattr(task, 'created_at', None) else None)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/processes')
def get_processes():
    """Get snapshot of per-process resource usage (top by memory)."""
    try:
        limit = int(request.args.get('limit', 10))
        processes = system_monitor.get_process_usage(limit=limit)
        return jsonify({'success': True, 'processes': processes, 'limit': limit})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/processes/<int:pid>/files')
def get_process_files(pid: int):
    """Get list of file paths currently opened by a process."""
    try:
        limit = request.args.get('limit')
        limit_val = int(limit) if limit is not None else None
        files = system_monitor.get_process_open_files(pid, limit=limit_val)
        return jsonify({'success': True, 'pid': pid, 'files': files, 'count': len(files)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/application_history')
def get_application_history():
    """Get application history for all monitoring sessions from separate database"""
    try:
        session = app_history_db_manager.get_session()
        try:
            # Get all application history records
            history = session.query(ApplicationHistory).order_by(ApplicationHistory.start_time.desc()).all()
            
            # Group by session
            sessions = {}
            for record in history:
                session_id = record.monitoring_session_id
                if session_id not in sessions:
                    sessions[session_id] = {
                        'session_id': session_id,
                        'start_time': record.start_time.isoformat() if record.start_time is not None else None,
                        'applications': []
                    }
                sessions[session_id]['applications'].append({
                    'id': record.id,
                    'name': record.name,
                    'pid': record.pid,
                    'cpu_usage': record.cpu_usage,
                    'memory_usage': record.memory_usage,
                    'start_time': record.start_time.isoformat() if record.start_time is not None else None
                })
            
            # Convert to list and sort by start time
            result = list(sessions.values())
            result.sort(key=lambda x: x['start_time'] or '', reverse=True)
            
            return jsonify({'success': True, 'sessions': result})
        finally:
            app_history_db_manager.close_session(session)
    except Exception as e:
        logger.error(f"Error getting application history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def track_running_applications(session_id):
    """Track currently running applications and save to separate database"""
    try:
        session = app_history_db_manager.get_session()
        try:
            # Get current running processes
            processes = system_monitor.get_process_usage(limit=100)
            for proc in processes:
                app_history = ApplicationHistory(
                    name=proc.get('name', 'Unknown'),
                    path='',  # Path information might not be available
                    pid=proc.get('pid'),
                    monitoring_session_id=session_id,
                    cpu_usage=proc.get('cpu_percent', 0.0),
                    memory_usage=proc.get('memory_percent', 0.0)
                )
                session.add(app_history)
            session.commit()
            logger.info(f"Tracked {len(processes)} applications for session {session_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error tracking applications: {e}")
        finally:
            app_history_db_manager.close_session(session)
    except Exception as e:
        logger.error(f"Error getting database session: {e}")


@app.route('/api/start_monitoring', methods=['POST'])
def start_monitoring():
    """Start system monitoring with real-----------------time WebSocket updates"""
    global system_running, monitoring_thread, monitoring_session_id

    if system_running:
        return jsonify({'success': False, 'message': 'Monitoring already running'})

    system_running = True
    # Generate a unique session ID for this monitoring session
    monitoring_session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Reset counters so new session starts from zero
    try:
        system_monitor.data_points_collected = 0
    except Exception:
        pass
    
    # Get monitoring interval from request
    try:
        payload = request.get_json(silent=True) or {}
        interval = payload.get('interval') or request.args.get('interval') or 5
        interval = max(1, min(int(float(interval)), 60))  # Clamp to 1-60 seconds
    except Exception:
        interval = 5
    
    # Track currently running applications
    track_running_applications(monitoring_session_id)

    # Start monitoring in background thread to avoid blocking
    def initialize_monitoring():
        try:
            # Initialize CPU measurement (first call returns 0.0)
            system_monitor.get_system_metrics()
            
            # Start monitoring thread
            system_monitor.start_monitoring(interval=interval)
            
            # Start file monitoring for real-time project updates
            start_file_monitoring()
            
            logger.info("System monitoring initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing monitoring: {e}")
    
    # Start initialization in background
    init_thread = threading.Thread(target=initialize_monitoring)
    init_thread.daemon = True
    init_thread.start()
    
    # Broadcast system status change immediately
    broadcast_system_status(True)
    logger.info("System monitoring started")

    # Start real-time monitoring loop with WebSocket broadcasting
    def enhanced_monitoring_loop():
        while system_running:
            try:
                # Get current metrics
                metrics = system_monitor.get_system_metrics()
                if metrics:
                    # Format metrics for real-time broadcast
                    metrics_data = {
                        'success': True,
                        'metrics': {
                            'cpu_stats': {
                                'current': metrics['cpu_usage']
                            },
                            'memory_stats': {
                                'current': metrics['memory_usage']
                            },
                            'active_processes': metrics['active_processes'],
                            'data_points': getattr(system_monitor, 'data_points_collected', 0),
                            'last_timestamp': metrics['timestamp'].isoformat()
                        },
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Broadcast to all connected clients
                    broadcast_system_metrics(metrics_data)
                    
                    # Check for alerts and broadcast them
                    if metrics['cpu_usage'] > 90:
                        broadcast_alert({
                            'type': 'critical',
                            'title': 'High CPU Usage',
                            'message': f'CPU usage is at {metrics["cpu_usage"]:.1f}%',
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                    elif metrics['memory_usage'] > 90:
                        broadcast_alert({
                            'type': 'critical',
                            'title': 'High Memory Usage',
                            'message': f'Memory usage is at {metrics["memory_usage"]:.1f}%',
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                
                # Sleep for a short interval (real-time updates)
                eventlet.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Error in enhanced monitoring loop: {e}")
                eventlet.sleep(5)

    # Start background learning process
    def learning_loop():
        while system_running:
            try:
                alerts = system_monitor.get_active_alerts()
                for alert in alerts:
                    context = {
                        'alert_severity': alert.severity.value,
                        'system_stress': False,
                        'repeated_alerts': 1,
                        'confidence_score': alert.confidence_score or 0.0
                    }

                    state = learning_agent.get_state_representation(context)
                    action, confidence = learning_agent.choose_action(state, context)
                    decision = security_agent.make_security_decision(alert, context)
                    
                    # Calculate reward (simplified)
                    reward = 0.5 if decision['action'].value == 'WARN' else 0.0
                    learning_agent.learn_from_experience(state, action, reward, state)

                eventlet.sleep(60)  # Learn every minute
            except Exception as e:
                logger.error(f"Error in learning loop: {e}")
                eventlet.sleep(60)

    # Start both monitoring threads
    monitoring_thread = threading.Thread(target=enhanced_monitoring_loop)
    monitoring_thread.daemon = True
    monitoring_thread.start()
    
    learning_thread = threading.Thread(target=learning_loop)
    learning_thread.daemon = True
    learning_thread.start()

    return jsonify({'success': True, 'message': 'Real-time monitoring started'})

@app.route('/api/stop_monitoring', methods=['POST'])
def stop_monitoring():
    """Stop system monitoring and broadcast status change"""
    global system_running

    if not system_running:
        return jsonify({'success': False, 'message': 'Monitoring not running'})

    system_running = False
    system_monitor.stop_monitoring()
    learning_agent.save_q_table()
    
    # Broadcast system status change
    broadcast_system_status(False)
    logger.info("System monitoring stopped")
    
    # Stop file monitoring
    stop_file_monitoring()
    
    return jsonify({'success': True, 'message': 'Real-time monitoring stopped'})

@app.route('/api/decisions/<int:task_id>')
def get_task_decision(task_id):
    """Get decision for a specific task"""
    try:
        session = db_manager.get_session()
        task = session.query(Task).filter(Task.id == task_id).first()
        db_manager.close_session(session)

        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404

        decision = task_manager.execute_task_decision(task)
        return jsonify({
            'success': True,
            'decision': decision
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/learning/explain/<int:task_id>')
def explain_decision(task_id):
    """Get explanation for a task decision"""
    try:
        session = db_manager.get_session()
        task = session.query(Task).filter(Task.id == task_id).first()
        db_manager.close_session(session)

        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404

        # Create context for learning agent
        context = {
            'task_risk': task.risk_score,
            'alert_severity': 'LOW',  # Default
            'system_stress': False,
            'repeated_alerts': 0,
            'confidence_score': 0.5
        }

        state = learning_agent.get_state_representation(context)
        action, confidence = learning_agent.choose_action(state, context)

        explanation = learning_agent.get_action_explanation(state, action)

        return jsonify({
            'success': True,
            'explanation': explanation,
            'confidence': confidence,
            'action': ['ALLOW', 'WARN', 'BLOCK', 'ESCALATE'][action]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/processes/chart-data')
def get_process_chart_data():
    """Get process data formatted for charts"""
    try:
        limit = int(request.args.get('limit', 15))
        processes = system_monitor.get_process_usage(limit=limit)
        
        # Format for charts
        chart_data = {
            'success': True,
            'processes': processes,
            'bar_chart': {
                'labels': [proc['name'][:15] + '...' if len(proc['name']) > 15 else proc['name'] for proc in processes[:10]],
                'memory_data': [proc['memory_percent'] for proc in processes[:10]],
                'cpu_data': [proc['cpu_percent'] for proc in processes[:10]]
            },
            'pie_chart': {
                'memory_distribution': system_monitor.categorize_processes_by_memory(processes),
                'cpu_distribution': system_monitor.categorize_processes_by_cpu(processes)
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# PROCESS MONITORING API ROUTES
# =============================================================================

@app.route('/api/system/gauge-data')
def get_system_gauge_data():
    """Get system metrics formatted for gauge charts"""
    try:
        if not system_running:
            return jsonify({
                'success': True,
                'cpu': {'value': 0, 'max': 100, 'color': system_monitor.get_gauge_color(0, 'cpu')},
                'memory': {'value': 0, 'max': 100, 'color': system_monitor.get_gauge_color(0, 'memory')},
                'processes': {'value': 0, 'max': 500, 'color': system_monitor.get_gauge_color(0, 'processes')},
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

        metrics = system_monitor.get_system_metrics()
        if not metrics:
            return jsonify({
                'success': False,
                'error': 'Could not retrieve system metrics'
            }), 500
            
        gauge_data = {
            'success': True,
            'cpu': {
                'value': metrics['cpu_usage'],
                'max': 100,
                'color': system_monitor.get_gauge_color(metrics['cpu_usage'], 'cpu')
            },
            'memory': {
                'value': metrics['memory_usage'],
                'max': 100,
                'color': system_monitor.get_gauge_color(metrics['memory_usage'], 'memory')
            },
            'processes': {
                'value': metrics['active_processes'],
                'max': max(500, metrics['active_processes'] * 1.2),  # Dynamic max
                'color': system_monitor.get_gauge_color(metrics['active_processes'], 'processes')
            },
            'timestamp': metrics['timestamp'].isoformat()
        }
        
        return jsonify(gauge_data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# EXPORT & DATABASE ROUTES
# =============================================================================

@app.route('/api/metrics/historical')
def get_historical_metrics():
    """Get historical system metrics for line charts"""
    try:
        try:
            hours = int(request.args.get('hours', 24))
        except Exception:
            hours = 24
        hours = max(1, min(hours, 168))
        
        # Get historical data from database
        session = db_manager.get_session()
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            metrics = session.query(SystemMetrics).filter(
                SystemMetrics.timestamp >= cutoff_time
            ).order_by(SystemMetrics.timestamp.asc()).all()
            
            # Return list of datapoints rather than nested dict for easier consumption
            data_points = [
                {
                    'timestamp': m.timestamp.isoformat(),
                    'cpu': m.cpu_usage,
                    'memory': m.memory_usage,
                    'processes': m.active_processes
                } for m in metrics
            ]

            chart_data = {
                'success': True,
                'data': data_points,
                'count': len(metrics),
                'time_range_hours': hours
            }
            
            return jsonify(chart_data)
        finally:
            db_manager.close_session(session)
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/export_metrics_mysql')
def export_metrics_mysql():
    """Export recent system metrics into a MySQL-compatible .sql dump text."""
    try:
        # Parse and clamp hours
        hours_str = request.args.get('hours', '24')
        try:
            hours = int(hours_str)
        except Exception:
            hours = 24
        hours = max(1, min(hours, 168))

        since_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        session = db_manager.get_session()
        query = (
            session.query(SystemMetrics)
            .filter(SystemMetrics.timestamp >= since_dt)
            .order_by(SystemMetrics.timestamp.asc())
        )

        def generate():
            try:
                yield "-- JARM Metrics MySQL export\n"
                yield "SET NAMES utf8mb4;\n"
                yield "SET time_zone = '+00:00';\n\n"
                yield (
                    "CREATE TABLE IF NOT EXISTS `system_metrics` (\n"
                    "  `id` INT NOT NULL AUTO_INCREMENT,\n"
                    "  `timestamp` DATETIME NOT NULL,\n"
                    "  `cpu_usage` DOUBLE NULL,\n"
                    "  `memory_usage` DOUBLE NULL,\n"
                    "  `active_processes` INT NULL,\n"
                    "  PRIMARY KEY (`id`),\n"
                    "  INDEX `idx_system_metrics_timestamp` (`timestamp`)\n"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n\n"
                )

                inserted = 0
                for metric in query.yield_per(1000):
                    try:
                        ts = getattr(metric, 'timestamp').strftime('%Y-%m-%d %H:%M:%S') if getattr(metric, 'timestamp') is not None else ''
                        cpu = float(getattr(metric, 'cpu_usage') if getattr(metric, 'cpu_usage') is not None else 0)
                        mem = float(getattr(metric, 'memory_usage') if getattr(metric, 'memory_usage') is not None else 0)
                        procs = int(getattr(metric, 'active_processes') if getattr(metric, 'active_processes') is not None else 0)
                        yield (
                            f"INSERT INTO `system_metrics` (`timestamp`, `cpu_usage`, `memory_usage`, "
                            f"`active_processes`) "
                            f"VALUES ('{ts}', {cpu}, {mem}, {procs});\n"
                        )
                        inserted += 1
                    except Exception:
                        # Skip malformed rows without failing the export
                        pass
                
                if inserted == 0:
                    yield "-- (no metrics available in the requested window)\n"
            finally:
                db_manager.close_session(session)

        return Response(
            stream_with_context(generate()),
            mimetype='text/sql',
            headers={'Content-Disposition': 'attachment; filename=jarm_metrics_mysql.sql'}
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/export_tasks_csv')
def export_tasks_csv():
    """Export tasks as CSV"""
    try:
        session = db_manager.get_session()
        try:
            tasks = session.query(Task).order_by(Task.created_at.asc()).all()
            def generate():
                yield 'id,name,description,command,category,risk_score,created_at\n'
                for t in tasks:
                    name = (t.task_name or '').replace('"', '""')
                    desc = (t.task_description or '').replace('"', '""')
                    cmd = (t.task_command or '').replace('"', '""')
                    cat = getattr(t, 'category').value if getattr(t, 'category') else ''
                    created = getattr(t, 'created_at').isoformat() if getattr(t, 'created_at') else ''
                    yield f'{t.id},"{name}","{desc}","{cmd}","{cat}",{t.risk_score},{created}\n'
            return Response(
                stream_with_context(generate()),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=tasks.csv'}
            )
        finally:
            db_manager.close_session(session)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/export_alerts_csv')
def export_alerts_csv():
    """Export alerts as CSV"""
    try:
        session = db_manager.get_session()
        try:
            from models import Alert
            alerts = session.query(Alert).order_by(Alert.created_at.asc()).all()
            def generate():
                yield 'id,type,severity,message,source,confidence_score,created_at\n'
                for a in alerts:
                    msg = (a.message or '').replace('"', '""')
                    src = (a.source or '').replace('"', '""')
                    sev = getattr(a, 'severity').value if getattr(a, 'severity') else ''
                    created = getattr(a, 'created_at').isoformat() if getattr(a, 'created_at') else ''
                    yield f'{a.id},"{a.alert_type}","{sev}","{msg}","{src}",{a.confidence_score},{created}\n'
            return Response(
                stream_with_context(generate()),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=alerts.csv'}
            )
        finally:
            db_manager.close_session(session)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# =============================================================================
# WEBSOCKET EVENT HANDLERS
# =============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    from flask import request as flask_request
    logger.info(f"Client connected")
    # Send initial system status to the connected client
    emit('system_status', {
        'system_running': system_running,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected")

@socketio.on('join_monitoring')
def handle_join_monitoring():
    """Join real-time monitoring room"""
    join_room('monitoring')
    logger.info(f"Client joined monitoring room")

@socketio.on('leave_monitoring')
def handle_leave_monitoring():
    """Leave real-time monitoring room"""
    leave_room('monitoring')
    logger.info(f"Client left monitoring room")

# =============================================================================
# REAL-TIME BROADCAST FUNCTIONS
# =============================================================================

def broadcast_system_metrics(metrics_data):
    """Broadcast system metrics to all connected clients"""
    socketio.emit('metrics_update', metrics_data, to='monitoring')

def broadcast_system_status(status):
    """Broadcast system status changes to all connected clients"""
    socketio.emit('system_status', {
        'system_running': status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

def broadcast_alert(alert_data):
    """Broadcast alerts to all connected clients"""
    socketio.emit('alert_notification', alert_data)

def broadcast_task_update(task_data):
    """Broadcast task updates to all connected clients"""
    socketio.emit('task_update', task_data)

def broadcast_file_change(file_data):
    """Broadcast file system changes to connected clients"""
    socketio.emit('file_change', file_data)

# =============================================================================
# FILE SYSTEM MONITORING
# =============================================================================

class ProjectFileHandler(FileSystemEventHandler):
    """Handles file system events for real-time project monitoring"""
    
    def __init__(self, project_root):
        super().__init__()
        self.project_root = project_root
        self.ignored_patterns = {
            '__pycache__', '.git', '.vscode', 'node_modules', 
            '.pytest_cache', '.mypy_cache', 'venv', 'env',
            '*.pyc', '*.pyo', '*.log', '.DS_Store', 'Thumbs.db'
        }
        
    def should_ignore(self, file_path):
        """Check if file should be ignored"""
        path_parts = file_path.replace('\\', '/').split('/')
        filename = os.path.basename(file_path)
        
        # Ignore hidden files and directories
        if any(part.startswith('.') for part in path_parts):
            return True
            
        # Ignore specific patterns
        for pattern in self.ignored_patterns:
            if pattern.startswith('*.'):
                if filename.endswith(pattern[1:]):
                    return True
            elif pattern in path_parts or pattern == filename:
                return True
                
        return False
    
    def on_modified(self, event):
        if event.is_directory or self.should_ignore(event.src_path):
            return
            
        rel_path = os.path.relpath(event.src_path, self.project_root)
        broadcast_file_change({
            'type': 'modified',
            'path': rel_path,
            'full_path': event.src_path,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    def on_created(self, event):
        if event.is_directory or self.should_ignore(event.src_path):
            return
            
        rel_path = os.path.relpath(event.src_path, self.project_root)
        broadcast_file_change({
            'type': 'created',
            'path': rel_path,
            'full_path': event.src_path,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    def on_deleted(self, event):
        if event.is_directory or self.should_ignore(event.src_path):
            return
            
        rel_path = os.path.relpath(event.src_path, self.project_root)
        broadcast_file_change({
            'type': 'deleted',
            'path': rel_path,
            'full_path': event.src_path,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

# Global file system observer
file_observer = None

def start_file_monitoring(project_root=None):
    """Start monitoring file system changes"""
    global file_observer
    
    if file_observer and file_observer.is_alive():
        return
        
    if not project_root:
        project_root = os.getcwd()
        
    try:
        # Prefer native observer; on Windows/eventlet conflicts, fall back to polling
        try:
            file_observer = Observer()
            event_handler = ProjectFileHandler(project_root)
            file_observer.schedule(event_handler, project_root, recursive=True)
            file_observer.start()
            logger.info(f"📁 File monitoring started for: {project_root}")
        except Exception as e1:
            if PollingObserver is None:
                raise e1
            # Fallback: polling-based observer is more compatible across environments
            file_observer = PollingObserver(timeout=1)
            event_handler = ProjectFileHandler(project_root)
            file_observer.schedule(event_handler, project_root, recursive=True)
            file_observer.start()
            logger.info(f"📁 File monitoring (polling) started for: {project_root}")
    except Exception as e:
        logger.error(f"❌ Failed to start file monitoring: {e}")

def stop_file_monitoring():
    """Stop monitoring file system changes"""
    global file_observer
    
    if file_observer and file_observer.is_alive():
        file_observer.stop()
        file_observer.join()
        file_observer = None
        logger.info("📁 File monitoring stopped")

# =============================================================================
# ENHANCED MONITORING FUNCTION
# =============================================================================

def real_time_monitoring_loop():
    """Enhanced monitoring loop that broadcasts real-time updates"""
    global system_running
    
    while system_running:
        try:
            # Get current metrics
            metrics = system_monitor.get_system_metrics()
            if metrics:
                # Format metrics for real-time broadcast
                metrics_data = {
                    'success': True,
                    'metrics': {
                        'cpu_stats': {
                            'current': metrics['cpu_usage']
                        },
                        'memory_stats': {
                            'current': metrics['memory_usage']
                        },
                        'active_processes': metrics['active_processes'],
                        'data_points': getattr(system_monitor, 'data_points_collected', 0),
                        'last_timestamp': metrics['timestamp'].isoformat()
                    },
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                # Broadcast to all connected clients
                broadcast_system_metrics(metrics_data)
                
                # Check for alerts and broadcast them
                if metrics['cpu_usage'] > 90:
                    broadcast_alert({
                        'type': 'critical',
                        'title': 'High CPU Usage',
                        'message': f'CPU usage is at {metrics["cpu_usage"]:.1f}%',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                elif metrics['memory_usage'] > 90:
                    broadcast_alert({
                        'type': 'critical',
                        'title': 'High Memory Usage',
                        'message': f'Memory usage is at {metrics["memory_usage"]:.1f}%',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
            
            # Sleep for a short interval (real-time updates)
            eventlet.sleep(1)  # Update every second
            
        except Exception as e:
            logger.error(f"Error in real-time monitoring loop: {e}")
            eventlet.sleep(5)  # Wait longer on error

# =============================================================================
# HEALTH & DIAGNOSTICS
# =============================================================================

@app.route('/healthz')
def healthz():
    """Basic liveness probe"""
    try:
        uptime = (datetime.now(timezone.utc) - app_start_time).total_seconds()
        return jsonify({
            'ok': True,
            'status': 'up',
            'system_running': system_running,
            'uptime_seconds': int(uptime),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
    except Exception as e:
        return jsonify({'ok': False, 'status': 'error', 'error': str(e)}), 500

@app.route('/readyz')
def readyz():
    """Readiness probe that ensures DB connectivity"""
    checks = {}
    overall_ok = True
    # Main DB
    try:
        s = db_manager.get_session()
        try:
            s.execute(text('SELECT 1'))
            checks['database'] = {'ok': True}
        finally:
            db_manager.close_session(s)
    except Exception as e:
        overall_ok = False
        checks['database'] = {'ok': False, 'error': str(e)}
    # App history DB
    try:
        s2 = app_history_db_manager.get_session()
        try:
            s2.execute(text('SELECT 1'))
            checks['app_history_db'] = {'ok': True}
        finally:
            app_history_db_manager.close_session(s2)
    except Exception as e:
        overall_ok = False
        checks['app_history_db'] = {'ok': False, 'error': str(e)}

    status_code = 200 if overall_ok else 503
    return jsonify({'ok': overall_ok, 'checks': checks, 'timestamp': datetime.now(timezone.utc).isoformat()}), status_code

@app.route('/api/diagnostics')
def diagnostics():
    """Lightweight diagnostics snapshot (no secrets)"""
    info = {
        'system': {
            'system_running': system_running,
            'data_points': getattr(system_monitor, 'data_points_collected', 0),
            'monitor_thread_alive': bool(getattr(system_monitor, 'monitor_thread', None) and system_monitor.monitor_thread.is_alive())
        },
        'config': {
            'debug': bool(getattr(Config, 'DEBUG', False)),
            'cpu_threshold': float(getattr(Config, 'CPU_THRESHOLD', 0)),
            'memory_threshold': float(getattr(Config, 'MEMORY_THRESHOLD', 0))
        },
        'time': {
            'now': datetime.now(timezone.utc).isoformat(),
            'uptime_seconds': int((datetime.now(timezone.utc) - app_start_time).total_seconds())
        }
    }
    # Database counters (best-effort)
    try:
        s = db_manager.get_session()
        try:
            tasks = s.query(Task).count()
            alerts = s.query(Alert).count()
            metrics = s.query(SystemMetrics).count()
            info['database'] = {'ok': True, 'counts': {'tasks': tasks, 'alerts': alerts, 'metrics': metrics}}
        finally:
            db_manager.close_session(s)
    except Exception as e:
        info['database'] = {'ok': False, 'error': str(e)}
    try:
        s2 = app_history_db_manager.get_session()
        try:
            apps = s2.query(ApplicationHistory).count()
            info['app_history_db'] = {'ok': True, 'counts': {'application_history': apps}}
        finally:
            app_history_db_manager.close_session(s2)
    except Exception as e:
        info['app_history_db'] = {'ok': False, 'error': str(e)}

    # Package versions (best-effort)
    try:
        import flask, flask_socketio, sqlalchemy, psutil as _psutil
        info['versions'] = {
            'flask': flask.__version__,
            'flask_socketio': getattr(flask_socketio, '__version__', 'unknown'),
            'sqlalchemy': sqlalchemy.__version__,
            'psutil': _psutil.__version__
        }
    except Exception:
        pass

    return jsonify({'success': True, 'diagnostics': info}), 200

# =============================================================================
# APPLICATION STARTUP
# =============================================================================

def is_port_in_use(port, host='127.0.0.1'):
    """Check if a port is already in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True

def find_available_port(start_port=5000, max_port=5010):
    """Find an available port starting from start_port"""
    for port in range(start_port, max_port):
        if not is_port_in_use(port):
            return port
    return None

if __name__ == '__main__':
    port = 5000  # Default port
    try:
        # Check if default port is available
        if is_port_in_use(port):
            logger.warning(f"⚠️  Port {port} is already in use, finding alternative...")
            alt_port = find_available_port(5000, 5010)
            if alt_port is None:
                logger.error("❌ No available ports found in range 5000-5010")
                logger.info("Please stop other instances or use a different port range.")
                exit(1)
            port = alt_port
            logger.info(f"✅ Using port {port} instead")
        
        logger.info(f"📊 Dashboard available at: http://localhost:{port}")
        
        # Use SocketIO's run method instead of Flask's for WebSocket support
        socketio.run(
            app,
            debug=False,  # Disable Flask debug to prevent port conflicts
            host='127.0.0.1',  # Bind to localhost for better Windows compatibility
            port=port,
            use_reloader=False,  # Disable auto-reloader to prevent port binding issues
            allow_unsafe_werkzeug=True  # For development
        )
    except KeyboardInterrupt:
        logger.info("\n⏹️  Shutting down...")
        if system_running:
            system_running = False
            system_monitor.stop_monitoring()
            broadcast_system_status(False)
        logger.info("✅ Server stopped")
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            logger.error(f"\n❌ Port {port} is still in use by another process.")
            logger.info("\nTo fix this, run one of these commands:")
            print(f"  Windows: netstat -ano | findstr :{port}")
            print(f"  Then: taskkill /F /PID <PID>")
        else:
            print(f"❌ Network Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
