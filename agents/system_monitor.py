import psutil
import time
import threading
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models import SystemMetrics, Alert, AlertSeverity, DatabaseManager, Notification
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemMonitorAgent:
    """Agent responsible for monitoring system resources and generating alerts.
    
    This agent monitors CPU usage, memory usage, and process count to detect
    anomalies and generate appropriate alerts. It also handles saving metrics
    to the database and managing the monitoring lifecycle.
    """
    def __init__(self, db_manager: DatabaseManager):
        """Initialize the SystemMonitorAgent.
        
        Args:
            db_manager: DatabaseManager instance for database operations
        """
        self.db_manager = db_manager
        self.monitoring = False
        self.monitor_thread = None
        self.cpu_threshold = Config.CPU_THRESHOLD
        self.memory_threshold = Config.MEMORY_THRESHOLD
        self.alert_cooldown = Config.ALERT_COOLDOWN
        self.last_alert_time = {}
        self.data_points_collected = 0

    # -------------------------------
    # Public helpers for testing
    # -------------------------------
    @staticmethod
    def categorize_processes_by_memory(processes: List[Dict]) -> Dict:
        """Categorize processes by memory usage for pie chart visualization."""
        high_mem = [p for p in processes if p.get('memory_percent', 0.0) > 5.0]
        medium_mem = [p for p in processes if 1.0 < p.get('memory_percent', 0.0) <= 5.0]
        low_mem = [p for p in processes if p.get('memory_percent', 0.0) <= 1.0]
        return {
            'labels': ['High Memory (>5%)', 'Medium Memory (1-5%)', 'Low Memory (<1%)'],
            'data': [len(high_mem), len(medium_mem), len(low_mem)],
            'colors': ['#ef4444', '#f59e0b', '#10b981']
        }

    @staticmethod
    def categorize_processes_by_cpu(processes: List[Dict]) -> Dict:
        """Categorize processes by CPU usage for pie chart visualization."""
        high_cpu = [p for p in processes if p.get('cpu_percent', 0.0) > 10.0]
        medium_cpu = [p for p in processes if 1.0 < p.get('cpu_percent', 0.0) <= 10.0]
        low_cpu = [p for p in processes if p.get('cpu_percent', 0.0) <= 1.0]
        return {
            'labels': ['High CPU (>10%)', 'Medium CPU (1-10%)', 'Low CPU (<1%)'],
            'data': [len(high_cpu), len(medium_cpu), len(low_cpu)],
            'colors': ['#dc2626', '#ea580c', '#059669']
        }

    @staticmethod
    def get_gauge_color(value: float, metric_type: str) -> str:
        """Get appropriate color based on metric value and type for gauge charts."""
        if metric_type in ['cpu', 'memory']:
            if value >= 90:
                return '#dc2626'
            elif value >= 70:
                return '#ea580c'
            elif value >= 50:
                return '#f59e0b'
            else:
                return '#10b981'
        else:  # processes
            if value >= 400:
                return '#dc2626'
            elif value >= 250:
                return '#ea580c'
            elif value >= 150:
                return '#f59e0b'
            else:
                return '#10b981'

    def get_system_metrics(self) -> Dict:
        """Get current system metrics"""
        try:
            # Use non-blocking CPU measurement (returns 0.0 on first call)
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            process_count = len(psutil.pids())

            return {
                'cpu_usage': cpu_percent,
                'memory_usage': memory.percent,
                'active_processes': process_count,
                'timestamp': datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}

    def _get_disk_usage(self):
        """Get disk usage with cross-platform fallback"""
        try:
            # Try a sensible default first
            return psutil.disk_usage('/')
        except Exception:
            # Fallback for Windows or unusual environments
            try:
                parts = psutil.disk_partitions(all=False)
                # Prefer a real writable filesystem (exclude cdrom/ramfs)
                for p in parts:
                    if 'cdrom' in p.opts.lower():
                        continue
                    if p.fstype and p.mountpoint:
                        return psutil.disk_usage(p.mountpoint)
                # Last resort: use current drive root
                import os
                mountpoint = os.path.abspath(os.sep)
                return psutil.disk_usage(mountpoint)
            except Exception:
                # If disk usage cannot be determined, synthesize a safe value
                class _Disk:
                    percent = 0.0
                return _Disk()

    def save_metrics(self, metrics: Dict):
        """Save system metrics to database with proper error handling"""
        if not metrics:
            return

        session = self.db_manager.get_session()
        try:
            system_metric = SystemMetrics(
                cpu_usage=metrics['cpu_usage'],
                memory_usage=metrics['memory_usage'],
                active_processes=metrics['active_processes']
            )
            session.add(system_metric)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving metrics: {e}")
        finally:
            self.db_manager.close_session(session)

    def check_anomalies(self, metrics: Dict) -> List[Dict]:
        """Check for system anomalies and generate alerts"""
        alerts = []
        current_time = datetime.utcnow()

        # Check CPU usage
        if metrics['cpu_usage'] > self.cpu_threshold:
            alert_key = f"cpu_high_{int(metrics['cpu_usage'])}"
            if self._should_alert(alert_key, current_time):
                alerts.append({
                    'type': 'High CPU Usage',
                    'severity': self._get_cpu_severity(metrics['cpu_usage']),
                    'message': f"CPU usage is {metrics['cpu_usage']:.1f}% (threshold: {self.cpu_threshold}%)",
                    'source': 'SystemMonitor',
                    'confidence': 0.95
                })

        # Check Memory usage
        if metrics['memory_usage'] > self.memory_threshold:
            alert_key = f"memory_high_{int(metrics['memory_usage'])}"
            if self._should_alert(alert_key, current_time):
                alerts.append({
                    'type': 'High Memory Usage',
                    'severity': self._get_memory_severity(metrics['memory_usage']),
                    'message': f"Memory usage is {metrics['memory_usage']:.1f}% (threshold: {self.memory_threshold}%)",
                    'source': 'SystemMonitor',
                    'confidence': 0.90
                })

        # Check for unusual process count
        if metrics['active_processes'] > 500:  # Threshold for process count
            alert_key = f"process_high_{metrics['active_processes']}"
            if self._should_alert(alert_key, current_time):
                alerts.append({
                    'type': 'High Process Count',
                    'severity': AlertSeverity.MEDIUM,
                    'message': f"Unusually high number of processes: {metrics['active_processes']}",
                    'source': 'SystemMonitor',
                    'confidence': 0.75
                })

        return alerts

    def _should_alert(self, alert_key: str, current_time: datetime) -> bool:
        """Check if enough time has passed since last alert of this type"""
        if alert_key not in self.last_alert_time:
            self.last_alert_time[alert_key] = current_time
            return True

        time_diff = (current_time - self.last_alert_time[alert_key]).total_seconds()
        if time_diff >= self.alert_cooldown:
            self.last_alert_time[alert_key] = current_time
            return True

        return False

    def _get_cpu_severity(self, cpu_usage: float) -> AlertSeverity:
        """Determine CPU alert severity"""
        if cpu_usage >= 95:
            return AlertSeverity.CRITICAL
        elif cpu_usage >= 90:
            return AlertSeverity.HIGH
        elif cpu_usage >= 80:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW

    def _get_memory_severity(self, memory_usage: float) -> AlertSeverity:
        """Determine memory alert severity"""
        if memory_usage >= 95:
            return AlertSeverity.CRITICAL
        elif memory_usage >= 90:
            return AlertSeverity.HIGH
        elif memory_usage >= 85:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW

    def create_alert(self, alert_data: Dict):
        """Create alert in database with proper error handling"""
        session = self.db_manager.get_session()
        try:
            alert = Alert(
                alert_type=alert_data['type'],
                severity=alert_data['severity'],
                message=alert_data['message'],
                source=alert_data['source'],
                confidence_score=alert_data.get('confidence', 0.0)
            )
            session.add(alert)
            session.commit()
            return alert
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating alert: {e}")
            return None
        finally:
            self.db_manager.close_session(session)

    def create_notification(self, alert_data: Dict):
        """Create notification in database with proper error handling"""
        session = self.db_manager.get_session()
        try:
            notification = Notification(
                severity=alert_data['severity'],
                category=alert_data.get('category', 'System'),
                message=alert_data['message']
            )
            session.add(notification)
            session.commit()
            return notification
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating notification: {e}")
            return None
        finally:
            self.db_manager.close_session(session)

    def start_monitoring(self, interval: int = 30):
        """Start continuous system monitoring"""
        if self.monitoring:
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("System monitoring started")

    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        # Reset counters when monitoring stops
        self.data_points_collected = 0
        logger.info("System monitoring stopped")

    def _monitor_loop(self, interval: int):
        """Main monitoring loop with improved error handling"""
        while self.monitoring:
            try:
                # Get current system metrics
                metrics = self.get_system_metrics()
                if metrics:
                    # Increment data points counter
                    self.data_points_collected += 1
                    # Save metrics to database
                    self.save_metrics(metrics)
                    # Check for anomalies based on collected metrics
                    alerts = self.check_anomalies(metrics)

                    # Create alerts and notifications for any detected anomalies
                    for alert_data in alerts:
                        alert = self.create_alert(alert_data)
                        if alert:
                            logger.info(f"Alert created: {alert_data['type']} - {alert_data['message']}")
                            # Also create a notification
                            self.create_notification(alert_data)

                # Wait for the specified interval before collecting metrics again
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(interval)

    def get_recent_metrics(self, hours: int = 24, limit: int = 100) -> List[SystemMetrics]:
        """Get recent system metrics with proper error handling"""
        session = self.db_manager.get_session()
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            return session.query(SystemMetrics).filter(
                SystemMetrics.timestamp >= cutoff_time
            ).order_by(SystemMetrics.timestamp.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting recent metrics: {e}")
            return []
        finally:
            self.db_manager.close_session(session)

    def get_active_alerts(self, limit: int = 50) -> List[Alert]:
        """Get recent alerts with proper error handling"""
        session = self.db_manager.get_session()
        try:
            # Since we removed the status column, we'll return recent alerts
            return session.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return []
        finally:
            self.db_manager.close_session(session)

    def get_process_usage(self, limit: int = 10) -> List[Dict]:
        """Return a snapshot of per-process resource usage (top by memory) with optimized sampling."""
        raw: List[Dict] = []
        # First pass: cheap attributes only for all processes
        for proc in psutil.process_iter(attrs=['pid', 'name', 'username']):
            try:
                try:
                    mem = proc.memory_percent() or 0.0
                except Exception:
                    mem = 0.0
                raw.append({
                    'proc': proc,
                    'pid': proc.info.get('pid'),
                    'name': proc.info.get('name') or 'unknown',
                    'user': proc.info.get('username') or 'unknown',
                    'memory_percent': float(mem)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort and slice top N by memory
        raw.sort(key=lambda p: p['memory_percent'], reverse=True)
        top = raw[:max(1, limit)]

        # Second pass: enrich only top N with cpu/io
        results: List[Dict] = []
        for entry in top:
            proc = entry['proc']
            cpu = 0.0
            read_bytes = 0
            write_bytes = 0
            try:
                cpu = proc.cpu_percent(interval=None) or 0.0
            except Exception:
                cpu = 0.0
            try:
                io = proc.io_counters()
                read_bytes = getattr(io, 'read_bytes', 0) or 0
                write_bytes = getattr(io, 'write_bytes', 0) or 0
            except Exception:
                pass
            results.append({
                'pid': entry['pid'],
                'name': entry['name'],
                'user': entry['user'],
                'cpu_percent': float(cpu),
                'memory_percent': float(entry['memory_percent']),
                'read_bytes': int(read_bytes),
                'write_bytes': int(write_bytes)
            })

        return results

    

    def get_process_open_files(self, pid: int, limit: Optional[int] = None) -> List[str]:
        """Return a list of file paths currently opened by the given process.
        Attempts to include memory-mapped files when available.
        """
        files: List[str] = []
        try:
            proc = psutil.Process(pid)
            # Regular open files
            try:
                for f in proc.open_files():
                    if f.path:
                        files.append(f.path)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
            # Memory-mapped files (best-effort)
            try:
                for m in proc.memory_maps():
                    if getattr(m, 'path', None) and m.path not in files:
                        files.append(m.path)
            except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                pass
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        if limit is not None:
            files = files[:max(0, limit)]
        return files

