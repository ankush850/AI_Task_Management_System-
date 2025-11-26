AI-Task Management System 

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Flask](https://img.shields.io/badge/flask-%23000.svg?style=flat&logo=flask&logoColor=white)]

JARM is an advanced AI-powered task management and system monitoring platform built with Flask. It features intelligent task scheduling, real-time system resource monitoring, security analysis, and an interactive dashboard with live updates.

## 🌟 Key Features

- **AI-Powered Task Management**: Intelligent task scheduling and execution using reinforcement learning algorithms
- **Real-time System Monitoring**: Continuous monitoring of CPU, memory, and process usage with live updates
- **Advanced Security Analysis**: Built-in security agent for threat detection, prevention, and response
- **Interactive Dashboard**: Modern web interface with real-time charts, metrics, and system status visualization
- **Multi-Agent Architecture**: Specialized agents for database operations, learning, security, and system monitoring
- **WebSocket Integration**: Real-time updates using Socket.IO for seamless user experience
- **Flexible Database Support**: Works with both MySQL and SQLite databases with automatic fallback
- **Comprehensive Alerting System**: Multi-level alert system with notifications and severity classification
- **Process Tracking**: Detailed monitoring of system processes with resource usage analysis
- **Historical Analytics**: In-depth analytics and reporting on system performance and task execution

## 🏗️ System Architecture

JARM employs a modular multi-agent architecture with five specialized agents:

### Task Manager Agent
Handles task creation, scheduling, execution, and risk analysis. Features:
- Risk assessment of tasks based on command analysis
- Task categorization (Non-Harmful, Little Harmful, Very Harmful)
- Task execution monitoring and statistics

### System Monitor Agent
Tracks system resources and generates alerts. Capabilities include:
- Real-time CPU and memory usage monitoring
- Process tracking and analysis
- Anomaly detection with configurable thresholds
- Alert generation and cooldown management

### Security Agent
Monitors for security threats and implements protective measures:
- Threat pattern recognition (malware indicators, suspicious commands)
- Privilege escalation detection
- Data exfiltration pattern identification
- Automated security response actions

### Learning Agent
Implements reinforcement learning for adaptive system behavior:
- Q-learning algorithm for decision making
- State representation based on system context
- Reward calculation for learning optimization
- Exploration vs exploitation strategies

### Database Agent
Manages data persistence, analytics, and reporting:
- Database abstraction layer with SQLAlchemy
- Analytics generation for tasks, alerts, and system metrics
- Data export capabilities
- Database maintenance and cleanup functions

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip package manager
- MySQL (optional, SQLite used as fallback)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd jarm
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env to set your database configuration and other settings
   ```

5. Run the application:
   ```bash
   python app.py
   ```

6. Access the dashboard at `http://localhost:5000`

### Configuration

The application can be configured through environment variables in the `.env` file:

- **Database Settings**: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- **Monitoring Thresholds**: `CPU_THRESHOLD`, `MEMORY_THRESHOLD`
- **Learning Parameters**: `Q_LEARNING_ALPHA`, `Q_LEARNING_GAMMA`, `Q_LEARNING_EPSILON`
- **Security Settings**: Suspicious command patterns and thresholds

## 📊 Dashboard Features

The interactive dashboard provides a comprehensive view of system status and metrics:

- **System Overview**: Real-time CPU, memory, and process metrics
- **Task Management**: Create and monitor tasks with risk assessment
- **Alert Center**: View active alerts with severity classification
- **Process Monitor**: Top processes with resource usage
- **Analytics Section**: Historical data analysis and trends
- **Application History**: Track applications used during monitoring sessions
- **Preferences**: Customize dashboard behavior and settings

### Real-time Updates

The dashboard features live updates through WebSocket connections:
- Instant metric updates
- Live alert notifications with audio cues
- Real-time process tracking
- Automatic refresh with configurable intervals

## 🔧 API Endpoints

### System Status and Control
- `GET /api/status` - Get current system status
- `POST /api/start_monitoring` - Start system monitoring
- `POST /api/stop_monitoring` - Stop system monitoring

### Task Management
- `GET /api/tasks` - Retrieve tasks (with limit parameter)
- `POST /api/tasks` - Create a new task
- `GET /api/task/stats` - Get task statistics

### Metrics and Analytics
- `GET /api/metrics` - Get system metrics (with hours parameter)
- `GET /api/analytics` - Get historical analytics (with days parameter)
- `GET /api/alerts` - Get active system alerts
- `GET /api/processes/chart-data` - Get process data formatted for charts

### Notifications
- `GET /api/notifications` - Get system notifications
- `POST /api/notifications/{id}/read` - Mark a notification as read
- `POST /api/notifications/mark_all_read` - Mark all notifications as read

### Export and Utilities
- `GET /api/export_metrics_mysql` - Export metrics as MySQL dump
- `GET /healthz` - Basic liveness probe
- `GET /readyz` - Readiness probe with database connectivity check

## 🛡️ Security Features

JARM incorporates multiple layers of security protection:

- **Task Risk Assessment**: Analyzes commands for potentially harmful operations
- **Threat Pattern Recognition**: Identifies malware indicators and suspicious activities
- **Privilege Escalation Detection**: Monitors for unauthorized privilege attempts
- **Automated Response**: Implements security actions based on threat severity
- **Audit Trail**: Logs all security actions for compliance and analysis

## 📈 Machine Learning Integration

The system leverages reinforcement learning for intelligent decision-making:

- **Q-Learning Algorithm**: Learns optimal actions based on system state
- **State Representation**: Encodes system context into learning states
- **Reward System**: Provides feedback for learning optimization
- **Adaptive Policies**: Balances exploration and exploitation for continuous improvement

## 🗃️ Database Schema

### Tasks Table
Stores information about created tasks:
- `id`: Unique identifier
- `task_name`: Name of the task
- `task_description`: Description of the task
- `task_command`: Command to execute
- `category`: Risk category (Non-Harmful, Little Harmful, Very Harmful)
- `risk_score`: Numerical risk assessment (0.0 - 1.0)
- `status`: Current status (pending, running, completed, failed)
- `created_at`, `updated_at`: Timestamps

### Alerts Table
Records system alerts:
- `id`: Unique identifier
- `alert_type`: Type of alert
- `severity`: Severity level (Low, Medium, High, Critical)
- `message`: Alert message
- `source`: Source of the alert
- `confidence_score`: Confidence in the alert (0.0 - 1.0)
- `created_at`: Timestamp

### System Metrics Table
Stores historical system metrics:
- `id`: Unique identifier
- `timestamp`: When the metrics were recorded
- `cpu_usage`: CPU utilization percentage
- `memory_usage`: Memory utilization percentage
- `disk_usage`: Disk utilization percentage
- `network_io`: Network I/O statistics
- `active_processes`: Number of active processes

### Notifications Table
User-facing notifications:
- `id`: Unique identifier
- `severity`: Severity level
- `category`: Category of notification
- `message`: Notification message
- `timestamp`: When the notification was created
- `is_read`: Read status (0 = unread, 1 = read)

## 🎨 Frontend Components

### Dashboard Interface
Built with modern JavaScript and responsive design:
- Real-time charts using Chart.js
- Interactive controls and settings
- Responsive layout for all device sizes
- Audio notifications for alerts
- Toast notifications for user feedback

### API Client
JavaScript client for communicating with backend services:
- Centralized API communication
- Error handling and retry logic
- Promise-based interface

### Real-time Manager
WebSocket integration for live updates:
- Connection management
- Event handling
- Automatic reconnection

## 🤝 Contributing

We welcome contributions to JARM! Here's how you can help:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please ensure your code follows the existing style and includes appropriate tests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

JARM builds upon several excellent open-source technologies:

- [Flask](https://palletsprojects.com/p/flask/) - Web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [Chart.js](https://www.chartjs.org/) - Data visualization
- [Socket.IO](https://socket.io/) - Real-time communication
- [psutil](https://github.com/giampaolo/psutil) - System and process utilities
- [NumPy](https://numpy.org/) and [Pandas](https://pandas.pydata.org/) - Data processing
- [Scikit-learn](https://scikit-learn.org/) - Machine learning algorithms
- [Gym](https://gym.openai.com/) and [Stable-Baselines3](https://github.com/DLR-RM/stable-baselines3) - Reinforcement learning
