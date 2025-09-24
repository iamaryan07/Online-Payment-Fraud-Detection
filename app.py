# app.py - FINAL VERSION - Landing page only for users
import streamlit as st
import hashlib
from sqlalchemy import text
from lib.db import init_db, get_engine
from lib.auth import ensure_session_keys
from lib.ui import topbar_brand

# --- Role-Based Page Definitions ---

# app.py - Control what users SEE in navigation
def get_pages_for_role(role):
    """Return pages based on user role - Navigation controls what users see"""
    if role == "user":
        # User: User dashboard + landing page
        return [
            st.Page("pages/user_dashboard.py", title="User Dashboard", icon="🏠"),
            st.Page("pages/landing.py", title="Landing", icon="📄")
        ]
    elif role == "cyber":
        # Cyber: ONLY sees cyber dashboard (but admin can still access it)
        return [
            st.Page("pages/cyber_dashboard.py", title="Cyber Dashboard", icon="🕵️")
        ]
    elif role == "admin":
        # Admin: Sees both dashboards (and can access both)
        return [
            st.Page("pages/admin_dashboard.py", title="Admin Dashboard", icon="🛠️"),
            st.Page("pages/cyber_dashboard.py", title="Cyber Dashboard", icon="🕵️")
        ]
    else:
        return []



# --- Authentication Functions ---

def authenticate_via_lib_auth(email, password):
    """Updated authentication to handle your existing hash format"""
    try:
        from lib.auth import authenticate_user
        return authenticate_user(email, password)
    except ImportError:
        from sqlalchemy import text
        import hashlib
        
        eng = get_engine()
        with eng.connect() as conn:
            user = conn.execute(text("""
                SELECT id, name, email, role, status, balance, password_hash
                FROM users WHERE email = :email
            """), {'email': email}).fetchone()
            
            if user and user.password_hash:
                # Handle bcrypt format (if available)
                try:
                    import bcrypt
                    if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                        return {"success": True, "user": user}
                except:
                    pass
                
                # Handle hash:salt format (your current format)
                if ':' in user.password_hash:
                    try:
                        stored_hash, salt = user.password_hash.split(':')
                        computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                        if computed_hash == stored_hash:
                            return {"success": True, "user": user}
                    except:
                        pass
                
                # Handle plain SHA-256
                sha256_hash = hashlib.sha256(password.encode()).hexdigest()
                if user.password_hash == sha256_hash:
                    return {"success": True, "user": user}
                
                # Handle plain text fallback
                if user.password_hash == password:
                    return {"success": True, "user": user}
            
            return {"success": False}

def register_via_lib_auth(name, email, phone, password, role="user"):
    """Enhanced registration system with role selection and approval workflow"""
    try:
        from lib.auth import register_user
        return register_user(name, email, phone, password, role)
    except ImportError:
        import hashlib
        from sqlalchemy import text
        from datetime import datetime
        
        eng = get_engine()
        with eng.connect() as conn:
            # Check if email already exists
            existing = conn.execute(text("SELECT id FROM users WHERE email = :email"), {'email': email}).fetchone()
            if existing:
                return {"success": False, "message": "Email already registered"}
            
            # Hash password
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            
            # Set role-specific defaults
            if role == "cyber":
                status = "pending"  # Cyber registrations need approval
                balance = 0.0  # Cyber officials don't need balance
                role_title = "Cyber Security Official"
            else:  # user
                status = "pending"  # All registrations need approval now
                balance = 0.0  # Balance assigned after approval
                role_title = "Customer"
            
            # Insert new user with pending status
            conn.execute(text("""
                INSERT INTO users (name, email, phone, password_hash, role, status, balance, created_at)
                VALUES (:name, :email, :phone, :password_hash, :role, :status, :balance, :created_at)
            """), {
                'name': name, 
                'email': email, 
                'phone': phone, 
                'password_hash': hashed_pw,
                'role': role,
                'status': status,
                'balance': balance,
                'created_at': datetime.now()
            })
            conn.commit()
            
            return {
                "success": True, 
                "message": f"{role_title} registration submitted! Awaiting admin approval."
            }


# Initialize everything
init_db()
ensure_session_keys()

def main():
    # Page configuration
    st.set_page_config(
        page_title="Fraud Detection System", 
        page_icon="🔒", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # If user is not authenticated, show login/register
    if not st.session_state.get("auth_status"):
        
        # Hide sidebar completely for login page
        st.markdown("""
            <style>
            section[data-testid="stSidebar"] {display: none !important;}
            .main .block-container {padding-left: 1rem; padding-right: 1rem;}
            </style>
        """, unsafe_allow_html=True)
        
        topbar_brand()
        
        st.title("🔐 Login to SecurePay")
        st.write("Enter your credentials or use a demo account below.")
        
        # Login/Register tabs
        with st.container():
            login_tab, register_tab = st.tabs(["Login", "Register"])

            # Login Form
            with login_tab:
                with st.form("login_form"):
                    email = st.text_input("Email", key="login_email")
                    password = st.text_input("Password", type="password", key="login_password")
                    submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

                    if submitted:
                        if not email or not password:
                            st.error("❌ Please fill in all fields")
                        else:
                            auth_result = authenticate_via_lib_auth(email, password)
                            if auth_result and auth_result.get("success"):
                                user = auth_result["user"]
                                st.session_state.auth_status = True
                                st.session_state.user_id = user.id
                                st.session_state.email = user.email
                                st.session_state.role = user.role
                                st.success("✅ Login successful!")
                                st.rerun()
                            else:
                                st.error("❌ Invalid email or password")

            # Register Form - UPDATED with Role Dropdown and Approval Workflow
            with register_tab:
                with st.form("register_form"):
                    reg_name = st.text_input("Full Name", key="reg_name")
                    reg_email = st.text_input("Email", key="reg_email")
                    reg_phone = st.text_input("Phone Number", key="reg_phone")
                    
                    # NEW: Role Selection Dropdown
                    reg_role = st.selectbox("Account Type", [
                        "user", 
                        "cyber"
                    ], format_func=lambda x: {
                        "user": "👤 Customer Account", 
                        "cyber": "🕵️ Cyber Security Official"
                    }[x])
                    
                    reg_password = st.text_input("Password", type="password", key="reg_password")
                    reg_confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")
                    
                    # Show different info based on role selection
                    if reg_role == "cyber":
                        st.info("🕵️ **Cyber Security Registration**\nYour application will be reviewed by administrators before approval.")
                    else:
                        st.info("👤 **Customer Registration**\nYour account will be reviewed by administrators before approval.")
                    
                    submitted = st.form_submit_button("📝 Register", use_container_width=True)

                    if submitted:
                        if not all([reg_name, reg_email, reg_phone, reg_password, reg_confirm]):
                            st.error("❌ Please fill in all fields")
                        elif reg_password != reg_confirm:
                            st.error("❌ Passwords do not match")
                        elif len(reg_password) < 6:
                            st.error("❌ Password must be at least 6 characters")
                        else:
                            result = register_via_lib_auth(reg_name, reg_email, reg_phone, reg_password, reg_role)
                            if result and result.get("success"):
                                st.success(f"✅ {result.get('message', 'Registration successful!')}")
                                st.info("⏳ Your account is pending admin approval. You'll be notified once approved.")
                            else:
                                st.error(f"❌ {result.get('message', 'Registration failed')}")


        st.markdown("---")
        
        # Demo credentials - UPDATED descriptions
        st.markdown("### 🚀 Quick Access Demo Credentials")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("**👨‍💼 Admin**\n📧 admin@fraud-detect.local\n🔑 admin123\n🛠️ Admin + Cyber Access")
        with col2:
            st.info("**🕵️ Cyber Official**\n📧 cyber@fraud-detect.local\n🔑 cyber123\n🕵️ Cyber Access")
        with col3:
            st.info("**👤 Customer**\n📧 user@fraud-detect.local\n🔑 user123\n🏠 User Dashboard + Landing")
    
    # If authenticated, set up role-based navigation
    else:
        role = st.session_state.get("role")
        
        # Get role-based pages
        pages = get_pages_for_role(role)
        
        if pages:
            # Create navigation with role-based pages
            pg = st.navigation(pages)
            
            # Add user info and logout to sidebar
            st.sidebar.title("🔒 SecurePay")
            st.sidebar.markdown("---")
            
            # Show enhanced role info
            if role == "cyber":
                role_display = "Cyber (Admin Access)"
                role_emoji = "🕵️🛠️"
            elif role == "admin":
                role_display = "Admin (Full Access)"
                role_emoji = "🛠️"
            else:
                role_display = "Customer"
                role_emoji = "👤"
            
            st.sidebar.info(f"**Logged in as:** {st.session_state.get('email', 'Unknown')}\n**Role:** {role_emoji} {role_display}")
            st.sidebar.markdown("---")
            
            # Logout button
            if st.sidebar.button("🚪 Logout", use_container_width=True):
                # Clear all session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            
            # Show top bar
            topbar_brand()
            
            # Run the selected page
            pg.run()
        else:
            st.error("❌ No pages available for your role.")
            if st.button("🚪 Logout"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

if __name__ == "__main__":
    main()
