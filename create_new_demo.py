import hashlib
import bcrypt
from datetime import datetime
from sqlalchemy import text
from lib.db import get_engine

def create_fresh_demo_accounts():
    """Create completely new demo accounts that will work"""
    eng = get_engine()
    
    # New simple demo accounts
    new_accounts = [
        {
            'name': 'Demo User',
            'email': 'demo@user.com',
            'password': 'demo123',
            'role': 'user',
            'balance': 5000.0
        },
        {
            'name': 'Demo Admin',
            'email': 'demo@admin.com', 
            'password': 'admin',
            'role': 'admin',
            'balance': 0.0
        },
        {
            'name': 'Demo Cyber',
            'email': 'demo@cyber.com',
            'password': 'cyber',
            'role': 'cyber', 
            'balance': 0.0
        }
    ]
    
    with eng.connect() as conn:
        print("🧹 Creating fresh demo accounts...")
        
        # Delete any existing demo accounts first
        for account in new_accounts:
            conn.execute(text("DELETE FROM users WHERE email = :email"), 
                        {'email': account['email']})
        
        # Create accounts using the SAME method as your working user
        for account in new_accounts:
            # Use simple SHA256 (most common format)
            password_hash = hashlib.sha256(account['password'].encode()).hexdigest()
            
            # Insert new account
            conn.execute(text("""
                INSERT INTO users (name, email, password_hash, role, status, balance, created_at, phone)
                VALUES (:name, :email, :password_hash, :role, :status, :balance, :created_at, :phone)
            """), {
                'name': account['name'],
                'email': account['email'], 
                'password_hash': password_hash,
                'role': account['role'],
                'status': 'active',
                'balance': account['balance'],
                'created_at': datetime.now(),
                'phone': '9999999999'
            })
            
            print(f"✅ Created {account['role'].upper()}: {account['email']}")
            print(f"   Password: {account['password']}")
            print(f"   Hash: SHA256")
        
        conn.commit()
        
        print("\n🎯 NEW DEMO CREDENTIALS:")
        print("=" * 50)
        for account in new_accounts:
            print(f"🔑 {account['role'].upper()} LOGIN:")
            print(f"   Email: {account['email']}")
            print(f"   Password: {account['password']}")
            print("-" * 30)
        
        # Test authentication for each account
        print("\n🧪 TESTING AUTHENTICATION:")
        from app import authenticate_via_lib_auth
        
        for account in new_accounts:
            try:
                result = authenticate_via_lib_auth(account['email'], account['password'])
                if result and result.get('success'):
                    user = result['user'] 
                    print(f"✅ {account['email']} - LOGIN SUCCESS")
                    print(f"   Role: {user.role}")
                    print(f"   Status: {user.status}")
                else:
                    print(f"❌ {account['email']} - LOGIN FAILED")
            except Exception as e:
                print(f"💥 {account['email']} - ERROR: {str(e)}")

if __name__ == "__main__":
    create_fresh_demo_accounts()
