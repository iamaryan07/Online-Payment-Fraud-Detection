# lib/ui.py
import streamlit as st

def topbar_brand():
    st.markdown(
        """
        <style>
        .brand-bar {
            padding: 10px 16px;
            border-radius: 10px;
            background: linear-gradient(90deg,#0f172a,#1e293b);
            color: #e2e8f0;
            margin-bottom: 10px;
        }
        .brand-title { font-size: 20px; font-weight: 700; }
        .brand-sub { font-size: 13px; opacity: 0.8; }
        </style>
        <div class="brand-bar">
            <div class="brand-title">🔒 Online Payment Fraud Detection</div>
            <div class="brand-sub">Real-time flags, case workflow, and auditability</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def stat_card(title, value, icon="📊", color="#0ea5e9"):
    st.markdown(
        f"""
        <div style="border-radius:12px;padding:16px;background:#0b1220;border:1px solid #1f2a44;">
            <div style="font-size:12px;opacity:0.7;">{title}</div>
            <div style="font-size:24px;font-weight:700;color:{color}">{icon} {value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def show_credentials_info():
    """Display default credentials for easy access"""
    st.info("""
    🔑 **Quick Login Credentials:**
    
    **Admin:** admin@fraud-detect.local / admin123
    
    **Cyber Official:** cyber@fraud-detect.local / cyber123
    
    **User:** user@fraud-detect.local / user123
    """)
