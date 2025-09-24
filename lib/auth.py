# lib/auth.py - Complete working version with phone validation and database lock fixes
import streamlit as st
from sqlalchemy import select, insert, update
from email_validator import validate_email, EmailNotValidError
import re
import time
import random
from lib.db import get_engine, users, audit_logs, hash_password, verify_password

def ensure_session_keys():
    """Initialize session state keys if they don't exist"""
    for k, v in {
        "auth_status": False,
        "user_id": None,
        "role": None,
        "email": None,
        "name": None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

def validate_phone(phone):
    """Validate 10-digit phone number"""
    if not phone:
        return False
    
    # Remove any spaces, hyphens, parentheses, dots
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    # Check if it's exactly 10 digits
    if len(clean_phone) == 10 and clean_phone.isdigit():
        return True
    
    return False

def format_phone(phone):
    """Format phone number as XXX-XXX-XXXX"""
    if not phone:
        return phone
    
    # Remove any non-digits
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    # Format as XXX-XXX-XXXX if 10 digits
    if len(clean_phone) == 10:
        return f"{clean_phone[:3]}-{clean_phone[3:6]}-{clean_phone[6:]}"
    
    return phone

def log_audit(actor_user_id, action, entity_type, entity_id, meta=None):
    """Audit logging with retry mechanism to handle database locks"""
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            eng = get_engine()
            with eng.begin() as conn:
                conn.execute(audit_logs.insert().values(
                    actor_user_id=actor_user_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id or 0,
                    meta=meta or {}
                ))
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                # Add small random delay to avoid collision
                time.sleep(retry_delay + random.uniform(0, 0.1))
                retry_delay *= 2
            else:
                # Don't fail the main operation if audit fails
                print(f"Warning: Audit log failed after {max_retries} attempts: {e}")
                return False

def auth_login(email, password):
    """Handle user login with proper error handling"""
    try:
        eng = get_engine()
        with eng.begin() as conn:
            u = conn.execute(select(users).where(users.c.email == email)).fetchone()
            if not u:
                return False, "Invalid email or password"
            
            if u.status == "pending":
                return False, "Account pending admin approval"
            elif u.status == "rejected":
                return False, "Account has been rejected"
            elif u.status != "approved":
                return False, f"Account status: {u.status}"
            
            if not verify_password(password, u.password_hash):
                return False, "Invalid email or password"
            
            # Set session state
            st.session_state.update({
                "auth_status": True,
                "user_id": u.id,
                "role": u.role,
                "email": u.email,
                "name": u.name or u.email.split("@")[0]
            })
            
            # Log audit (non-blocking)
            log_audit(u.id, "login", "user", u.id, {"role": u.role})
            return True, f"Welcome back, {u.name or u.email}!"
            
    except Exception as e:
        return False, f"Login failed: {str(e)}"

def auth_logout():
    """Handle user logout"""
    uid = st.session_state.get("user_id")
    if uid:
        log_audit(uid, "logout", "user", uid, {})
    
    # Clear session state
    st.session_state.update({
        "auth_status": False,
        "user_id": None,
        "role": None,
        "email": None,
        "name": None
    })

def auth_register(name, email, phone, role, password):
    """Handle user registration with comprehensive validation"""
    
    # Input validation
    if not name or not name.strip():
        return False, "Full name is required"
    
    if not email or not email.strip():
        return False, "Email is required"
    
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    # Email validation
    try:
        validate_email(email.strip())
    except EmailNotValidError as e:
        return False, f"Invalid email: {str(e)}"

    # Phone validation
    if phone and not validate_phone(phone):
        return False, "Phone number must be exactly 10 digits (e.g., 1234567890 or 123-456-7890)"

    # Format inputs
    name = name.strip()
    email = email.strip().lower()
    formatted_phone = format_phone(phone) if phone else None
    
    # Hash password
    try:
        phash = hash_password(password)
    except Exception as e:
        return False, f"Password processing failed: {str(e)}"
    
    # Database operation with retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            eng = get_engine()
            with eng.begin() as conn:
                # Check for existing user
                existing = conn.execute(
                    select(users.c.id).where(users.c.email == email)
                ).fetchone()
                
                if existing:
                    return False, "Email already registered. Please use a different email or try logging in."
                
                # Insert new user
                result = conn.execute(users.insert().values(
                    name=name,
                    email=email,
                    phone=formatted_phone,
                    role=role,
                    password_hash=phash,
                    status="pending",
                    balance=0.0,
                    kyc_status="not_submitted"
                ))
                
                uid = result.inserted_primary_key[0]
            
            # Log audit (non-blocking)
            log_audit(uid, "register", "user", uid, {
                "role": role,
                "has_phone": bool(phone)
            })
            
            return True, "Registration successful! Your account is pending admin approval. You will be notified once approved."
            
        except Exception as e:
            error_str = str(e).lower()
            if "database is locked" in error_str and attempt < max_retries - 1:
                # Wait and retry for database locks
                time.sleep(0.5 + random.uniform(0, 0.5))
                continue
            elif "unique constraint" in error_str or "already exists" in error_str:
                return False, "Email already registered. Please use a different email."
            else:
                return False, f"Registration failed: {str(e)}"
    
    return False, "Registration failed after multiple attempts. Please try again."

def role_guard(required_roles):
    """Check if user has required role permissions"""
    if not st.session_state.get("auth_status"):
        st.warning("🔒 Please login to access this page.")
        st.stop()
    
    user_role = st.session_state.get("role")
    if user_role not in required_roles:
        st.error(f"🚫 Access denied. Required role: {'/'.join(required_roles)}. Your role: {user_role}")
        st.stop()

def render_auth_panel():
    """Render authentication panel in sidebar"""
    with st.sidebar:
        st.header("🔐 Authentication")
        
        if not st.session_state.get("auth_status"):
            # Not logged in - show login/register tabs
            tab_login, tab_register = st.tabs(["🔑 Login", "📝 Register"])
            
            with tab_login:
                with st.form("login_form", clear_on_submit=False):
                    st.markdown("**Login to your account**")
                    email = st.text_input("📧 Email", placeholder="your@email.com")
                    pwd = st.text_input("🔒 Password", type="password", placeholder="Enter password")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("🚀 Login", use_container_width=True, type="primary")
                    with col2:
                        if st.form_submit_button("🧹 Clear", use_container_width=True):
                            st.rerun()
                    
                    if submitted:
                        if not email or not pwd:
                            st.error("Please fill in all fields")
                        else:
                            with st.spinner("Logging in..."):
                                ok, msg = auth_login(email, pwd)
                            if ok:
                                st.success(msg)
                                time.sleep(1)  # Brief pause to show success message
                                st.rerun()
                            else:
                                st.error(msg)
                
                # Demo credentials info
                st.markdown("---")
                with st.expander("🎯 Demo Credentials"):
                    st.markdown("""
                    **Admin Account:**
                    - Email: `admin@fraud-detect.local`
                    - Password: `admin123`
                    
                    **User Account:**  
                    - Email: `user@fraud-detect.local`
                    - Password: `user123`
                    
                    **Cyber Official:**
                    - Email: `cyber@fraud-detect.local`  
                    - Password: `cyber123`
                    """)
            
            with tab_register:
                with st.form("register_form", clear_on_submit=True):
                    st.markdown("**Create new account**")
                    
                    name = st.text_input("👤 Full Name", placeholder="John Doe")
                    email = st.text_input("📧 Email", placeholder="john@example.com")
                    phone = st.text_input(
                        "📱 Phone (10 digits)", 
                        placeholder="1234567890 or 123-456-7890",
                        help="Enter exactly 10 digits. Examples: 1234567890, 123-456-7890, (123) 456-7890"
                    )
                    role = st.selectbox("👔 Role", ["user"], help="Users can self-register. Admin/Cyber roles are assigned by administrators.")
                    pwd = st.text_input("🔒 Password", type="password", placeholder="Minimum 6 characters")
                    confirm_pwd = st.text_input("🔒 Confirm Password", type="password", placeholder="Re-enter password")
                    
                    submitted = st.form_submit_button("📝 Create Account", use_container_width=True, type="primary")
                    
                    if submitted:
                        # Validation
                        if not all([name, email, pwd]):
                            st.error("Please fill in all required fields (Name, Email, Password)")
                        elif pwd != confirm_pwd:
                            st.error("Passwords do not match")
                        elif len(pwd) < 6:
                            st.error("Password must be at least 6 characters long")
                        else:
                            with st.spinner("Creating account..."):
                                ok, msg = auth_register(name, email, phone, role, pwd)
                            
                            if ok:
                                st.success(msg)
                                st.balloons()
                            else:
                                st.error(msg)
        
        else:
            # Logged in - show user info and logout
            user_name = st.session_state.get('name', 'User')
            user_role = st.session_state.get('role', 'user')
            user_email = st.session_state.get('email', '')
            
            st.success(f"✅ **Logged in**")
            
            # User info card
            with st.container():
                st.markdown(f"""
                **👤 {user_name}**  
                **📧** {user_email}  
                **👔** {user_role.title()}
                """)
            
            st.markdown("---")
            
            # Role-specific quick info
            if user_role == "admin":
                st.info("🛠️ **Admin Panel**\nFull system access")
            elif user_role == "cyber":
                st.info("🕵️ **Cyber Official**\nFraud investigation access")
            elif user_role == "user":
                st.info("👤 **Customer Account**\nPayment and profile access")
            
            st.markdown("---")
            
            # Logout button
            if st.button("🚪 Logout", use_container_width=True, type="secondary"):
                auth_logout()
                st.success("Logged out successfully!")
                time.sleep(1)
                st.rerun()

# Additional utility functions for other modules to use
def get_current_user_id():
    """Get current logged in user ID"""
    return st.session_state.get("user_id")

def get_current_user_role():
    """Get current logged in user role"""
    return st.session_state.get("role")

def get_current_user_email():
    """Get current logged in user email"""
    return st.session_state.get("email")

def is_authenticated():
    """Check if user is authenticated"""
    return st.session_state.get("auth_status", False)

def require_auth():
    """Decorator-like function to require authentication"""
    if not is_authenticated():
        st.warning("🔒 Please login to access this feature.")
        st.stop()

# Input validation utilities
def validate_email_format(email):
    """Validate email format without external library"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None

def validate_password_strength(password):
    """Basic password strength validation"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    # Optional: Add more strength checks
    # if not re.search(r'[A-Za-z]', password):
    #     return False, "Password must contain letters"
    # if not re.search(r'\d', password):
    #     return False, "Password must contain numbers"
    
    return True, "Password is valid"

def sanitize_input(text):
    """Basic input sanitization"""
    if not text:
        return text
    return text.strip()[:255]  # Limit length and strip whitespace
