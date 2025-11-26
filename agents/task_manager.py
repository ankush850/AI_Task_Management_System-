import logging
from datetime import datetime
from typing import Dict, List, Tuple
from models import Task, TaskCategory, DatabaseManager
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskManagerAgent:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.suspicious_patterns = Config.SUSPICIOUS_PATTERNS
        self.risk_keywords = {
            'delete': 0.8,
            'remove': 0.7,
            'kill': 0.9,
            'format': 0.95,
            'shutdown': 0.9,
            'reboot': 0.8,
            'rm': 0.85,
            'del': 0.8,
            'taskkill': 0.9,
            'killall': 0.9
        }

    def analyze_task_risk(self, task_command: str, task_description: str = "") -> Tuple[float, TaskCategory]:
        """
        Analyze task risk and categorize it
        Returns: (risk_score, category)
        """
        risk_score = 0.0
        text_to_analyze = f"{task_command} {task_description}".lower()

        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if pattern.lower() in text_to_analyze:
                risk_score += 0.4

        # Check for risk keywords
        for keyword, weight in self.risk_keywords.items():
            if keyword in text_to_analyze:
                risk_score += weight * 0.12

        # Check for system commands
        system_commands = ['sudo', 'admin', 'root', 'systemctl', 'service']
        for cmd in system_commands:
            if cmd in text_to_analyze:
                risk_score += 0.2

        # Check for file operations
        file_ops = ['rm', 'del', 'delete', 'remove', 'unlink']
        for op in file_ops:
            if op in text_to_analyze:
                risk_score += 0.35

        # Normalize risk score to 0-1 range
        risk_score = min(risk_score, 1.0)

        # Categorize based on risk score
        if risk_score >= 0.7:
            category = TaskCategory.VERY_HARMFUL
        elif risk_score >= 0.3:
            category = TaskCategory.LITTLE_HARMFUL
        else:
            category = TaskCategory.NON_HARMFUL

        return risk_score, category

    def create_task(self, task_name: str, task_description: str = "",
                   task_command: str = "") -> Task:
        """Create a new task with risk analysis"""
        risk_score, category = self.analyze_task_risk(task_command, task_description)

        session = self.db_manager.get_session()
        try:
            task = Task(
                task_name=task_name,
                task_description=task_description,
                task_command=task_command,
                category=category,
                risk_score=risk_score
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            logger.info(f"Task created: {task_name} with risk score {risk_score}")
            return task
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating task: {e}")
            raise
        finally:
            self.db_manager.close_session(session)

    def get_tasks_by_category(self, category: TaskCategory) -> List[Task]:
        """Get all tasks in a specific category with error handling"""
        session = self.db_manager.get_session()
        try:
            return session.query(Task).filter(Task.category == category).all()
        except Exception as e:
            logger.error(f"Error getting tasks by category: {e}")
            return []
        finally:
            self.db_manager.close_session(session)

    def update_task_status(self, task_id: int, status: str) -> bool:
        """Update task status with error handling"""
        session = self.db_manager.get_session()
        try:
            task = session.query(Task).filter(Task.id == task_id).first()
            if task:
                # Use setattr for SQLAlchemy models to ensure proper attribute setting
                setattr(task, 'status', status)
                setattr(task, 'updated_at', datetime.utcnow())
                session.commit()
                logger.info(f"Task {task_id} status updated to {status}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating task status: {e}")
            return False
        finally:
            self.db_manager.close_session(session)

    def get_task_statistics(self) -> Dict:
        """Get task statistics by category with error handling"""
        session = self.db_manager.get_session()
        try:
            stats = {}
            for category in TaskCategory:
                count = session.query(Task).filter(Task.category == category).count()
                stats[category.value] = count
            return stats
        except Exception as e:
            logger.error(f"Error getting task statistics: {e}")
            return {}
        finally:
            self.db_manager.close_session(session)

    def execute_task_decision(self, task: Task) -> Dict:
        """Execute decision based on task category"""
        decision = {
            'task_id': task.id,
            'category': task.category.value if hasattr(task.category, 'value') else str(task.category),
            'action': '',
            'message': '',
            'timestamp': datetime.utcnow()
        }

        # Get the actual value of the enum for comparison
        category_value = task.category.value if hasattr(task.category, 'value') else str(task.category)
        
        if category_value == TaskCategory.NON_HARMFUL.value:
            decision['action'] = 'ALLOW'
            decision['message'] = 'Task is safe to execute'

        elif category_value == TaskCategory.LITTLE_HARMFUL.value:
            decision['action'] = 'WARN'
            decision['message'] = f'Task has moderate risk (score: {task.risk_score:.2f}). Execute with caution.'

        elif category_value == TaskCategory.VERY_HARMFUL.value:
            decision['action'] = 'BLOCK'
            decision['message'] = f'Task is highly dangerous (score: {task.risk_score:.2f}). Blocked for system safety.'

        return decision
