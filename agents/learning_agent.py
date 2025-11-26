import numpy as np
import json
import pickle
import os
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from models import DatabaseManager, Alert, Task
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QLearningAgent:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.alpha = Config.Q_LEARNING_ALPHA  # Learning rate
        self.gamma = Config.Q_LEARNING_GAMMA  # Discount factor
        self.epsilon = Config.Q_LEARNING_EPSILON  # Exploration rate
        self.q_table = {}
        self.state_size = 10  # Number of features in state representation
        self.action_size = 4  # Number of possible actions (ALLOW, WARN, BLOCK, ESCALATE)

        # Load existing Q-table if available
        self.load_q_table()

    def get_state_representation(self, context: Dict) -> str:
        """
        Convert context into state representation for Q-learning
        State features: [cpu_usage, memory_usage, alert_severity, task_risk,
                        repeated_alerts, system_stress, time_of_day, day_of_week,
                        recent_blocks, confidence_score]
        """
        features = []

        # System metrics (normalized to 0-1)
        features.append(min(context.get('cpu_usage', 0) / 100, 1.0))
        features.append(min(context.get('memory_usage', 0) / 100, 1.0))

        # Alert severity (0-3 for LOW, MEDIUM, HIGH, CRITICAL)
        severity_map = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
        features.append(severity_map.get(context.get('alert_severity', 'LOW'), 0) / 3)

        # Task risk score (0-1)
        features.append(context.get('task_risk', 0))

        # Repeated alerts (normalized)
        features.append(min(context.get('repeated_alerts', 0) / 10, 1.0))

        # System stress (boolean to float)
        features.append(1.0 if context.get('system_stress', False) else 0.0)

        # Time features (normalized)
        current_time = datetime.now()
        features.append(current_time.hour / 24)  # Hour of day
        features.append(current_time.weekday() / 7)  # Day of week

        # Recent blocks (normalized)
        features.append(min(context.get('recent_blocks', 0) / 5, 1.0))

        # Confidence score (0-1)
        features.append(context.get('confidence_score', 0))

        # Convert to state hash
        state_vector = np.array(features)
        return self._vector_to_hash(state_vector)

    def _vector_to_hash(self, vector: np.ndarray) -> str:
        """Convert state vector to hash string"""
        # Discretize continuous values for Q-table
        discretized = np.round(vector * 10).astype(int)
        return '_'.join(map(str, discretized))

    def get_q_value(self, state: str, action: int) -> float:
        """Get Q-value for state-action pair"""
        if state not in self.q_table:
            self.q_table[state] = np.zeros(self.action_size)
        return self.q_table[state][action]

    def update_q_value(self, state: str, action: int, reward: float, next_state: str):
        """Update Q-value using Q-learning formula"""
        if state not in self.q_table:
            self.q_table[state] = np.zeros(self.action_size)

        current_q = self.q_table[state][action]
        max_next_q = max(self.get_q_value(next_state, a) for a in range(self.action_size))

        # Q-learning update formula
        new_q = current_q + self.alpha * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state][action] = new_q

    def choose_action(self, state: str, context: Optional[Dict] = None) -> Tuple[int, float]:
        """
        Choose action using epsilon-greedy policy
        Returns: (action_index, confidence)
        """
        if state not in self.q_table:
            self.q_table[state] = np.zeros(self.action_size)

        # Epsilon-greedy exploration
        if np.random.random() < self.epsilon:
            # Explore: random action
            action = np.random.randint(0, self.action_size)
            confidence = 0.5  # Low confidence for random actions
        else:
            # Exploit: best known action
            q_values = self.q_table[state]
            action = int(np.argmax(q_values))
            # Ensure a reasonable lower bound for exploitation confidence
            confidence = max(0.5, min(float(q_values[action]) / 10.0, 1.0))

        return int(action), float(confidence)

    def calculate_reward(self, action: int, outcome: Dict) -> float:
        """
        Calculate reward based on action and outcome
        Returns reward value (-1 to 1)
        """
        reward = 0.0

        # Base reward for correct decisions
        if outcome.get('correct_decision', False):
            reward += 0.5
        else:
            reward -= 0.3

        # Penalty for false positives (blocking safe tasks)
        if action == 2 and outcome.get('false_positive', False):  # BLOCK action
            reward -= 0.8

        # Penalty for false negatives (allowing dangerous tasks)
        if action == 0 and outcome.get('false_negative', False):  # ALLOW action
            reward -= 1.0

        # Bonus for preventing actual threats
        if action == 2 and outcome.get('threat_prevented', False):  # BLOCK action
            reward += 1.0

        # Bonus for appropriate warnings
        if action == 1 and outcome.get('warning_appropriate', False):  # WARN action
            reward += 0.3

        # Penalty for unnecessary escalations
        if action == 3 and outcome.get('unnecessary_escalation', False):  # ESCALATE action
            reward -= 0.2

        return np.clip(reward, -1.0, 1.0)

    def learn_from_experience(self, state: str, action: int, reward: float, next_state: str):
        """Learn from a single experience"""
        self.update_q_value(state, action, reward, next_state)

        # Save to database
        self._save_state_to_db(state, action, reward)

    def _save_state_to_db(self, state: str, action: int, reward: float):
        """Save learning state (placeholder - database functionality removed)"""
        # Database functionality has been removed
        pass

    def load_q_table(self):
        """Load Q-table from database with error handling"""
        # Database functionality has been removed
        logger.info(f"Q-table loaded with {len(self.q_table)} states")

    def save_q_table(self):
        """Save Q-table to file and database with error handling"""
        # Save to file
        try:
            with open('q_table.pkl', 'wb') as f:
                pickle.dump(self.q_table, f)
            logger.info("Q-table saved to file")
        except Exception as e:
            logger.error(f"Error saving Q-table to file: {e}")

        # Database functionality has been removed
        logger.info("Q-table database saving skipped (database functionality removed)")

    def get_learning_statistics(self) -> Dict:
        """Get learning statistics with error handling"""
        # Database functionality has been removed
        return {
            'total_states': 0,
            'total_visits': 0,
            'q_table_size': len(self.q_table),
            'epsilon': self.epsilon,
            'alpha': self.alpha,
            'gamma': self.gamma
        }

    def decay_epsilon(self, decay_rate: float = 0.995):
        """Decay exploration rate over time"""
        self.epsilon = max(self.epsilon * decay_rate, 0.01)

    def train_on_historical_data(self, training_data: List[Dict]):
        """Train on historical data"""
        for experience in training_data:
            state = experience['state']
            action = experience['action']
            reward = experience['reward']
            next_state = experience.get('next_state', state)

            self.learn_from_experience(state, action, reward, next_state)

    def get_action_explanation(self, state: str, action: int) -> str:
        """Get explanation for why an action was chosen"""
        if state not in self.q_table:
            return "No previous experience with this state"

        q_values = self.q_table[state]
        action_names = ['ALLOW', 'WARN', 'BLOCK', 'ESCALATE']

        explanation = f"Action {action_names[action]} chosen with Q-value {q_values[action]:.3f}. "

        if action == np.argmax(q_values):
            explanation += "This is the best known action for this state."
        else:
            explanation += f"Best known action would be {action_names[np.argmax(q_values)]}."

        return explanation
