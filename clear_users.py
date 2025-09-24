# clear_users.py - Delete all users from database
from sqlalchemy import create_engine, text

def delete_all_users():
    """Delete ALL users from database"""
    try:
        # Connect to your database
        engine = create_engine('sqlite:///fraud_app.db')
        
        with engine.connect() as conn:
            # Count users before deletion
            count_before = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            print(f"📊 Found {count_before} users in database")
            
            if count_before == 0:
                print("✅ Database is already empty")
                return
            
            # Show all users that will be deleted
            users = conn.execute(text("SELECT id, email, role FROM users")).fetchall()
            print("👥 Users to be deleted:")
            for user in users:
                print(f"  - ID: {user.id}, Email: {user.email}, Role: {user.role}")
            
            # Confirm deletion
            confirm = input(f"\n⚠️  Are you sure you want to delete ALL {count_before} users? (yes/no): ")
            
            if confirm.lower() in ['yes', 'y']:
                # Delete all users
                result = conn.execute(text("DELETE FROM users"))
                conn.commit()
                
                print(f"✅ Successfully deleted {result.rowcount} users!")
                print("🗂️ Users table is now empty")
            else:
                print("❌ Operation cancelled")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    delete_all_users()
