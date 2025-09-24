# add_demo_users.py - Add demo users to database
import hashlib
from sqlalchemy import create_engine, text
from datetime import datetime

def hash_password(password):
    """Hash password using SHA-256 (matching your app's method)"""
    return hashlib.sha256(password.encode()).hexdigest()

def add_demo_users():
    """Add the three demo users to database"""
    try:
        # Connect to your database
        engine = create_engine('sqlite:///fraud_app.db')
        
        # Demo users data
        demo_users = [
            {
                'name': 'System Administrator',
                'email': 'admin@fraud-detect.local',
                'password': 'admin123',
                'role': 'admin',
                'status': 'approved',
                'balance': 10000.00,
                'phone': '+1-555-0001'
            },
            {
                'name': 'Cyber Security Officer',
                'email': 'cyber@fraud-detect.local',
                'password': 'cyber123',
                'role': 'cyber',
                'status': 'approved',
                'balance': 5000.00,
                'phone': '+1-555-0002'
            },
            {
                'name': 'Demo Customer',
                'email': 'user@fraud-detect.local',
                'password': 'user123',
                'role': 'user',
                'status': 'approved',
                'balance': 2000.00,
                'phone': '+1-555-0003'
            }
        ]
        
        with engine.connect() as conn:
            for user_data in demo_users:
                # Check if user already exists
                existing = conn.execute(
                    text("SELECT id FROM users WHERE email = :email"), 
                    {'email': user_data['email']}
                ).fetchone()
                
                if existing:
                    print(f"⚠️  User {user_data['email']} already exists (ID: {existing.id})")
                    continue
                
                # Hash the password
                hashed_password = hash_password(user_data['password'])
                
                # Insert new user
                conn.execute(text("""
                    INSERT INTO users (name, email, password_hash, role, status, balance, phone, created_at)
                    VALUES (:name, :email, :password_hash, :role, :status, :balance, :phone, :created_at)
                """), {
                    'name': user_data['name'],
                    'email': user_data['email'],
                    'password_hash': hashed_password,
                    'role': user_data['role'],
                    'status': user_data['status'],
                    'balance': user_data['balance'],
                    'phone': user_data['phone'],
                    'created_at': datetime.now()
                })
                
                print(f"✅ Added user: {user_data['email']} (Role: {user_data['role']})")
            
            conn.commit()
            print(f"\n🎉 Demo users setup complete!")
            
            # Show all users
            users = conn.execute(text("SELECT id, email, role, balance FROM users")).fetchall()
            print(f"\n📊 Current users in database ({len(users)} total):")
            for user in users:
                print(f"  - ID: {user.id}, Email: {user.email}, Role: {user.role}, Balance: ${user.balance:.2f}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    add_demo_users()
