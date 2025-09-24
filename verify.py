from sqlalchemy import text
from lib.db import get_engine

def check_database():
    eng = get_engine()
    with eng.connect() as conn:
        # Show all users
        users = conn.execute(text("SELECT * FROM users")).fetchall()
        
        print(f"📊 Found {len(users)} users in database:")
        for user in users:
            print(f"ID: {user.id} | Email: {user.email} | Role: {user.role} | Status: {user.status}")
            print(f"Hash: {user.password_hash[:30]}...")
            print("---")

if __name__ == "__main__":
    check_database()
