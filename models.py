from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, Enum, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import enum
import urllib.parse
import logging

from sqlalchemy import MetaData

from sqlalchemy import MetaData

# Create separate metadata for main tables and application history
main_metadata = MetaData()
history_metadata = MetaData()

Base = declarative_base(metadata=main_metadata)

# Create a separate Base for application history to isolate it in a different database
AppHistoryBase = declarative_base(metadata=history_metadata)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskCategory(enum.Enum):
    NON_HARMFUL = "Non-Harmful"
    LITTLE_HARMFUL = "Little Harmful"
    VERY_HARMFUL = "Very Harmful"

class AlertSeverity(enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

class ActionType(enum.Enum):
    ALLOW = "Allow"
    WARN = "Warn"
    BLOCK = "Block"
    ESCALATE = "Escalate"

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    task_name = Column(String(255), nullable=False)
    task_description = Column(Text)
    task_command = Column(Text)
    category = Column(Enum(TaskCategory), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=text("(CURRENT_TIMESTAMP)"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), nullable=False, default='pending', server_default=text("'pending'"))
    risk_score = Column(Float, nullable=False, default=0.0, server_default=text("0"))
    execution_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)

    def __repr__(self):
        return f"<Task(id={self.id}, name='{self.task_name}', category='{self.category.value}')>"

class Alert(Base):
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True)
    alert_type = Column(String(100), nullable=False)
    severity = Column(Enum(AlertSeverity), nullable=False)
    message = Column(Text, nullable=False)
    source = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, server_default=text("(CURRENT_TIMESTAMP)"))
    confidence_score = Column(Float, nullable=False, default=0.0, server_default=text("0"))

    def __repr__(self):
        return f"<Alert(id={self.id}, type='{self.alert_type}', severity='{self.severity.value}')>"

class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    severity = Column(Enum(AlertSeverity), nullable=False)
    category = Column(String(100), nullable=False, default='System')
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, server_default=text("(CURRENT_TIMESTAMP)"))
    is_read = Column(Integer, nullable=False, default=0, server_default=text("0"))  # 0 = unread, 1 = read
    
    def __repr__(self):
        return f"<Notification(id={self.id}, severity='{self.severity.value}', message='{self.message[:50]}...')>"

class SystemMetrics(Base):
    __tablename__ = 'system_metrics'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, server_default=text("(CURRENT_TIMESTAMP)"))
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_usage = Column(Float)
    network_io = Column(Float)
    active_processes = Column(Integer)

    def __repr__(self):
        return f"<SystemMetrics(id={self.id}, cpu={self.cpu_usage}%, memory={self.memory_usage}%)>"


class ApplicationHistory(AppHistoryBase):
    __tablename__ = 'application_history'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    path = Column(Text)
    pid = Column(Integer)
    start_time = Column(DateTime, default=datetime.utcnow, server_default=text("(CURRENT_TIMESTAMP)"))
    end_time = Column(DateTime)
    monitoring_session_id = Column(String(50))
    cpu_usage = Column(Float)
    memory_usage = Column(Float)

    def __repr__(self):
        return f"<ApplicationHistory(id={self.id}, name='{self.name}', pid={self.pid})>"


class DatabaseManager:
    def __init__(self, config, engine=None, db_url=None):
        self.config = config
        # Allow injection of a pre-built engine (helps with tests/mocks)
        if engine is not None:
            self.engine = engine
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            return

        # Use provided db_url or fallback to default logic
        if db_url:
            selected_url = db_url
        else:
            # Prefer explicit DB_URL if provided (allows forcing sqlite)
            explicit_url = getattr(config, 'DB_URL', None) or os.getenv('DB_URL')

            # Build default MySQL URL using the secure method
            mysql_url = config.get_db_url() if hasattr(config, 'get_db_url') else None

            # Fallback SQLite URL (local file)
            sqlite_url = os.getenv('SQLITE_URL', 'sqlite:///app.db')

            selected_url = explicit_url or mysql_url or sqlite_url
        
        self.engine = None

        # Try creating engine/connecting; on failure, fallback to SQLite
        try:
            # Add timeout configurations for better reliability
            connect_args = {}
            engine_kwargs = {
                'echo': False,
                'pool_pre_ping': True,
                'pool_size': 20,
                'max_overflow': 30,
                'pool_recycle': 3600,
                'pool_timeout': 30
            }
            if selected_url and 'mysql' in selected_url:
                connect_args = {
                    'connect_timeout': 30,
                    'read_timeout': 30,
                    'write_timeout': 30
                }
                engine_kwargs.update({
                    'connect_args': connect_args
                })

            self.engine = create_engine(selected_url, **engine_kwargs)

            # Validate connectivity if possible
            try:
                conn_ctx = getattr(self.engine, 'connect', None)
                if callable(conn_ctx):
                    with self.engine.connect() as _:
                        pass
            except Exception as e:
                raise e
        except Exception as e:
            # Log the error and fallback
            logger.warning(f"Database connection failed for '{selected_url}': {e}. Falling back to SQLite '{selected_url or 'sqlite:///app.db'}'.")
            fallback_url = db_url or 'sqlite:///app.db'
            self.engine = create_engine(fallback_url, echo=False, pool_pre_ping=True, pool_size=10, max_overflow=20, pool_recycle=3600)

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Create all database tables except application history"""
        # Create all tables using main metadata
        if self.engine is not None:
            main_metadata.create_all(bind=self.engine)

    def get_session(self):
        """Get database session with proper error handling"""
        try:
            return self.SessionLocal()
        except Exception as e:
            logger.error(f"Failed to create database session: {e}")
            raise

    def close_session(self, session):
        """Close database session with proper error handling"""
        try:
            if session:
                session.close()
        except Exception as e:
            logger.error(f"Failed to close database session: {e}")
            raise

    def execute_query(self, query, params=None):
        """Execute a query with parameters safely"""
        session = self.get_session()
        try:
            if params:
                result = session.execute(query, params)
            else:
                result = session.execute(query)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            logger.error(f"Database query execution failed: {e}")
            raise
        finally:
            self.close_session(session)

    def execute_query_with_result(self, query, params=None):
        """Execute a query and return results"""
        session = self.get_session()
        try:
            if params:
                result = session.execute(query, params)
            else:
                result = session.execute(query)
            return result.fetchall()
        except Exception as e:
            logger.error(f"Database query with result failed: {e}")
            raise
        finally:
            self.close_session(session)
