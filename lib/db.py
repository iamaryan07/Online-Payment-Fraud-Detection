# lib/db.py - Complete fixed schema without meta column issues
from sqlalchemy import create_engine, Table, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, JSON, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import os
import datetime
import hashlib
import secrets

# Database configuration
DB_URL = os.getenv("APP_DB_URL", "sqlite:///fraud_app.db")

sqlite_args = {
    "check_same_thread": False,
    "timeout": 30,
    "isolation_level": None
}

_engine = create_engine(
    DB_URL, 
    connect_args=sqlite_args if DB_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

_session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
_metadata = MetaData()

# Database tables with CORRECTED SCHEMA - NO META COLUMN
users = Table(
    "users", _metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String, unique=True, nullable=False),
    Column("phone", String),
    Column("password_hash", String, nullable=False),
    Column("role", String, nullable=False),
    Column("status", String, default="pending"),
    Column("name", String),
    Column("balance", Float, default=0.0),
    Column("kyc_status", String, default="not_submitted"),
    Column("created_at", DateTime, server_default=func.now()),
)

kyc_docs = Table(
    "kyc_docs", _metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("doc_type", String),
    Column("doc_url", String),
    Column("uploaded_at", DateTime, server_default=func.now())
)

transactions = Table(
    "transactions", _metadata,
    Column("id", Integer, primary_key=True),
    Column("sender_id", Integer, ForeignKey("users.id")),
    Column("recipient_id", Integer, ForeignKey("users.id")),
    Column("transaction_type", String, default="payment"),
    Column("amount", Float),
    Column("currency", String, default="USD"),
    Column("description", String, default=""),
    Column("ip", String),
    Column("device", String),
    Column("location", String),
    Column("status", String, default="Success"),
    Column("risk_score", Float, default=0.0),
    Column("details", JSON),
    Column("created_at", DateTime, server_default=func.now())
)

cases = Table(
    "cases", _metadata,
    Column("id", Integer, primary_key=True),
    Column("transaction_id", Integer, ForeignKey("transactions.id")),
    Column("assigned_to", Integer, ForeignKey("users.id")),
    Column("status", String, default="Assigned"),
    Column("finding", String, default=""),
    Column("report", Text, default=""),
    Column("priority", String, default="Medium"),
    Column("created_at", DateTime, server_default=func.now()),
    Column("updated_at", DateTime, onupdate=func.now())
)

tickets = Table(
    "tickets", _metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("subject", String),
    Column("message", Text),
    Column("status", String, default="Open"),
    Column("created_at", DateTime, server_default=func.now())
)

# FIXED: audit_logs with NO META COLUMN - only simple string details
audit_logs = Table(
    "audit_logs", _metadata,
    Column("id", Integer, primary_key=True),
    Column("actor_user_id", Integer, ForeignKey("users.id")),
    Column("action", String),
    Column("entity_type", String),
    Column("entity_id", Integer),
    Column("details", String),  # Simple String field only - NO META COLUMN
    Column("created_at", DateTime, server_default=func.now())
)

settings = Table(
    "settings", _metadata,
    Column("id", Integer, primary_key=True),
    Column("key", String, unique=True),
    Column("value", JSON)
)

# Password functions
def hash_password(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{password_hash}:{salt}"

def verify_password(password, stored_hash):
    try:
        password_hash, salt = stored_hash.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == password_hash
    except:
        return False

# Phone validation and formatting
def validate_phone(phone):
    """Validate phone number format"""
    if not phone:
        return True  # Phone is optional
    
    # Remove all non-digits
    digits = ''.join(filter(str.isdigit, phone))
    return len(digits) == 10

def format_phone(phone):
    """Format phone number as XXX-XXX-XXXX"""
    if not phone:
        return None
    
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return phone

def init_db():
    _metadata.create_all(_engine)
    
    from sqlalchemy import select, insert
    
    with _engine.begin() as conn:
        # System settings
        default_settings = {
            "tx_limit_amount": 5000.0,
            "max_failed_attempts": 3,
            "unusual_locations": ["Unknown", "High-Risk-Geo"],
            "flag_threshold": 0.4,
            "block_threshold": 0.7,
            "default_user_balance": 2000.0
        }
        
        existing_settings = conn.execute(select(settings).where(settings.c.key == "system")).fetchone()
        if not existing_settings:
            conn.execute(insert(settings).values(key="system", value=default_settings))
        
        # Default users with proper balances
        default_users = [
            ("System Administrator", "admin@fraud-detect.local", "555-000-0001", "admin", "admin123", "approved", 100000.0),
            ("Cyber Security Officer", "cyber@fraud-detect.local", "555-000-0002", "cyber", "cyber123", "approved", 50000.0),
            ("John Customer", "user@fraud-detect.local", "555-000-0003", "user", "user123", "approved", 10000.0),
            ("Jane Smith", "user2@fraud-detect.local", "555-000-0004", "user", "user123", "approved", 8000.0),
            ("Mike Johnson", "user3@fraud-detect.local", "555-000-0005", "user", "user123", "approved", 5000.0)
        ]
        
        for name, email, phone, role, password, status, balance in default_users:
            existing = conn.execute(select(users).where(users.c.email == email)).fetchone()
            if not existing:
                password_hash = hash_password(password)
                conn.execute(insert(users).values(
                    name=name, email=email, phone=phone, role=role,
                    password_hash=password_hash, status=status, balance=balance,
                    kyc_status="submitted" if role == "user" else "not_applicable"
                ))

def get_engine():
    return _engine

def get_session():
    return _session()

def get_user_balance(user_id):
    """Get current user balance from database"""
    from sqlalchemy import select
    with _engine.begin() as conn:
        user = conn.execute(select(users.c.balance).where(users.c.id == user_id)).fetchone()
        return user.balance if user else 0.0

def update_user_balance(user_id, new_balance):
    """Update user balance in database"""
    from sqlalchemy import update
    with _engine.begin() as conn:
        conn.execute(update(users).where(users.c.id == user_id).values(balance=new_balance))
