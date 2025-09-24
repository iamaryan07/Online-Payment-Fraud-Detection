import streamlit as st
import pandas as pd
from sqlalchemy import select, update, insert, desc, and_, text
from lib.auth import role_guard
from lib.db import get_engine, users, transactions, cases, settings, audit_logs, tickets
from datetime import datetime, timedelta
from lib.ml import AdvancedFraudModel  # ADD THIS LINE
import json
import random
import hashlib

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_payment_password_column_exists():
    """Check if payment_password column exists in users table"""
    try:
        eng = get_engine()
        with eng.begin() as conn:
            # Try to select the column - if it doesn't exist, this will fail
            conn.execute(text("SELECT payment_password FROM users LIMIT 1"))
            return True
    except Exception:
        return False

def create_payment_password_column():
    """Create payment_password column if it doesn't exist"""
    try:
        eng = get_engine()
        with eng.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN payment_password VARCHAR(64)"))
            return True
    except Exception as e:
        st.error(f"Failed to create payment_password column: {str(e)}")
        return False

def get_user_payment_password(user_id):
    """Get user payment password safely"""
    try:
        eng = get_engine()
        with eng.begin() as conn:
            if check_payment_password_column_exists():
                result = conn.execute(text("SELECT payment_password FROM users WHERE id = :user_id"), {"user_id": user_id}).fetchone()
                return result[0] if result else None
            else:
                return None
    except Exception:
        return None

def set_user_payment_password(user_id, password_hash):
    """Set user payment password safely"""
    try:
        eng = get_engine()
        with eng.begin() as conn:
            if check_payment_password_column_exists():
                conn.execute(text("UPDATE users SET payment_password = :password WHERE id = :user_id"), 
                           {"password": password_hash, "user_id": user_id})
                return True
            else:
                # Try to create column and then set password
                if create_payment_password_column():
                    conn.execute(text("UPDATE users SET payment_password = :password WHERE id = :user_id"), 
                               {"password": password_hash, "user_id": user_id})
                    return True
                return False
    except Exception as e:
        st.error(f"Failed to set payment password: {str(e)}")
        return False

def verify_payment_password(user_id, entered_password):
    """Verify the payment password against stored hash"""
    try:
        stored_password = get_user_payment_password(user_id)
        if stored_password:
            return hash_password(entered_password) == stored_password
        return False
    except Exception:
        return False

def generate_realistic_device_data():
    """Generate realistic device data for fraud detection analysis - HIDDEN FROM USER"""
    browsers = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/91.0.4472.124",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15"
    ]
    
    return {
        "user_agent": random.choice(browsers),
        "ip": f"192.168.{random.randint(0,255)}.{random.randint(1,254)}",
        "screen_resolution": f"{random.choice(['1920x1080', '1366x768', '1440x900', '1280x720'])}",
        "timezone": random.choice(["America/New_York", "America/Los_Angeles", "Europe/London"]),
        "language": "en-US"
    }

def calculate_fraud_risk_score(amount, sender_id, recipient_id, location, device_data, failed_attempts=0, test_scenario="Normal Transaction"):
    """Enhanced fraud detection with AUTOMATIC test scenario handling - AUTOMATIC SELECTION BASED ON AMOUNT"""
    risk_score = 0.0
    risk_factors = []
    
    # Get system configuration thresholds
    eng = get_engine()
    with eng.begin() as conn:
        sys_cfg_row = conn.execute(select(settings).where(settings.c.key == "system")).fetchone()
        sys_cfg = sys_cfg_row.value if sys_cfg_row else {}
    
    # AUTOMATIC TEST SCENARIO APPLICATION - BASED ON AMOUNT THRESHOLD
    if test_scenario == "High Amount Test":
        # Simulate high amount test scenario - add additional risk
        risk_score += 0.25
        risk_factors.append("High amount test scenario - Enhanced security protocols active")
    # "Normal Transaction" requires no additional modifications
    
    # Amount-based risk factors
    tx_limit = sys_cfg.get("tx_limit_amount", 5000.0)
    if amount > tx_limit:
        risk_score += 0.35
        risk_factors.append(f"Large transaction amount exceeds ${tx_limit:.0f} limit")
    elif amount > 1000:
        risk_score += 0.20
        risk_factors.append("Significant transaction amount over $1,000")
    
    # Pattern-based risk detection
    if amount % 100 == 0 and amount >= 500:
        risk_score += 0.25
        risk_factors.append("Round amount pattern detected (potential manual fraud)")
    
    # Micro-transaction detection (card testing)
    if amount < 1.0:
        risk_score += 0.40
        risk_factors.append("Micro-transaction pattern (potential card testing)")
    
    # Location-based risk assessment
    high_risk_locations = ["Unknown", "High-Risk-Geo", "Tor-Exit-Node", "VPN-Detected"]
    if location in high_risk_locations:
        risk_score += 0.30
        risk_factors.append(f"High-risk geographic location: {location}")
    
    # Device-based risk indicators
    device_string = device_data.get("user_agent", "").lower()
    suspicious_indicators = ["bot", "headless", "automation", "emulator", "selenium", "phantom"]
    detected_indicators = [indicator for indicator in suspicious_indicators if indicator in device_string]
    
    if detected_indicators:
        risk_score += 0.30
        risk_factors.append(f"Suspicious device indicators: {', '.join(detected_indicators)}")
    
    # Failed attempts penalty
    if failed_attempts > 0:
        risk_score += min(0.20, failed_attempts * 0.05)
        risk_factors.append(f"Multiple authentication attempts: {failed_attempts}")
    
    # Velocity-based risk (transaction frequency analysis)
    with eng.begin() as conn:
        recent_txs = conn.execute(
            select(transactions.c.id, transactions.c.amount, transactions.c.created_at)
            .where(
                transactions.c.sender_id == sender_id,
                transactions.c.created_at >= (datetime.now() - timedelta(hours=24))
            )
        ).fetchall()
        
        if len(recent_txs) > 5:
            risk_score += 0.25
            risk_factors.append(f"High transaction velocity: {len(recent_txs)} transactions in 24 hours")
        
        # Amount velocity check
        total_24h = sum(tx.amount for tx in recent_txs) + amount
        if total_24h > 10000:
            risk_score += 0.20
            risk_factors.append(f"High amount velocity: ${total_24h:.2f} in 24 hours")
    
    # User behavior analysis
    with eng.begin() as conn:
        user_history = conn.execute(
            select(transactions.c.amount, transactions.c.risk_score)
            .where(transactions.c.sender_id == sender_id)
            .limit(10)
        ).fetchall()
        
        if user_history:
            avg_amount = sum(tx.amount for tx in user_history) / len(user_history)
            if amount > avg_amount * 3:
                risk_score += 0.15
                risk_factors.append("Transaction amount significantly higher than user's typical pattern")
        
        # New user risk
        user_info = conn.execute(select(users.c.created_at).where(users.c.id == sender_id)).fetchone()
        if user_info:
            account_age = (datetime.now() - user_info.created_at).days
            if account_age < 7:
                risk_score += 0.20
                risk_factors.append("New account (less than 7 days old)")
            elif account_age < 30:
                risk_score += 0.10
                risk_factors.append("Recently created account (less than 30 days)")
    
    # Time-based risk factors
    current_hour = datetime.now().hour
    if current_hour < 6 or current_hour > 23:
        risk_score += 0.15
        risk_factors.append("Transaction during unusual hours (night/early morning)")
    
    # Weekend transaction risk
    if datetime.now().weekday() >= 5:  # Saturday = 5, Sunday = 6
        risk_score += 0.05
        risk_factors.append("Weekend transaction pattern")
    
    # Cap risk score at 1.0
    risk_score = min(1.0, risk_score)
    
    return risk_score, risk_factors

def process_payment(sender_id, recipient_id, amount, description, device_data, location, failed_attempts, test_scenario="Normal Transaction"):
    """Enhanced payment processing with REAL ML model integration - FULLY FIXED VERSION"""
    try:
        eng = get_engine()
        
        # Initialize ML model
        fraud_model = AdvancedFraudModel()
        
        with eng.begin() as conn:
            # Get sender and recipient info
            sender = conn.execute(select(users).where(users.c.id == sender_id)).fetchone()
            recipient = conn.execute(select(users).where(users.c.id == recipient_id)).fetchone()
            
            if not sender or not recipient:
                return None, "Error: User not found", 0.0, [], "Unknown"
            
            # Ensure balance is a number
            sender_balance = float(sender.balance) if sender.balance else 0.0
            
            if sender_balance < amount:
                return None, "Insufficient Balance", 0.0, [], "Unknown"
            
            # Prepare transaction data for ML model - FIXED DATA TYPES
            tx_data = {
                "amount": float(amount),
                "hour": int(datetime.now().hour),
                "failed_attempts": int(failed_attempts) if failed_attempts else 0,
                "location": str(location),
                "device": str(device_data.get("user_agent", "")),
                "sender_balance": float(sender_balance),
                "recipient_new": True,
            }
            
            # Get ML prediction - ENSURE FLOAT RETURN
            ml_fraud_probability = float(fraud_model.predict_proba(tx_data))
            
            # Get rule-based risk score - HANDLE TUPLE RETURN CORRECTLY
            rule_risk_result = calculate_fraud_risk_score(amount, sender_id, recipient_id, location, device_data, failed_attempts, test_scenario)
            if isinstance(rule_risk_result, tuple):
                rule_risk_score = float(rule_risk_result[0])  # Get risk score from tuple
                existing_risk_factors = rule_risk_result[1] if len(rule_risk_result) > 1 else []
            else:
                rule_risk_score = float(rule_risk_result)
                existing_risk_factors = []
            
            # Hybrid scoring: 70% ML + 30% rules - SAFE CALCULATION
            final_risk_score = (0.7 * ml_fraud_probability) + (0.3 * rule_risk_score)
            final_risk_score = float(final_risk_score)  # Ensure it's a float
            
            # Get risk factors - COMBINE ML AND RULE FACTORS
            risk_factors = list(existing_risk_factors) if existing_risk_factors else []
            
            if amount > 1000:
                risk_factors.append(f"Large transaction amount: ${amount:,.2f}")
            if location in ["Unknown", "High-Risk-Geo"]:
                risk_factors.append(f"High-risk location: {location}")
            if ml_fraud_probability > 0.5:
                risk_factors.append(f"ML model flagged: {ml_fraud_probability:.1%} fraud probability")
            
            # Determine payment status based on final score
            if final_risk_score >= 0.7:
                status = "Pending Approval"
                process_now = False
            elif final_risk_score >= 0.4:
                status = "Under Review"
                process_now = True
            else:
                status = "Success"
                process_now = True
            
            # Process payment based on risk assessment
            if process_now:
                new_sender_balance = sender_balance - amount
                new_recipient_balance = float(recipient.balance) + amount
                conn.execute(update(users).where(users.c.id == sender_id).values(balance=new_sender_balance))
                conn.execute(update(users).where(users.c.id == recipient_id).values(balance=new_recipient_balance))
            
            # Create transaction details
            now = datetime.now()
            transaction_details = {
                "risk_factors": risk_factors,
                "device_info": device_data,
                "processed": process_now,
                "test_scenario": test_scenario,
                "ml_probability": float(ml_fraud_probability),
                "rule_risk_score": float(rule_risk_score),
                "final_risk_score": float(final_risk_score),
                "fraud_indicators": {
                    "high_amount": amount > 5000.0,
                    "unusual_location": location in ["Unknown", "High-Risk-Geo"],
                    "suspicious_device": any(word in device_data.get("user_agent", "").lower() for word in ["emulator", "bot", "headless"]),
                    "round_amount": amount % 100 == 0 and amount >= 500,
                    "unusual_time": now.hour < 6 or now.hour > 23
                }
            }
            
            # Insert transaction
            result = conn.execute(insert(transactions).values(
                sender_id=sender_id,
                recipient_id=recipient_id,
                transaction_type="payment",
                amount=amount,
                description=description,
                ip=device_data.get("ip", "192.168.1.1"),
                device=device_data.get("user_agent", "Unknown"),
                location=location,
                status=status,
                risk_score=final_risk_score,
                details=json.dumps(transaction_details),
                created_at=now
            ))
            
            tx_id = result.inserted_primary_key[0]
            
            # Create investigation case for high-risk transactions
            if status in ["Under Review", "Pending Approval"]:
                priority = "High" if status == "Pending Approval" else "Medium"
                conn.execute(insert(cases).values(
                    transaction_id=tx_id,
                    assigned_to=None,
                    status="Assigned",
                    finding="",
                    report="",
                    priority=priority,
                    created_at=now
                ))
            
            # Enhanced audit logging
            audit_details = f"Payment processing: ${amount:.2f} from user {sender_id} to user {recipient_id} - Status: {status} - ML Risk: {ml_fraud_probability:.3f} - Final Risk: {final_risk_score:.3f} - Test Scenario: {test_scenario} - Factors: {len(risk_factors)}"
            conn.execute(insert(audit_logs).values(
                actor_user_id=sender_id,
                action="process_payment",
                entity_type="transaction",
                entity_id=tx_id,
                details=audit_details,
                created_at=now
            ))
            
            # Return recipient name for display
            recipient_name = recipient.name if recipient.name else "Unknown Recipient"
            
            return tx_id, status, final_risk_score, risk_factors, recipient_name
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Payment processing error: {str(e)}")
        st.error(f"Debug info: {error_details}")
        return None, f"Error: {str(e)}", 0.0, [], "Unknown"



def get_current_user():
    """Get fresh user data with current balance"""
    eng = get_engine()
    with eng.begin() as conn:
        return conn.execute(select(users).where(users.c.id == st.session_state["user_id"])).fetchone()

def render_overview():
    """Enhanced Dashboard Overview with comprehensive account analytics"""
    st.header("📊 Account Overview & Analytics")
    
    user = get_current_user()
    eng = get_engine()
    
    with eng.begin() as conn:
        # Comprehensive transaction analytics
        all_sent_transactions = conn.execute(
            select(transactions.c.amount, transactions.c.status, transactions.c.risk_score, transactions.c.created_at)
            .where(transactions.c.sender_id == user.id)
        ).fetchall()
        
        all_received_transactions = conn.execute(
            select(transactions.c.amount, transactions.c.status, transactions.c.created_at)
            .where(and_(
                transactions.c.recipient_id == user.id,
                transactions.c.status == "Success"  # Only show successful incoming payments
            ))
        ).fetchall()
        
        # Security and risk analytics
        flagged_transactions = conn.execute(
            select(transactions.c.id, transactions.c.risk_score, transactions.c.status)
            .where(and_(
                transactions.c.sender_id == user.id,
                transactions.c.status.in_(["Under Review", "Pending Approval", "Rejected"])
            ))
        ).fetchall()
        
        # Recent activity analysis
        recent_activity = conn.execute(
            select(transactions.c.amount, transactions.c.status, transactions.c.created_at)
            .where(transactions.c.sender_id == user.id)
            .order_by(desc(transactions.c.created_at))
            .limit(7)
        ).fetchall()
    
    # Enhanced key metrics display
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Current Balance", f"${user.balance:,.2f}")
    
    with col2:
        sent_count = len(all_sent_transactions)
        successful_sent = len([tx for tx in all_sent_transactions if tx.status == "Success"])
        st.metric("📤 Transactions Sent", sent_count, f"{successful_sent} successful")
    
    with col3:
        received_count = len(all_received_transactions)
        total_received = sum(tx.amount for tx in all_received_transactions)
        st.metric("📥 Payments Received", received_count, f"${total_received:,.2f}")
    
    with col4:
        if flagged_transactions:
            risk_level = "Enhanced"
        else:
            risk_level = "Standard Protection"
        st.metric("🔐 Security Status", risk_level, f"{len(flagged_transactions)} monitored")
    
    st.markdown("---")
    
    # Enhanced account information and analytics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👤 Account Information")
        st.write(f"**Full Name:** {user.name or 'Not Set'}")
        st.write(f"**Email Address:** {user.email}")
        st.write(f"**Phone Number:** {user.phone or 'Not Set'}")
        st.write(f"**Account Status:** {user.status.title()}")
        # st.write(f"**KYC Verification:** {user.kyc_status.replace('_', ' ').title()}")
        st.write(f"**Member Since:** {user.created_at.strftime('%B %d, %Y')}")
        
        # Account security indicators - USER FRIENDLY
        if flagged_transactions:
            st.info(f"🔐 Enhanced security monitoring active for {len(flagged_transactions)} transactions")
        else:
            st.success("✅ All transactions processed normally")
    
    with col2:
        st.subheader("📈 Transaction Analytics")
        
        if all_sent_transactions:
            # Transaction success rate
            successful_tx = len([tx for tx in all_sent_transactions if tx.status == "Success"])
            success_rate = (successful_tx / len(all_sent_transactions)) * 100
            st.write(f"**✅ Transaction Success Rate:** {success_rate:.1f}%")
            
            # Average transaction amount
            avg_amount = sum(tx.amount for tx in all_sent_transactions) / len(all_sent_transactions)
            st.write(f"**💰 Average Transaction:** ${avg_amount:.2f}")
            
            # Security status - USER FRIENDLY
            if flagged_transactions:
                st.write(f"**🔐 Security Status:** Enhanced Monitoring Active")
            else:
                st.write(f"**🔐 Security Status:** Standard Protection")
            
            # Monthly transaction volume
            monthly_total = sum(tx.amount for tx in all_sent_transactions 
                              if tx.created_at.month == datetime.now().month)
            st.write(f"**📊 This Month's Volume:** ${monthly_total:,.2f}")
            
            # Account activity level
            if len(recent_activity) >= 5:
                activity_level = "High"
            elif len(recent_activity) >= 2:
                activity_level = "Medium"
            else:
                activity_level = "Low"
            st.write(f"**📱 Account Activity:** {activity_level}")
        else:
            st.info("📭 No transaction history available yet")
    
    # Recent activity timeline
    if recent_activity:
        st.subheader("🕐 Recent Account Activity")
        for activity in recent_activity[:5]:
            status_emoji = {
                "Success": "✅",
                "Under Review": "🔍", 
                "Pending Approval": "⏳",
                "Rejected": "❌"
            }.get(activity.status, "📋")
            
            time_ago = (datetime.now() - activity.created_at).days
            time_display = f"{time_ago} days ago" if time_ago > 0 else "Today"
            
            st.write(f"{status_emoji} ${activity.amount:.2f} payment - {activity.status} - {time_display}")

def process_payment_results(tx_id, status, amount, recipient_name, test_scenario, description):
    """Handle payment results display - SEPARATED FUNCTION TO AVOID CODE DUPLICATION"""
    
    # ENHANCED USER-FRIENDLY STATUS MESSAGES WITH PERSONALIZED INFO
    if status == "Success":
        st.success("✅ **Payment Processed Successfully!**")
        st.success(f"💰 **${amount:,.2f} transferred successfully to {recipient_name}**")
        st.info("📧 **Both parties have been notified of the completed payment**")
        # st.balloons()
        
    elif status == "Under Review":
        st.success("✅ **Payment Processed Successfully!**")
        st.info("📋 **Additional Security Monitoring:** Your payment has been processed and is under routine security monitoring for your protection.")
        st.success(f"💰 **${amount:,.2f} transferred successfully to {recipient_name}**")
        
    elif status == "Pending Approval":
        st.warning("⏳ **Payment Pending Security Approval**")
        st.info("🔐 **Enhanced Security Review:** Your payment is being reviewed by our security team to ensure account protection.")
        st.info("📧 **You will be notified once the security review is complete**")
        st.info(f"💰 **${amount:,.2f} pending to be sent to {recipient_name} - reviewed by team**")
        
    else:
        st.info(f"📋 **Payment Status:** {status}")
    
    # Enhanced transaction details
    with st.container():
        st.markdown("**📄 Transaction Confirmation**")
        
        details_col1, details_col2, details_col3 = st.columns(3)
        
        with details_col1:
            st.metric("🆔 Transaction ID", f"#{tx_id}")
            st.write(f"**👤 Recipient:** {recipient_name}")
        
        with details_col2:
            st.metric("💰 Amount Processed", f"${amount:,.2f}")
            st.write(f"**📝 Description:** {description}")
        
        with details_col3:
            st.metric("📅 Processing Time", datetime.now().strftime("%H:%M:%S"))
            st.write(f"**🧪 Test Scenario:** {test_scenario}")
        
        # Enhanced status explanation based on test scenario
        st.markdown("**📋 What Happens Next?**")
        
        if status == "Success":
            st.success(f"""
            **✅ Payment Completed Successfully ({test_scenario})**
            • ${amount:,.2f} has been immediately transferred to {recipient_name}
            • Both accounts have been updated with the new balances  
            • Email notifications have been sent to both parties
            • Transaction completed using {test_scenario.lower()} security protocols
            """)
            
        elif status == "Under Review":
            st.info(f"""
            **📋 Routine Security Review Process ({test_scenario})**
            • Your ${amount:,.2f} payment to {recipient_name} has been processed and funds transferred
            • Flagged for routine security review using {test_scenario.lower()} protocols
            • No action required from you - this is an automated process
            • Review typically completes within 24 hours
            • You'll receive an email notification when review is complete
            """)
            
        elif status == "Pending Approval":
            st.warning(f"""
            **🔐 Security Investigation Required ({test_scenario})**
            • ${amount:,.2f} payment to {recipient_name} has been blocked due to {test_scenario.lower()} security protocols
            • Funds remain secured in your account until investigation completes
            • Our security team will analyze the transaction within 2-4 hours
            • Enhanced security verification applied due to {test_scenario.lower()} classification
            • You'll receive email notification with the investigation result
            """)
    
    # Reset password attempts on successful processing
    if "payment_password_attempts" in st.session_state:
        st.session_state.payment_password_attempts = 0
    
    # Add a small delay and then rerun to refresh the page
    import time
    time.sleep(1)
    st.rerun()

def render_send_money():
    """Enhanced Send Money interface with FORM-BASED PASSWORD AUTHENTICATION - NO DIALOG AT ALL"""
    st.header("💸 Send Money - Secure Payment System")
    
    user = get_current_user()
    
    # Check if payment password functionality is available
    has_payment_password = False
    password_column_exists = check_payment_password_column_exists()
    
    if password_column_exists:
        user_password = get_user_payment_password(user.id)
        has_payment_password = user_password is not None
    
    # If payment password functionality is not available, show option to enable it
    if not password_column_exists:
        st.info("🔐 **Enhanced Security Available**")
        st.info("Payment password authentication can be enabled for additional security.")
        
        if st.button("🚀 Enable Payment Password Security", type="secondary"):
            if create_payment_password_column():
                st.success("✅ **Payment password feature enabled!**")
                st.info("Please go to Profile Settings to set your payment password.")
                st.rerun()
            else:
                st.error("❌ Failed to enable payment password feature. Please contact support.")
    
    elif not has_payment_password:
        st.warning("🔐 **Payment Password Recommended**")
        st.info("For enhanced security, we recommend setting a payment password.")
        st.info("💡 Go to **Profile Settings** → **Security Settings** to set your payment password, or continue without it.")
    
    # Enhanced balance check and user guidance
    if user.balance <= 0:
        st.error("❌ Insufficient Balance for Transactions")
        st.write("Your account balance is insufficient to send payments. Please contact an administrator to add funds to your account.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("💰 Current Balance", f"${user.balance:,.2f}")
        with col2:
            st.metric("💸 Available for Spending", "$0.00")
        
        # Enhanced balance request functionality
        with st.expander("📋 Request Account Funding from Administrator"):
            with st.form("enhanced_balance_request"):
                requested_amount = st.number_input("Requested Amount ($)", 
                                                 min_value=50.0, max_value=10000.0, value=500.0, step=50.0)
                business_purpose = st.selectbox("Purpose", [
                    "Business Operations", "Personal Use", "Investment Activity", 
                    "Emergency Funding", "Account Testing", "Other"
                ])
                detailed_reason = st.text_area("Detailed Justification", 
                                             placeholder="Please provide a detailed explanation for why you need additional account funding...", 
                                             height=100)
                urgency_level = st.selectbox("Urgency Level", ["Normal", "High Priority", "Urgent"])
                
                if st.form_submit_button("📤 Submit Funding Request", type="primary"):
                    if detailed_reason.strip():
                        # Create enhanced support ticket for funding request
                        eng = get_engine()
                        with eng.begin() as conn:
                            ticket_subject = f"Account Funding Request - ${requested_amount:,.2f} ({urgency_level})"
                            ticket_message = f"""
ACCOUNT FUNDING REQUEST

Requested Amount: ${requested_amount:,.2f}
Purpose: {business_purpose}
Urgency Level: {urgency_level}
Current Balance: ${user.balance:,.2f}

Detailed Justification:
{detailed_reason}

User Information:
- Name: {user.name}
- Email: {user.email}
- Account ID: {user.id}
- Member Since: {user.created_at.strftime('%Y-%m-%d')}
                            """
                            
                            conn.execute(insert(tickets).values(
                                user_id=user.id,
                                subject=ticket_subject,
                                message=ticket_message,
                                status="Open",
                                created_at=datetime.now()
                            ))
                        
                        st.success("✅ Funding request submitted successfully!")
                        st.info("📧 An administrator will review your request and add funds to your account if approved.")
                    else:
                        st.error("❌ Please provide a detailed justification for the funding request.")
        
        return
    
    # Get available recipients
    eng = get_engine()
    with eng.begin() as conn:
        recipients = conn.execute(
            select(users.c.id, users.c.name, users.c.email, users.c.created_at)
            .where(and_(
                users.c.role == "user",
                users.c.status == "approved",
                users.c.id != st.session_state["user_id"]
            ))
            .order_by(users.c.name)
        ).fetchall()
    
    if not recipients:
        st.warning("⚠️ No approved users available for payments at this time.")
        return
    
    st.subheader("💳 Secure Payment Processing")
    
    with st.container():
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("**Payment Details**")
            
            # Enhanced recipient selection with user information
            recipient_options = {}
            for recipient in recipients:
                member_duration = (datetime.now() - recipient.created_at).days
                recipient_display = f"{recipient.name} ({recipient.email}) - Member for {member_duration} days"
                recipient_options[recipient_display] = recipient.id
            
            selected_recipient_display = st.selectbox("👤 Payment Recipient", list(recipient_options.keys()))
            recipient_id = recipient_options[selected_recipient_display]
            
            # Enhanced amount input with smart defaults
            max_amount = float(user.balance)
            
            # Smart default amount based on user history
            with eng.begin() as conn:
                recent_amounts = conn.execute(
                    select(transactions.c.amount)
                    .where(and_(
                        transactions.c.sender_id == user.id,
                        transactions.c.status == "Success"
                    ))
                    .order_by(desc(transactions.c.created_at))
                    .limit(5)
                ).fetchall()
                
                if recent_amounts:
                    avg_recent = sum(tx.amount for tx in recent_amounts) / len(recent_amounts)
                    suggested_amount = min(avg_recent, max_amount, 1000.0)
                else:
                    suggested_amount = min(100.0, max_amount)
            
            amount = st.number_input("💰 Payment Amount ($)", 
                                   min_value=0.01, max_value=max_amount, 
                                   value=suggested_amount, step=0.01,
                                   help=f"Maximum available: ${max_amount:,.2f}")
            
            # Enhanced description options
            description_options = [
                "Payment for services", "Repayment of loan", "Gift payment", 
                "Business transaction", "Shared expense", "Purchase payment",
                "Rent payment", "Utility payment", "Other"
            ]
            description_type = st.selectbox("📝 Payment Category", description_options)
            
            if description_type == "Other":
                custom_description = st.text_input("Custom Description", 
                                                 placeholder="Enter payment description...")
                description = custom_description if custom_description else "Payment"
            else:
                description = description_type
            
            # Enhanced validation for large amounts - USER FRIENDLY ONLY
            if amount > 1000:
                st.info("💡 **Large Payment Notice:** Payments over $1,000 may require additional processing time for security verification.")
        
        with col2:
            st.markdown("**Transaction Summary**")
            
            # Real-time balance calculation
            st.metric("💰 Current Balance", f"${user.balance:,.2f}")
            
            remaining_balance = user.balance - amount
            st.metric("📊 Balance After Payment", f"${remaining_balance:,.2f}")
            
            # Transaction size analysis - USER FRIENDLY
            if amount > 0:
                percentage_of_balance = (amount / user.balance) * 100
                st.write(f"**Transaction Size:** {percentage_of_balance:.1f}% of balance")
                
                if percentage_of_balance > 50:
                    st.info("💡 **Large transaction relative to account balance**")
                elif percentage_of_balance > 80:
                    st.warning("⚠️ **Very large transaction - please verify recipient details**")
        
        # Enhanced validation and security checks
        if amount > user.balance:
            st.error(f"❌ Transaction amount exceeds available balance! Available: ${user.balance:,.2f}")
            return
        
        if amount <= 0:
            st.error("❌ Invalid amount! Payment amount must be greater than zero.")
            return
        
        st.markdown("---")
        
        # AUTOMATIC FRAUD DETECTION TESTING DROPDOWN - USER CANNOT CHANGE
        st.subheader("🛠️ Fraud Detection Testing")
        
        # AUTOMATIC SELECTION BASED ON AMOUNT THRESHOLD
        if amount >= 1000:
            # Automatically select "High Amount Test" for amounts $1000+
            selected_test_scenario = "High Amount Test"
            test_scenario_color = "#ffc107"  # Warning color
            test_description = f"💡 **Automatic Selection:** High Amount Test selected"
        else:
            # Automatically select "Normal Transaction" for amounts under $1000
            selected_test_scenario = "Normal Transaction"
            test_scenario_color = "#28a745"  # Success color
            test_description = f"💡 **Automatic Selection:** Normal Transaction selected"
        
        # Display DISABLED dropdown with automatic selection
        st.selectbox(
            "🔴 Security Test Scenario", 
            ["Normal Transaction", "High Amount Test"],
            index=0 if selected_test_scenario == "Normal Transaction" else 1,
            disabled=True,  # USER CANNOT CHANGE THIS
            help="Automatically selected. Users cannot modify this selection."
        )
        
        # Display automatic selection explanation
        st.markdown(f"""
        <div style='padding: 10px; border-left: 4px solid {test_scenario_color}; background-color: {test_scenario_color}22; border-radius: 5px; margin: 10px 0;'>
            <p style='margin: 0; color: {test_scenario_color}; font-weight: 600;'>{test_description}</p>
            <p style='margin: 5px 0 0 0; font-size: 0.9em; color: #666;'>This selection is automatic and cannot be changed by the user.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Enhanced testing mode information based on automatic selection
        if selected_test_scenario == "High Amount Test":
            st.warning("⚠️ **High Amount Test Active**")
        else:
            st.info("ℹ️ **Normal Transaction Mode**")
        
        st.markdown("---")
        
        # Get recipient name for display
        recipient_name = selected_recipient_display.split('(')[0].strip()
        
        # FORM-BASED PAYMENT PROCESSING - NO DIALOG AT ALL
        if has_payment_password:
            # Show password authentication section
            st.subheader("🔐 Payment Authentication Required")
            
            with st.form("payment_authentication_form"):
                st.markdown(f"""
                **Payment Confirmation**  
                **From:** {user.name}  
                **To:** {recipient_name}  
                **Amount:** ${amount:,.2f}  
                **Description:** {description}
                """)
                
                # Initialize session state for password attempts if not exists
                if "payment_password_attempts" not in st.session_state:
                    st.session_state.payment_password_attempts = 0
                
                # Check if user has exceeded maximum attempts
                if st.session_state.payment_password_attempts >= 3:
                    st.error("❌ **Maximum password attempts exceeded.**")
                    st.error("For security reasons, please refresh the page or try again later.")
                    
                    if st.form_submit_button("🔄 Reset and Try Again", type="secondary", use_container_width=True):
                        st.session_state.payment_password_attempts = 0
                        st.rerun()
                    return
                
                # Password input field
                payment_password = st.text_input(
                    "🔑 Enter Payment Password",
                    type="password",
                    placeholder="Enter your secure payment password...",
                    help="This is the password you set in Profile Settings for secure payments."
                )
                
                # Show remaining attempts if user has made failed attempts
                if st.session_state.payment_password_attempts > 0:
                    remaining_attempts = 3 - st.session_state.payment_password_attempts
                    st.warning(f"⚠️ **{remaining_attempts} attempt(s) remaining**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    auth_submit = st.form_submit_button("✅ Authenticate & Process Payment", type="primary", use_container_width=True)
                
                with col2:
                    cancel_submit = st.form_submit_button("❌ Cancel Payment", type="secondary", use_container_width=True)
                
                if cancel_submit:
                    st.session_state.payment_password_attempts = 0  # Reset attempts
                    st.info("❌ **Payment cancelled by user.**")
                    return
                
                if auth_submit:
                    if not payment_password.strip():
                        st.error("❌ Please enter your payment password.")
                        return
                    
                    # Verify password
                    if verify_payment_password(st.session_state["user_id"], payment_password):
                        st.session_state.payment_password_attempts = 0  # Reset attempts on success
                        
                        # Process payment immediately after successful authentication
                        device_data = generate_realistic_device_data()
                        location = "US"
                        failed_attempts = 0
                        
                        with st.spinner("🔄 Processing secure payment..."):
                            result = process_payment(
                                st.session_state["user_id"], recipient_id, amount, 
                                description, device_data, location, failed_attempts, selected_test_scenario
                            )
                            
                            if result[0] is not None:  # tx_id is not None
                                tx_id, status, risk_score, risk_factors, recipient_name_db = result
                                # Process payment results
                                process_payment_results(tx_id, status, amount, recipient_name_db, selected_test_scenario, description)
                                return
                            else:
                                st.error(f"❌ Payment processing failed: {result[1]}")
                                return
                    else:
                        st.session_state.payment_password_attempts += 1
                        remaining = 3 - st.session_state.payment_password_attempts
                        
                        if remaining > 0:
                            st.error(f"❌ **Incorrect password.** {remaining} attempt(s) remaining.")
                        else:
                            st.error("❌ **Maximum attempts exceeded.** Please refresh the page and try again.")
                        return
        else:
            # No password required - direct payment processing
            if st.button("🔐 Process Secure Payment", type="primary", use_container_width=True):
                # Generate device data and process payment
                device_data = generate_realistic_device_data()
                location = "US"
                failed_attempts = 0
                
                with st.spinner("🔄 Processing secure payment..."):
                    result = process_payment(
                        st.session_state["user_id"], recipient_id, amount, 
                        description, device_data, location, failed_attempts, selected_test_scenario
                    )
                    
                    if result[0] is not None:  # tx_id is not None
                        tx_id, status, risk_score, risk_factors, recipient_name_db = result
                        # Process payment results
                        process_payment_results(tx_id, status, amount, recipient_name_db, selected_test_scenario, description)
                    else:
                        st.error(f"❌ Payment processing failed: {result[1]}")

def render_transaction_history():
    """Enhanced Transaction History with comprehensive filtering and analysis"""
    st.header("📊 Transaction History & Account Activity")
    
    user = get_current_user()
    eng = get_engine()
    
    # Enhanced filtering controls with comprehensive options
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        tx_type = st.selectbox("Transaction Type", ["All", "Sent", "Received"])
    
    with col2:
        status_filter = st.selectbox("Status Filter", ["All", "Success", "Under Review", "Pending Approval", "Rejected"])
    
    with col3:
        time_period = st.selectbox("Time Period", ["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days"])
    
    with col4:
        limit_results = st.selectbox("Show Results", [25, 50, 100, 200])
    
    # Build dynamic query based on filters
    with eng.begin() as conn:
        base_query = select(
            transactions.c.id, transactions.c.sender_id, transactions.c.recipient_id,
            transactions.c.amount, transactions.c.status, transactions.c.description,
            transactions.c.created_at, transactions.c.details
        )
        
        # Apply transaction type filter
        if tx_type == "Sent":
            query = base_query.where(transactions.c.sender_id == user.id)
        elif tx_type == "Received":
            query = base_query.where(transactions.c.recipient_id == user.id)
        else:  # All
            query = base_query.where(
                (transactions.c.sender_id == user.id) | (transactions.c.recipient_id == user.id)
            )
        
        # Apply status filter
        if status_filter != "All":
            query = query.where(transactions.c.status == status_filter)
        
        # Apply time period filter
        if time_period != "All Time":
            days_back = {"Last 7 Days": 7, "Last 30 Days": 30, "Last 90 Days": 90}[time_period]
            cutoff_date = datetime.now() - timedelta(days=days_back)
            query = query.where(transactions.c.created_at >= cutoff_date)
        
        # Add ordering and limit
        query = query.order_by(desc(transactions.c.created_at)).limit(limit_results)
        
        user_transactions = conn.execute(query).fetchall()
    
    # Enhanced transaction summary analytics
    if user_transactions:
        sent_txs = [tx for tx in user_transactions if tx.sender_id == user.id]
        received_txs = [tx for tx in user_transactions if tx.recipient_id == user.id]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📤 Sent", len(sent_txs))
        with col2:
            st.metric("📥 Received", len(received_txs))
        with col3:
            sent_total = sum(tx.amount for tx in sent_txs)
            st.metric("💸 Total Sent", f"${sent_total:,.2f}")
        with col4:
            received_total = sum(tx.amount for tx in received_txs)
            st.metric("💰 Total Received", f"${received_total:,.2f}")
        
        st.markdown("---")
        
        # Enhanced transaction display with test scenario information
        for tx in user_transactions:
            is_sent = tx.sender_id == user.id
            
            # Get other party information
            with eng.begin() as conn:
                if is_sent:
                    other_party = conn.execute(
                        select(users.c.name, users.c.email)
                        .where(users.c.id == tx.recipient_id)
                    ).fetchone()
                    direction_icon = "📤"
                    direction_text = "Sent to"
                    amount_color = "#dc3545"  # Red for sent
                    amount_prefix = "-"
                else:
                    other_party = conn.execute(
                        select(users.c.name, users.c.email)
                        .where(users.c.id == tx.sender_id)
                    ).fetchone()
                    direction_icon = "📥"
                    direction_text = "Received from"
                    amount_color = "#28a745"  # Green for received
                    amount_prefix = "+"
            
            # Extract test scenario from transaction details
            test_scenario = "Unknown"
            if tx.details:
                try:
                    details_obj = json.loads(tx.details)
                    test_scenario = details_obj.get("test_scenario", "Normal Transaction")
                except:
                    test_scenario = "Normal Transaction"
            
            # Enhanced status display with user-friendly descriptions
            status_config = {
                "Success": {"icon": "✅", "color": "#28a745", "text": "Completed"},
                "Under Review": {"icon": "🔍", "color": "#17a2b8", "text": "Security Review"},
                "Pending Approval": {"icon": "⏳", "color": "#ffc107", "text": "Pending Approval"},
                "Rejected": {"icon": "❌", "color": "#dc3545", "text": "Rejected"}
            }
            
            status_info = status_config.get(tx.status, {"icon": "📋", "color": "#6c757d", "text": tx.status})
            
            # Enhanced transaction card display with test scenario
            with st.container():
                card_col1, card_col2, card_col3, card_col4 = st.columns([3, 2, 1.5, 1])
                
                with card_col1:
                    other_name = other_party.name if other_party else "Unknown User"
                    other_email = other_party.email if other_party else "N/A"
                    st.write(f"**{direction_icon} {direction_text}** {other_name}")
                    st.caption(f"📧 {other_email}")
                    if tx.description:
                        st.caption(f"📝 {tx.description}")
                    # Show test scenario for sent transactions
                    if is_sent:
                        scenario_color = "#ffc107" if test_scenario == "High Amount Test" else "#28a745"
                        st.caption(f"🧪 Test: {test_scenario}")
                
                with card_col2:
                    st.markdown(f"<span style='color: {amount_color}; font-weight: bold; font-size: 1.3em;'>{amount_prefix}${tx.amount:,.2f}</span>", 
                               unsafe_allow_html=True)
                    st.caption(f"ID: #{tx.id}")
                
                with card_col3:
                    st.markdown(f"<span style='color: {status_info['color']};'>{status_info['icon']} {status_info['text']}</span>", 
                               unsafe_allow_html=True)
                
                with card_col4:
                    st.write(tx.created_at.strftime("%m/%d/%Y"))
                    st.caption(tx.created_at.strftime("%I:%M %p"))
                
                # Enhanced status explanations for user guidance
                if tx.status == "Under Review":
                    st.info(f"📋 **Routine Review ({test_scenario}):** This transaction is under standard security monitoring. No action required.")
                elif tx.status == "Pending Approval":
                    st.warning(f"⏳ **Security Review ({test_scenario}):** This transaction is being reviewed by our security team. You'll be notified of the decision.")
                elif tx.status == "Rejected":
                    st.error(f"❌ **Transaction Rejected ({test_scenario}):** This transaction was rejected due to security concerns. Contact support if you believe this was an error.")
                
                st.markdown("---")
    else:
        st.info("📭 No transactions found matching the selected filters.")

def render_security_alerts():
    """Enhanced Security Alerts with comprehensive threat analysis - USER FRIENDLY INTERFACE"""
    st.header("🔐 Security Center & Account Protection")
    
    current_user = get_current_user()
    eng = get_engine()
    
    with eng.begin() as conn:
        # Comprehensive security analysis
        all_user_transactions = conn.execute(
            select(transactions)
            .where(transactions.c.sender_id == st.session_state["user_id"])
            .order_by(desc(transactions.c.created_at))
        ).fetchall()
        
        flagged_transactions = [tx for tx in all_user_transactions 
                               if tx.status in ["Under Review", "Pending Approval", "Rejected - Fraudulent"]]
        
        # Recent activity analysis
        recent_activity = conn.execute(
            select(audit_logs.c.action, audit_logs.c.created_at, audit_logs.c.details)
            .where(audit_logs.c.actor_user_id == st.session_state["user_id"])
            .order_by(desc(audit_logs.c.created_at))
            .limit(15)
        ).fetchall()
    
    # Enhanced security dashboard with user-friendly metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🛡️ Account Security Status")
        
        # User-friendly security level calculation
        if len(flagged_transactions) == 0:
            security_level = "Excellent"
            security_description = "No security concerns detected"
            security_color = "#28a745"
        elif len(flagged_transactions) <= 2:
            security_level = "Good" 
            security_description = "Minor security monitoring active"
            security_color = "#ffc107"
        else:
            security_level = "Enhanced Protection"
            security_description = "Additional security measures active"
            security_color = "#dc3545"
        
        st.markdown(f"""
        <div style='padding: 15px; border-left: 5px solid {security_color}; background-color: rgba(0,0,0,0.05);'>
            <h4 style='margin: 0; color: {security_color};'>{security_level}</h4>
            <p style='margin: 5px 0 0 0;'>{security_description}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write(f"**💰 Account Balance:** ${current_user.balance:,.2f}")
        st.write(f"**📋 Account Status:** {current_user.status.title()}")
        st.write(f"**📊 Total Transactions:** {len(all_user_transactions)}")
        st.write(f"**👀 Monitored Transactions:** {len(flagged_transactions)}")
    
    with col2:
        st.subheader("📱 Recent Account Activity")
        
        if recent_activity:
            for activity in recent_activity[:8]:
                action_display = activity.action.replace('_', ' ').title()
                
                # Enhanced activity icons based on action type
                if "payment" in activity.action.lower():
                    activity_icon = "💰"
                elif "login" in activity.action.lower():
                    activity_icon = "🔑"
                else:
                    activity_icon = "📋"
                
                time_ago = datetime.now() - activity.created_at
                if time_ago.days > 0:
                    time_str = f"{time_ago.days}d ago"
                elif time_ago.seconds > 3600:
                    time_str = f"{time_ago.seconds // 3600}h ago"
                else:
                    time_str = f"{time_ago.seconds // 60}m ago"
                
                st.write(f"{activity_icon} {action_display} - {time_str}")
        else:
            st.info("📭 No recent account activity recorded.")

def render_profile_settings():
    """Enhanced Profile Settings with comprehensive user management and SAFE PASSWORD SETTINGS"""
    st.header("⚙️ Profile Settings & Account Management")
    
    current_user = get_current_user()
    
    # Enhanced profile information update
    st.subheader("👤 Personal Information")
    
    with st.form("profile_update_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_name = st.text_input("Full Name", value=current_user.name or "")
            new_phone = st.text_input("Phone Number", value=current_user.phone or "")
        
        with col2:
            st.write(f"**📧 Email:** {current_user.email}")
            st.caption("Email cannot be changed for security reasons")
            st.write(f"**📅 Member Since:** {current_user.created_at.strftime('%B %d, %Y')}")
            st.write(f"**🆔 Account ID:** {current_user.id}")
        
        if st.form_submit_button("💾 Update Profile Information", type="primary"):
            eng = get_engine()
            with eng.begin() as conn:
                conn.execute(
                    update(users)
                    .where(users.c.id == st.session_state["user_id"])
                    .values(name=new_name, phone=new_phone)
                )
                
                # Enhanced audit logging
                conn.execute(insert(audit_logs).values(
                    actor_user_id=st.session_state["user_id"],
                    action="update_profile",
                    entity_type="user",
                    entity_id=st.session_state["user_id"],
                    details=f"Updated profile: name='{new_name}', phone='{new_phone}'",
                    created_at=datetime.now()
                ))
            
            st.success("✅ Profile updated successfully!")
            st.rerun()
    
    st.markdown("---")
    
    # SAFE: Payment Password Settings Section with error handling
    st.subheader("🔐 Security Settings")
    
    # Check if payment password functionality is available
    password_column_exists = check_payment_password_column_exists()
    
    if password_column_exists:
        # Check if user has a payment password
        user_password = get_user_payment_password(current_user.id)
        has_password = user_password is not None
        
        if has_password:
            st.success("✅ **Payment password is set and active**")
            st.info("🔒 Your payment password is required for all transactions to ensure security.")
            
            # Change password form
            with st.expander("🔄 Change Payment Password"):
                with st.form("change_password_form"):
                    current_password = st.text_input("Current Payment Password", type="password")
                    new_password = st.text_input("New Payment Password", type="password", 
                                               help="Must be at least 6 characters long")
                    confirm_password = st.text_input("Confirm New Password", type="password")
                    
                    if st.form_submit_button("🔄 Change Password", type="primary"):
                        if not current_password or not new_password or not confirm_password:
                            st.error("❌ Please fill in all password fields.")
                        elif not verify_payment_password(current_user.id, current_password):
                            st.error("❌ Current password is incorrect.")
                        elif len(new_password) < 6:
                            st.error("❌ New password must be at least 6 characters long.")
                        elif new_password != confirm_password:
                            st.error("❌ New password and confirmation do not match.")
                        else:
                            # Update password
                            hashed_password = hash_password(new_password)
                            if set_user_payment_password(current_user.id, hashed_password):
                                # Log password change
                                eng = get_engine()
                                with eng.begin() as conn:
                                    conn.execute(insert(audit_logs).values(
                                        actor_user_id=current_user.id,
                                        action="change_payment_password",
                                        entity_type="user",
                                        entity_id=current_user.id,
                                        details="Payment password changed successfully",
                                        created_at=datetime.now()
                                    ))
                                
                                st.success("✅ **Payment password changed successfully!**")
                                st.rerun()
                            else:
                                st.error("❌ Failed to update password. Please try again.")
        else:
            st.warning("⚠️ **No payment password set**")
            st.error("🔒 You must set a payment password to make transactions.")
            
            # Set password form
            with st.form("set_password_form"):
                st.markdown("**Set Your Payment Password**")
                new_password = st.text_input("Payment Password", type="password", 
                                           help="Must be at least 6 characters long")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                password_requirements = st.expander("📋 Password Requirements")
                with password_requirements:
                    st.write("""
                    **Your payment password should:**
                    - Be at least 6 characters long
                    - Be different from your login password
                    - Be something you can remember easily
                    - Not be shared with anyone
                    """)
                
                if st.form_submit_button("🔐 Set Payment Password", type="primary"):
                    if not new_password or not confirm_password:
                        st.error("❌ Please fill in both password fields.")
                    elif len(new_password) < 6:
                        st.error("❌ Password must be at least 6 characters long.")
                    elif new_password != confirm_password:
                        st.error("❌ Passwords do not match.")
                    else:
                        # Set password
                        hashed_password = hash_password(new_password)
                        if set_user_payment_password(current_user.id, hashed_password):
                            # Log password creation
                            eng = get_engine()
                            with eng.begin() as conn:
                                conn.execute(insert(audit_logs).values(
                                    actor_user_id=current_user.id,
                                    action="set_payment_password",
                                    entity_type="user",
                                    entity_id=current_user.id,
                                    details="Payment password set for the first time",
                                    created_at=datetime.now()
                                ))
                            
                            st.success("✅ **Payment password set successfully!**")
                            st.success("🎉 You can now make secure payments!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to set password. Please try again.")
    else:
        st.info("🔐 **Enhanced Security Available**")
        st.info("Payment password authentication can be enabled for additional security.")
        
        if st.button("🚀 Enable Payment Password Security", type="secondary"):
            if create_payment_password_column():
                st.success("✅ **Payment password feature enabled!**")
                st.info("You can now set your payment password below.")
                st.rerun()
            else:
                st.error("❌ Failed to enable payment password feature. Please contact support.")
    
    st.markdown("---")
    
    # Enhanced notification preferences
    st.subheader("📧 Notification Preferences")
    
    col1, col2 = st.columns(2)
    
    with col1:
        email_notifications = st.checkbox("📧 Email notifications for transactions", value=True)
        security_alerts = st.checkbox("🔐 Security alerts and warnings", value=True)
        
    with col2:
        sms_notifications = st.checkbox("📱 SMS notifications for large payments", value=False)
        monthly_summary = st.checkbox("📊 Monthly account summary", value=True)
    
    if st.button("💾 Save Notification Preferences"):
        # In a real application, save these preferences to database
        st.success("✅ Notification preferences saved successfully!")
    
    st.markdown("---")
    
    # Enhanced account information display
    st.subheader("📋 Account Information")
    
    info_col1, info_col2 = st.columns(2)
    
    with info_col1:
        st.write(f"**👤 User ID:** {current_user.id}")
        st.write(f"**📧 Email:** {current_user.email}")
        st.write(f"**📞 Phone:** {current_user.phone or 'Not provided'}")
        st.write(f"**📅 Account Created:** {current_user.created_at.strftime('%B %d, %Y')}")
    
    with info_col2:
        # Enhanced account status display with color coding
        account_status_color = {"approved": "#28a745", "pending": "#ffc107", "rejected": "#dc3545"}.get(current_user.status, "#6c757d")
        
        st.markdown(f"""
        <div style='padding: 15px; background: linear-gradient(90deg, {account_status_color}22, transparent); border-left: 5px solid {account_status_color}; margin-bottom: 20px; border-radius: 5px;'>
            <h4 style='margin: 0; color: {account_status_color};'>💰 ${current_user.balance:,.2f}</h4>
            <p style='margin: 5px 0 0 0;'>{current_user.email} | Status: {current_user.status.title()} | Account: {current_user.id}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write(f"**📋 Account Status:** {current_user.status.title()}")
        # st.write(f"**✅ KYC Status:** {current_user.kyc_status.replace('_', ' ').title()}")
        st.write(f"**🔐 Account Type:** Standard User")
        
        # Payment password status
        if password_column_exists:
            user_password = get_user_payment_password(current_user.id)
            has_password = user_password is not None
            if has_password:
                st.write(f"**🔒 Payment Security:** Password Protected ✅")
            else:
                st.write(f"**🔒 Payment Security:** Not Set ❌")
        else:
            st.write(f"**🔒 Payment Security:** Available on request")

def render_support_center():
    """Support Center with safe column handling"""
    st.header("🆘 Support Center")
    
    current_user = get_current_user()
    
    # Support ticket form
    st.subheader("📝 Create Support Ticket")
    
    with st.form("support_ticket_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            ticket_category = st.selectbox("Issue Category", [
                "Payment Issues", "Account Questions", "Security Concerns", 
                "Balance Inquiries", "Technical Problems", "General Inquiry"
            ])
            
        with col2:
            # Only show priority if column exists, otherwise use default
            priority_level = st.selectbox("Priority Level", ["Low", "Medium", "High", "Urgent"])
        
        ticket_subject = st.text_input("Ticket Subject", placeholder="Brief description of your issue...")
        ticket_description = st.text_area("Detailed Description", 
                                        placeholder="Please provide detailed information about your issue...",
                                        height=150)
        
        submitted = st.form_submit_button("📤 Submit Support Ticket", type="primary")
        
        if submitted and ticket_subject.strip() and ticket_description.strip():
            # Create support ticket with safe column insertion
            eng = get_engine()
            with eng.begin() as conn:
                # First, check if priority column exists
                try:
                    # Try to insert with priority
                    ticket_result = conn.execute(insert(tickets).values(
                        user_id=current_user.id,
                        subject=f"[{ticket_category}] {ticket_subject}",
                        message=ticket_description,
                        status="Open",
                        priority=priority_level,  # This might fail if column doesn't exist
                        created_at=datetime.now()
                    ))
                except Exception:
                    # Fallback: insert without priority column
                    ticket_result = conn.execute(insert(tickets).values(
                        user_id=current_user.id,
                        subject=f"[{ticket_category}] {ticket_subject}",
                        message=ticket_description,
                        status="Open",
                        created_at=datetime.now()
                    ))
                
                ticket_id = ticket_result.inserted_primary_key[0]
            
            st.success(f"✅ Support ticket #{ticket_id} created successfully!")
            st.info("📧 You will receive email updates on ticket progress.")
            st.rerun()
        elif submitted:
            st.error("❌ Please fill in both subject and description fields.")
    
    st.markdown("---")
    
    # Display existing tickets with safe column handling
    st.subheader("📋 My Support Tickets")
    
    eng = get_engine()
    with eng.begin() as conn:
        try:
            # Try to get tickets with priority column
            user_tickets = conn.execute(
                select(tickets.c.id, tickets.c.subject, tickets.c.status, tickets.c.priority, tickets.c.created_at)
                .where(tickets.c.user_id == current_user.id)
                .order_by(desc(tickets.c.created_at))
                .limit(10)
            ).fetchall()
            has_priority_column = True
        except Exception:
            # Fallback: get tickets without priority column
            user_tickets = conn.execute(
                select(tickets.c.id, tickets.c.subject, tickets.c.status, tickets.c.created_at)
                .where(tickets.c.user_id == current_user.id)
                .order_by(desc(tickets.c.created_at))
                .limit(10)
            ).fetchall()
            has_priority_column = False
    
    if user_tickets:
        for ticket in user_tickets:
            # Status color coding
            status_colors = {
                "Open": "#ffc107",
                "In Progress": "#17a2b8", 
                "Resolved": "#28a745",
                "Closed": "#6c757d"
            }
            
            status_color = status_colors.get(ticket.status, "#6c757d")
            
            # Priority handling (only if column exists)
            if has_priority_column:
                priority_icons = {
                    "Low": "🔵",
                    "Medium": "🟡",
                    "High": "🟠", 
                    "Urgent": "🔴"
                }
                priority_icon = priority_icons.get(getattr(ticket, 'priority', 'Medium'), "🟡")
                priority_text = getattr(ticket, 'priority', 'Medium')
            else:
                priority_icon = "📋"
                priority_text = "Normal"
            
            with st.container():
                if has_priority_column:
                    ticket_col1, ticket_col2, ticket_col3 = st.columns([3, 1, 1])
                else:
                    ticket_col1, ticket_col2 = st.columns([4, 1])
                
                with ticket_col1:
                    st.markdown(f"**🎫 #{ticket.id}** - {ticket.subject}")
                    st.caption(f"Created: {ticket.created_at.strftime('%B %d, %Y at %I:%M %p')}")
                
                with ticket_col2:
                    st.markdown(f"<span style='color: {status_color}; font-weight: bold;'>{ticket.status}</span>", 
                               unsafe_allow_html=True)
                
                if has_priority_column:
                    with ticket_col3:
                        st.write(f"{priority_icon} {priority_text}")
                
                st.markdown("---")
    else:
        st.info("📭 No support tickets found. Create your first ticket above if you need assistance.")


def run():
    """Main User Dashboard Function"""
    role_guard(["user"])
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.title("Customer Dashboard")
    
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, type="secondary"):
            st.rerun()
    
    # Enhanced tab navigation
    tabs = st.tabs([
        "📊 Overview", 
        "💸 Send Money", 
        "📋 Transaction History", 
        "🔐 Security Center", 
        "⚙️ Profile Settings", 
        "🆘 Support Center"
    ])
    
    # Tab content rendering
    with tabs[0]:
        render_overview()
    
    with tabs[1]:
        render_send_money()
    
    with tabs[2]:
        render_transaction_history()
    
    with tabs[3]:
        render_security_alerts()
    
    with tabs[4]:
        render_profile_settings()
    
    with tabs[5]:
        render_support_center()

if __name__ == "__main__":
    run()
