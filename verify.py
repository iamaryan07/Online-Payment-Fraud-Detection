# fix_passwords_bcrypt.py - Fix passwords using bcrypt (matching your system)
from sqlalchemy import create_engine, text

def fix_demo_passwords():
    """Fix demo user passwords to work with your bcrypt system"""
    try:
        engine = create_engine('sqlite:///fraud_app.db')
        
        # Try to use bcrypt if available
        try:
            import bcrypt
            print("✅ Using bcrypt hashing (recommended)")
            
            demo_updates = [
                ('admin@fraud-detect.local', 'admin123'),
                ('cyber@fraud-detect.local', 'cyber123'), 
                ('user@fraud-detect.local', 'user123')
            ]
            
            with engine.connect() as conn:
                for email, password in demo_updates:
                    # Generate bcrypt hash
                    salt = bcrypt.gensalt()
                    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
                    hashed_str = hashed.decode('utf-8')
                    
                    # Update the user's password
                    result = conn.execute(text("""
                        UPDATE users 
                        SET password_hash = :password_hash 
                        WHERE email = :email
                    """), {
                        'password_hash': hashed_str,
                        'email': email
                    })
                    
                    if result.rowcount > 0:
                        print(f"✅ Updated password for {email}")
                        print(f"   New hash: {hashed_str[:30]}...")
                    else:
                        print(f"❌ User {email} not found")
                
                conn.commit()
                print("\n🎉 All demo passwords updated with bcrypt!")
                
        except ImportError:
            print("❌ bcrypt not available, using fallback method...")
            
            # Fallback: Try to match your existing hash format
            import hashlib
            import secrets
            
            demo_updates = [
                ('admin@fraud-detect.local', 'admin123'),
                ('cyber@fraud-detect.local', 'cyber123'),
                ('user@fraud-detect.local', 'user123')
            ]
            
            with engine.connect() as conn:
                for email, password in demo_updates:
                    # Generate salt and hash (matching your format)
                    salt = secrets.token_hex(16)  # 32-char hex salt
                    hash_part = hashlib.sha256((password + salt).encode()).hexdigest()
                    combined_hash = f"{hash_part}:{salt}"
                    
                    # Update user password
                    result = conn.execute(text("""
                        UPDATE users 
                        SET password_hash = :password_hash 
                        WHERE email = :email
                    """), {
                        'password_hash': combined_hash,
                        'email': email
                    })
                    
                    if result.rowcount > 0:
                        print(f"✅ Updated password for {email}")
                        print(f"   New hash: {combined_hash[:30]}...")
                    else:
                        print(f"❌ User {email} not found")
                
                conn.commit()
                print("\n🎉 All demo passwords updated with salted hash!")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_demo_passwords()
