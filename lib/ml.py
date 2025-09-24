# lib/ml.py - Enhanced ML with realistic features
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import datetime
import json

class AdvancedFraudModel:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.trained = False
        self.feature_names = [
            'amount', 'hour', 'day_of_week', 'failed_attempts', 'unusual_location',
            'device_risk', 'amount_velocity_1h', 'amount_velocity_24h', 'tx_count_1h',
            'tx_count_24h', 'recipient_new', 'sender_balance_ratio', 'round_amount'
        ]

    def _extract_features(self, tx, user_history=None):
        """Extract realistic fraud detection features"""
        amount = float(tx.get("amount", 0))
        hour = int(tx.get("hour", 12))
        day_of_week = datetime.datetime.now().weekday()
        failed_attempts = int(tx.get("failed_attempts", 0))
        
        # Location risk
        unusual_location = 1 if tx.get("location") in ["Unknown", "High-Risk-Geo"] else 0
        
        # Device risk
        risky_devices = ["emulator", "rooted", "unknown"]
        device_risk = 1 if tx.get("device", "").lower() in risky_devices else 0
        
        # Velocity features (would be calculated from user_history in real system)
        amount_velocity_1h = user_history.get("amount_1h", 0) if user_history else 0
        amount_velocity_24h = user_history.get("amount_24h", 0) if user_history else 0
        tx_count_1h = user_history.get("count_1h", 0) if user_history else 0
        tx_count_24h = user_history.get("count_24h", 0) if user_history else 0
        
        # Behavioral features
        recipient_new = 1 if tx.get("recipient_new", False) else 0
        sender_balance = float(tx.get("sender_balance", 1000))
        sender_balance_ratio = min(amount / sender_balance, 1.0) if sender_balance > 0 else 1.0
        
        # Amount pattern
        round_amount = 1 if amount % 100 == 0 and amount >= 100 else 0
        
        return np.array([
            amount, hour, day_of_week, failed_attempts, unusual_location,
            device_risk, amount_velocity_1h, amount_velocity_24h, tx_count_1h,
            tx_count_24h, recipient_new, sender_balance_ratio, round_amount
        ])

    def fit_realistic_data(self):
        """Train with more realistic synthetic data"""
        X = []
        y = []
        
        # Generate realistic training data
        for _ in range(2000):
            # Normal transactions
            amount = np.random.lognormal(4, 1)  # Log-normal distribution for amounts
            hour = np.random.randint(6, 23)  # Normal hours
            day_of_week = np.random.randint(0, 7)
            failed_attempts = np.random.choice([0, 1], p=[0.9, 0.1])
            unusual_location = 0
            device_risk = 0
            amount_velocity_1h = np.random.exponential(50)
            amount_velocity_24h = np.random.exponential(200)
            tx_count_1h = np.random.poisson(1)
            tx_count_24h = np.random.poisson(5)
            recipient_new = np.random.choice([0, 1], p=[0.7, 0.3])
            sender_balance_ratio = np.random.uniform(0, 0.3)  # Normal spending ratio
            round_amount = np.random.choice([0, 1], p=[0.8, 0.2])
            
            X.append([amount, hour, day_of_week, failed_attempts, unusual_location,
                     device_risk, amount_velocity_1h, amount_velocity_24h, tx_count_1h,
                     tx_count_24h, recipient_new, sender_balance_ratio, round_amount])
            y.append(0)  # Normal transaction
        
        # Fraudulent transactions
        for _ in range(500):
            amount = np.random.lognormal(6, 1.5)  # Larger amounts
            hour = np.random.choice([2, 3, 4, 23, 0, 1])  # Unusual hours
            day_of_week = np.random.randint(0, 7)
            failed_attempts = np.random.choice([2, 3, 4, 5], p=[0.3, 0.3, 0.2, 0.2])
            unusual_location = np.random.choice([0, 1], p=[0.3, 0.7])
            device_risk = np.random.choice([0, 1], p=[0.4, 0.6])
            amount_velocity_1h = np.random.exponential(500)  # High velocity
            amount_velocity_24h = np.random.exponential(2000)
            tx_count_1h = np.random.poisson(5)  # Many transactions
            tx_count_24h = np.random.poisson(20)
            recipient_new = np.random.choice([0, 1], p=[0.3, 0.7])  # Often new recipients
            sender_balance_ratio = np.random.uniform(0.5, 1.0)  # High spending ratio
            round_amount = np.random.choice([0, 1], p=[0.4, 0.6])  # More round amounts
            
            X.append([amount, hour, day_of_week, failed_attempts, unusual_location,
                     device_risk, amount_velocity_1h, amount_velocity_24h, tx_count_1h,
                     tx_count_24h, recipient_new, sender_balance_ratio, round_amount])
            y.append(1)  # Fraudulent transaction
        
        X = np.array(X)
        y = np.array(y)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model.fit(X_scaled, y)
        self.trained = True
        
        return self.model.score(X_scaled, y)

    def predict_proba(self, tx, user_history=None):
        """Predict fraud probability with enhanced features"""
        if not self.trained:
            accuracy = self.fit_realistic_data()
            print(f"Model trained with accuracy: {accuracy:.3f}")
        
        features = self._extract_features(tx, user_history).reshape(1, -1)
        features_scaled = self.scaler.transform(features)
        prob = self.model.predict_proba(features_scaled)[0, 1]
        
        return float(prob)

    def get_feature_importance(self):
        """Get feature importance for explainability"""
        if self.trained:
            importance = self.model.feature_importances_
            return dict(zip(self.feature_names, importance))
        return {}
