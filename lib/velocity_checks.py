# lib/velocity_checks.py - Velocity and pattern detection
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from lib.db import get_engine, transactions, users

class VelocityChecker:
    def __init__(self):
        self.rules = {
            "max_amount_1h": 5000,
            "max_amount_24h": 10000,
            "max_tx_count_1h": 10,
            "max_tx_count_24h": 50,
            "max_unique_recipients_24h": 20
        }
    
    def check_velocity(self, user_id, amount):
        """Check if transaction violates velocity rules"""
        eng = get_engine()
        now = datetime.utcnow()
        violations = []
        
        with eng.begin() as conn:
            # Check 1-hour velocity
            hour_ago = now - timedelta(hours=1)
            recent_1h = conn.execute(
                select(transactions.c.amount)
                .where(and_(
                    transactions.c.sender_id == user_id,
                    transactions.c.created_at >= hour_ago,
                    transactions.c.status.in_(["Success", "Under Review"])
                ))
            ).fetchall()
            
            amount_1h = sum(tx.amount for tx in recent_1h)
            count_1h = len(recent_1h)
            
            if amount_1h + amount > self.rules["max_amount_1h"]:
                violations.append(f"1h amount limit exceeded: ${amount_1h + amount:.2f}")
            
            if count_1h + 1 > self.rules["max_tx_count_1h"]:
                violations.append(f"1h transaction count exceeded: {count_1h + 1}")
            
            # Check 24-hour velocity
            day_ago = now - timedelta(hours=24)
            recent_24h = conn.execute(
                select(transactions.c.amount, transactions.c.recipient_id)
                .where(and_(
                    transactions.c.sender_id == user_id,
                    transactions.c.created_at >= day_ago,
                    transactions.c.status.in_(["Success", "Under Review"])
                ))
            ).fetchall()
            
            amount_24h = sum(tx.amount for tx in recent_24h)
            count_24h = len(recent_24h)
            unique_recipients = len(set(tx.recipient_id for tx in recent_24h if tx.recipient_id))
            
            if amount_24h + amount > self.rules["max_amount_24h"]:
                violations.append(f"24h amount limit exceeded: ${amount_24h + amount:.2f}")
            
            if count_24h + 1 > self.rules["max_tx_count_24h"]:
                violations.append(f"24h transaction count exceeded: {count_24h + 1}")
            
            if unique_recipients > self.rules["max_unique_recipients_24h"]:
                violations.append(f"Too many unique recipients: {unique_recipients}")
        
        return violations, {
            "amount_1h": amount_1h,
            "amount_24h": amount_24h,
            "count_1h": count_1h,
            "count_24h": count_24h,
            "unique_recipients_24h": unique_recipients
        }

class PatternDetector:
    def detect_suspicious_patterns(self, amount, description, recent_transactions):
        """Detect suspicious transaction patterns"""
        patterns = []
        
        # Round amount detection
        if amount >= 100 and amount % 100 == 0:
            patterns.append("Round amount")
        
        # Sequential amounts
        if recent_transactions:
            amounts = [tx.amount for tx in recent_transactions[-5:]]
            if len(amounts) >= 3:
                # Check for arithmetic progression
                diffs = [amounts[i+1] - amounts[i] for i in range(len(amounts)-1)]
                if len(set(diffs)) == 1 and diffs[0] != 0:
                    patterns.append("Sequential amounts")
        
        # Repetitive descriptions
        if recent_transactions:
            descriptions = [tx.description for tx in recent_transactions[-10:] if tx.description]
            if descriptions and descriptions.count(description) >= 3:
                patterns.append("Repetitive description")
        
        # High frequency small amounts (card testing)
        small_amounts = [tx for tx in recent_transactions[-20:] if tx.amount < 10]
        if len(small_amounts) >= 5:
            patterns.append("Possible card testing")
        
        return patterns
