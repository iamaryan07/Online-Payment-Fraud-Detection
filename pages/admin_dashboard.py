# pages/admin_dashboard.py - Complete enhanced admin interface - ALL NONE ERRORS FIXED
import streamlit as st
import pandas as pd
from sqlalchemy import select, update, insert, desc, and_
from lib.auth import role_guard
from lib.db import get_engine, users, transactions, cases, settings, audit_logs

def render_admin_overview():
    """Admin Overview Dashboard"""
    st.header("🎯 System Overview")
    
    eng = get_engine()
    with eng.begin() as conn:
        # Get system statistics
        total_users = conn.execute(select(users.c.id).where(users.c.role == "user")).fetchall()
        pending_users = conn.execute(select(users.c.id).where(users.c.status == "pending")).fetchall()
        total_transactions = conn.execute(select(transactions.c.id)).fetchall()
        flagged_transactions = conn.execute(select(transactions.c.id).where(transactions.c.status.in_(["Flagged", "Under Review"]))).fetchall()
        pending_approvals = conn.execute(select(transactions.c.id).where(transactions.c.status == "Pending Approval")).fetchall()
        open_cases = conn.execute(select(cases.c.id).where(cases.c.status.in_(["Assigned", "In Review"]))).fetchall()
        
        # System health metrics - FIXED: Handle None values
        total_balance = conn.execute(select(users.c.balance).where(users.c.role == "user")).fetchall()
        system_balance = sum(float(b.balance) if b.balance is not None else 0.0 for b in total_balance)
        
        # Today's transactions
        today_txs = conn.execute(
            select(transactions.c.id)
            .where(transactions.c.created_at >= pd.Timestamp.now().strftime('%Y-%m-%d'))
        ).fetchall()
    
    # Key Metrics - ENHANCED
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("👥 Total Users", len(total_users), f"{len(pending_users)} pending")
    with col2:
        st.metric("💳 Total Transactions", len(total_transactions), f"{len(today_txs)} today")
    with col3:
        st.metric("🚨 Flagged Transactions", len(flagged_transactions))
    with col4:
        st.metric("⏳ Pending Approvals", len(pending_approvals))
    with col5:
        st.metric("💰 System Balance", f"${system_balance:,.2f}")
    
    st.markdown("---")
    
    # System Health Dashboard
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 System Health")
        
        # Calculate health score
        health_score = 100 - (len(flagged_transactions) * 2) - (len(open_cases) * 3) - (len(pending_approvals) * 1)
        health_score = max(0, min(100, health_score))
        
        if health_score >= 90:
            st.success(f"🟢 Excellent ({health_score}%)")
        elif health_score >= 70:
            st.warning(f"🟡 Good ({health_score}%)")
        else:
            st.error(f"🔴 Needs Attention ({health_score}%)")
        
        # Risk thresholds info
        with eng.begin() as conn:
            cfg = conn.execute(select(settings).where(settings.c.key == "system")).fetchone()
            if cfg:
                st.info(f"""**Risk Thresholds:**  
                Flag: {cfg.value.get('flag_threshold', 0.4):.2f}  
                Block: {cfg.value.get('block_threshold', 0.7):.2f}""")
    
    with col2:
        st.subheader("📈 Recent Activity")
        with eng.begin() as conn:
            recent_logs = conn.execute(
                select(audit_logs.c.action, audit_logs.c.created_at, audit_logs.c.details)
                .order_by(desc(audit_logs.c.created_at))
                .limit(8)
            ).fetchall()
        
        for log in recent_logs:
            action_display = (log.action or "unknown_action").replace('_', ' ').title()
            # Parse details string to extract amount if present
            if log.details and isinstance(log.details, str):
                if '$' in log.details:
                    try:
                        parts = log.details.split('$')
                        if len(parts) > 1:
                            amount_part = parts[1].split(' ')[0]
                            action_display += f" (${amount_part})"
                    except:
                        pass
            st.write(f"• {action_display}")
    
    # Critical Alerts
    if len(pending_approvals) > 5 or len(flagged_transactions) > 10:
        st.markdown("---")
        st.subheader("🚨 Critical Alerts")
        
        if len(pending_approvals) > 5:
            st.error(f"🔴 {len(pending_approvals)} high-risk payments are blocked and awaiting cyber approval!")
        
        if len(flagged_transactions) > 10:
            st.warning(f"🟡 {len(flagged_transactions)} transactions are flagged and may need case assignment!")

def render_user_management():
    """Enhanced User Management Tab with Role-based Approval"""
    st.header("👥 User Management")
    
    eng = get_engine()
    
    # Pending Registrations - ENHANCED
    st.subheader("📋 Pending Registrations")
    
    with eng.begin() as conn:
        pending = conn.execute(
            select(users).where(users.c.status == "pending")
            .order_by(users.c.created_at)
        ).fetchall()
    
    if pending:
        # Group by role for better organization
        user_pending = [u for u in pending if u.role == "user"]
        cyber_pending = [u for u in pending if u.role == "cyber"]
        
        # Customer Registrations
        if user_pending:
            st.markdown("#### 👤 Customer Registrations")
            for user in user_pending:
                render_pending_user(user, "Customer", "👤", 2000.0)  # Default $2000 for customers
        
        # Cyber Official Registrations
        if cyber_pending:
            st.markdown("#### 🕵️ Cyber Security Official Registrations")
            for user in cyber_pending:
                render_pending_user(user, "Cyber Official", "🕵️", 0.0)  # No balance for cyber officials
        
        if not user_pending and not cyber_pending:
            st.success("✅ No pending registrations")
    
    else:
        st.success("✅ No pending registrations")
    
    # Rest of your existing user management code...

def render_pending_user(user, role_display, role_icon, default_balance):
    """Helper function to render pending user approval interface"""
    with st.container():
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.write(f"**{user.name or 'No Name'}**")
            st.write(f"📧 {user.email or 'No Email'}")
            st.write(f"📱 {user.phone or 'No Phone'}")
        
        with col2:
            st.write(f"**Role:** {role_icon} {role_display}")
            st.write(f"**Registered:** {user.created_at.strftime('%Y-%m-%d') if user.created_at else 'Unknown'}")
            st.write(f"**Default Balance:** ${default_balance:,.2f}" if default_balance > 0 else "**Balance:** Not applicable")
        
        with col3:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅", key=f"approve_{user.id}", help="Approve"):
                    eng = get_engine()
                    with eng.begin() as conn:
                        conn.execute(update(users).where(users.c.id == user.id).values(
                            status="approved", 
                            balance=default_balance
                        ))
                        conn.execute(insert(audit_logs).values(
                            actor_user_id=st.session_state["user_id"], 
                            action="approve_user", 
                            entity_type="user", 
                            entity_id=user.id, 
                            details=f"Approved {role_display.lower()}: {user.email} with balance ${default_balance}"
                        ))
                    st.success(f"✅ {role_display} {user.email} approved!")
                    st.rerun()
            
            with col_b:
                if st.button("❌", key=f"reject_{user.id}", help="Reject"):
                    eng = get_engine()
                    with eng.begin() as conn:
                        conn.execute(update(users).where(users.c.id == user.id).values(status="rejected"))
                        conn.execute(insert(audit_logs).values(
                            actor_user_id=st.session_state["user_id"], 
                            action="reject_user", 
                            entity_type="user", 
                            entity_id=user.id, 
                            details=f"Rejected {role_display.lower()} registration: {user.email}"
                        ))
                    st.warning(f"❌ {role_display} {user.email} rejected!")
                    st.rerun()
        
        st.markdown("---")


def render_balance_management():
    """Balance Management Tab"""
    st.header("💰 Balance Management")
    
    eng = get_engine()
    with eng.begin() as conn:
        user_accounts = conn.execute(
            select(users).where(users.c.role == "user")
            .order_by(users.c.name)
        ).fetchall()
    
    if not user_accounts:
        st.warning("No user accounts found.")
        return
    
    # Balance Adjustment
    st.subheader("⚖️ Adjust User Balance")
    
    col1, col2 = st.columns(2)
    
    with col1:
        selected_user_id = st.selectbox(
            "Select User", 
            [u.id for u in user_accounts],
            format_func=lambda x: next(f"{u.name or 'Unknown'} ({u.email}) - ${float(u.balance or 0):,.2f}" for u in user_accounts if u.id == x)
        )
        
        selected_user = next(u for u in user_accounts if u.id == selected_user_id)
        
        adjustment_type = st.selectbox("Adjustment Type", ["Add Funds", "Deduct Funds", "Set Balance"])
        amount = st.number_input("Amount ($)", min_value=0.01, value=100.0, step=0.01)
        reason = st.text_input("Reason", value="Admin adjustment")
    
    with col2:
        st.subheader("👤 Selected User")
        st.write(f"**Name:** {selected_user.name or 'Unknown'}")
        st.write(f"**Email:** {selected_user.email or 'No Email'}")
        current_balance = float(selected_user.balance or 0)
        st.write(f"**Current Balance:** ${current_balance:,.2f}")
        
        # Calculate new balance - FIXED: Handle None balance
        if adjustment_type == "Add Funds":
            new_balance = current_balance + amount
        elif adjustment_type == "Deduct Funds":
            new_balance = max(0, current_balance - amount)
        else:
            new_balance = amount
        
        st.write(f"**New Balance:** ${new_balance:,.2f}")
        
        # Show recent balance history
        with eng.begin() as conn:
            recent_adjustments = conn.execute(
                select(transactions)
                .where(and_(
                    transactions.c.transaction_type == "admin_adjustment",
                    transactions.c.sender_id == selected_user_id
                ))
                .order_by(desc(transactions.c.created_at))
                .limit(3)
            ).fetchall()
        
        if recent_adjustments:
            st.write("**Recent Adjustments:**")
            for adj in recent_adjustments:
                st.write(f"• {adj.description or 'No description'} - {adj.created_at.strftime('%m/%d') if adj.created_at else 'Unknown date'}")
    
    if st.button("💾 Apply Adjustment", type="primary"):
        with eng.begin() as conn:
            conn.execute(update(users).where(users.c.id == selected_user_id).values(balance=new_balance))
            
            # Log adjustment as transaction
            conn.execute(transactions.insert().values(
                sender_id=st.session_state["user_id"] if adjustment_type == "Add Funds" else selected_user_id,
                recipient_id=selected_user_id if adjustment_type == "Add Funds" else None,
                transaction_type="admin_adjustment",
                amount=amount,
                description=f"{adjustment_type}: {reason}",
                status="Success",
                details={"admin_id": st.session_state["user_id"], "type": adjustment_type, "reason": reason}
            ))
            
            conn.execute(insert(audit_logs).values(
                actor_user_id=st.session_state["user_id"],
                action="balance_adjustment",
                entity_type="user",
                entity_id=selected_user_id,
                details=f"Balance {adjustment_type}: ${amount} for {selected_user.email} - New balance: ${new_balance} - Reason: {reason}"
            ))
        
        st.success(f"✅ Balance updated! New balance: ${new_balance:,.2f}")
        st.rerun()
    
    st.markdown("---")
    
    # Balance Overview
    st.subheader("📊 Balance Overview")
    
    balance_data = []
    total_system_balance = 0
    
    for user in user_accounts:
        user_balance = float(user.balance or 0)  # FIXED: Handle None balance
        balance_data.append({
            "User": user.name or "No Name",
            "Email": user.email or "No Email",
            "Balance": user_balance,
            "Status": str(user.status or "Unknown").title()  # FIXED: Handle None status
        })
        total_system_balance += user_balance  # FIXED: Now safe from None
    
    balance_df = pd.DataFrame(balance_data)
    st.dataframe(balance_df, use_container_width=True)
    
    # System balance metrics - FIXED: Handle None values
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💰 Total System Balance", f"${total_system_balance:,.2f}")
    with col2:
        avg_balance = total_system_balance / len(user_accounts) if user_accounts else 0
        st.metric("📊 Average Balance", f"${avg_balance:,.2f}")
    with col3:
        max_balance = max(float(user.balance or 0) for user in user_accounts) if user_accounts else 0  # FIXED: Handle None
        st.metric("📈 Highest Balance", f"${max_balance:,.2f}")

def render_transaction_monitoring():
    """Transaction Monitoring Tab with dynamic priority colors"""
    st.header("📊 Transaction Monitoring")
    
    eng = get_engine()
    
    # Get system configuration for thresholds
    with eng.begin() as conn:
        sys_cfg_row = conn.execute(select(settings).where(settings.c.key == "system")).fetchone()
        sys_cfg = sys_cfg_row.value if sys_cfg_row else {}
        
        # Get admin-configured thresholds
        flag_threshold = sys_cfg.get("flag_threshold", 0.4)
        block_threshold = sys_cfg.get("block_threshold", 0.7)
    
    # Enhanced filter controls
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_filter = st.selectbox("Filter by Status", [
            "All", "Success", "Flagged", "Under Review", "Blocked", "Pending Approval", "Rejected"
        ])
    with col2:
        tx_type_filter = st.selectbox("Transaction Type", [
            "All", "payment", "admin_adjustment"
        ])
    with col3:
        risk_filter = st.selectbox("Risk Level", [
            "All", 
            f"Low (< {flag_threshold})", 
            f"Medium ({flag_threshold} - {block_threshold})", 
            f"High (≥ {block_threshold})"
        ])
    with col4:
        limit = st.selectbox("Records", [50, 100, 200, 500])
    
    # Get transactions with filters
    with eng.begin() as conn:
        query = select(transactions).order_by(desc(transactions.c.created_at)).limit(limit)
        
        if status_filter != "All":
            query = query.where(transactions.c.status == status_filter)
        if tx_type_filter != "All":
            query = query.where(transactions.c.transaction_type == tx_type_filter)
        
        txs = conn.execute(query).fetchall()
    
    # Apply dynamic risk filter based on admin thresholds
    if risk_filter != "All":
        if f"Low (< {flag_threshold})" in risk_filter:
            txs = [tx for tx in txs if (tx.risk_score or 0) < flag_threshold]
        elif f"Medium ({flag_threshold} - {block_threshold})" in risk_filter:
            txs = [tx for tx in txs if flag_threshold <= (tx.risk_score or 0) < block_threshold]
        elif f"High (≥ {block_threshold})" in risk_filter:
            txs = [tx for tx in txs if (tx.risk_score or 0) >= block_threshold]
    
    if txs:
        # Transaction statistics - FIXED: Handle None values
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_amount = sum(tx.amount or 0 for tx in txs)
            st.metric("💰 Total Amount", f"${total_amount:,.2f}")
        with col2:
            valid_risk_scores = [tx.risk_score for tx in txs if tx.risk_score is not None]
            avg_risk = sum(valid_risk_scores) / len(valid_risk_scores) if valid_risk_scores else 0
            st.metric("⚠️ Avg Risk Score", f"{avg_risk:.3f}")
        with col3:
            high_risk_count = len([tx for tx in txs if (tx.risk_score or 0) >= block_threshold])
            st.metric("🔴 High Risk Count", high_risk_count)
        with col4:
            success_count = len([tx for tx in txs if tx.status == "Success"])
            success_rate = success_count / len(txs) * 100 if txs else 0
            st.metric("✅ Success Rate", f"{success_rate:.1f}%")
        
        st.markdown("---")
        
        # Enhanced transaction display with dynamic priority colors
        for tx in txs:
            # Determine priority based on ADMIN-SET thresholds - FIXED: Handle None risk_score
            risk_score = tx.risk_score or 0
            
            if risk_score >= block_threshold:
                priority_icon = "🔴"
                priority_text = "High Risk"
                priority_color = "#dc3545"
                priority_bg = "#dc354522"
            elif risk_score >= flag_threshold:
                priority_icon = "🟡"
                priority_text = "Medium Risk"
                priority_color = "#ffc107"
                priority_bg = "#ffc10722"
            else:
                priority_icon = "🟢"
                priority_text = "Low Risk"
                priority_color = "#28a745"
                priority_bg = "#28a74522"
            
            with st.container():
                # Display transaction with priority styling
                st.markdown(f"""
                <div style='padding: 10px; border-left: 4px solid {priority_color}; background: {priority_bg}; margin-bottom: 10px; border-radius: 5px;'>
                    <h4 style='color: {priority_color}; margin: 0;'>{priority_icon} {priority_text} - TX #{tx.id}</h4>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                
                with col1:
                    # Get user names - FIXED: Handle None values
                    with eng.begin() as conn:
                        if tx.sender_id:
                            sender = conn.execute(
                                select(users.c.name, users.c.email)
                                .where(users.c.id == tx.sender_id)
                            ).fetchone()
                            sender_name = f"{sender.name or 'Unknown'} ({sender.email})" if sender else f"User {tx.sender_id}"
                        else:
                            sender_name = "System"
                        
                        if tx.recipient_id:
                            recipient = conn.execute(
                                select(users.c.name, users.c.email)
                                .where(users.c.id == tx.recipient_id)
                            ).fetchone()
                            recipient_name = f"{recipient.name or 'Unknown'} ({recipient.email})" if recipient else f"User {tx.recipient_id}"
                        else:
                            recipient_name = "System"
                    
                    st.write(f"**TX #{tx.id}** - {(tx.transaction_type or 'unknown').title()}")
                    st.write(f"**From:** {sender_name}")
                    st.write(f"**To:** {recipient_name}")
                
                with col2:
                    st.write(f"**${tx.amount or 0:,.2f}**")
                    st.markdown(f"<span style='color: {priority_color}; font-weight: bold;'>Risk: {risk_score:.3f}</span>", unsafe_allow_html=True)
                
                with col3:
                    # Status with color coding
                    status_colors = {
                        "Success": "🟢",
                        "Flagged": "🟡", 
                        "Under Review": "🟡",
                        "Blocked": "🔴",
                        "Pending Approval": "🔴",
                        "Rejected": "❌"
                    }
                    status_icon = status_colors.get(tx.status, "📋")
                    st.write(f"{status_icon} {tx.status or 'Unknown'}")
                
                with col4:
                    if tx.created_at:
                        st.write(tx.created_at.strftime("%m/%d/%Y"))
                        st.write(tx.created_at.strftime("%I:%M %p"))
                    else:
                        st.write("Unknown date")
                
                # Enhanced details expandable section
                if tx.details and isinstance(tx.details, dict):
                    risk_factors = tx.details.get("risk_factors", [])
                    if risk_factors:
                        with st.expander("🔍 Risk Analysis"):
                            cola, colb = st.columns(2)
                            
                            with cola:
                                st.write("**Risk Factors:**")
                                for factor in risk_factors[:5]:
                                    st.write(f"• {factor}")
                            
                            with colb:
                                st.write("**Technical Details:**")
                                st.write(f"• **IP:** {tx.ip or 'Unknown'}")
                                st.write(f"• **Device:** {(tx.device or 'Unknown')[:30]}...")
                                st.write(f"• **Location:** {tx.location or 'Unknown'}")
                                
                                if tx.details.get("velocity_violations"):
                                    st.write(f"• **Velocity Issues:** {len(tx.details['velocity_violations'])}")
                
                st.markdown("---")
    else:
        st.info("📭 No transactions match the selected filters.")
        
        # Show current thresholds for reference
        st.subheader("📊 Current Risk Thresholds")
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"""
            **Risk Processing:**
            • **Risk < {flag_threshold}:** Process Immediately (Success)
            • **Risk {flag_threshold} - {block_threshold}:** Process but Flag (Under Review)
            • **Risk ≥ {block_threshold}:** Block until Approved (Pending Approval)
            """)
        
        with col2:
            st.write("**Priority Legend:**")
            st.markdown(f"🟢 **Low Risk:** Below {flag_threshold}")
            st.markdown(f"🟡 **Medium Risk:** {flag_threshold} - {block_threshold}")
            st.markdown(f"🔴 **High Risk:** Above {block_threshold}")

def render_case_management():
    """Case Management Tab"""
    st.header("🕵️ Case Management")
    
    eng = get_engine()
    
    # Open Cases
    st.subheader("📋 Unassigned Cases")
    
    with eng.begin() as conn:
        open_cases = conn.execute(
            select(cases, transactions)
            .join(transactions, cases.c.transaction_id == transactions.c.id)
            .where(cases.c.status == "Assigned", cases.c.assigned_to.is_(None))
        ).fetchall()
        
        cyber_officials = conn.execute(
            select(users).where(users.c.role == "cyber", users.c.status == "approved")
        ).fetchall()
    
    if open_cases:
        # Bulk assignment feature
        st.subheader("⚡ Bulk Case Assignment")
        
        if cyber_officials:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                cyber_options = {f"{c.name or c.email}": c.id for c in cyber_officials}
                bulk_assignee = st.selectbox("Assign All Cases To", list(cyber_options.keys()))
            
            with col2:
                if st.button("📋 Assign All Cases", type="primary"):
                    cyber_id = cyber_options[bulk_assignee]
                    with eng.begin() as conn:
                        for case in open_cases:
                            conn.execute(
                                update(cases)
                                .where(cases.c.id == case.cases_id)
                                .values(assigned_to=cyber_id, status="In Review")
                            )
                            conn.execute(insert(audit_logs).values(
                                actor_user_id=st.session_state["user_id"],
                                action="assign_case",
                                entity_type="case",
                                entity_id=case.cases_id,
                                details=f"Bulk assigned case #{case.cases_id} to {bulk_assignee}"
                            ))
                    
                    st.success(f"✅ All {len(open_cases)} cases assigned to {bulk_assignee}")
                    st.rerun()
            
            with col3:
                st.metric("Open Cases", len(open_cases))
        
        st.markdown("---")
        
        # Individual case assignment
        for case in open_cases:
            # GET DYNAMIC THRESHOLDS FROM SETTINGS
            with eng.begin() as conn:
                sys_cfg_row = conn.execute(select(settings).where(settings.c.key == "system")).fetchone()
                sys_cfg = sys_cfg_row.value if sys_cfg_row else {}
                
                # Get admin-configured thresholds
                flag_threshold = sys_cfg.get("flag_threshold", 0.4)
                block_threshold = sys_cfg.get("block_threshold", 0.7)
            
            # Determine priority based on ADMIN-SET thresholds - FIXED: Handle None risk_score
            risk_score = case.transactions_risk_score or 0
            
            if risk_score >= block_threshold:
                priority_icon = "🔴"
                priority_text = "High Priority"
                priority_color = "#dc3545"
                priority_bg = "#dc354522"
                threshold_desc = f"Above Block Threshold ({block_threshold})"
            elif risk_score >= flag_threshold:
                priority_icon = "🟡"
                priority_text = "Medium Priority"
                priority_color = "#ffc107"
                priority_bg = "#ffc10722"
                threshold_desc = f"Above Flag Threshold ({flag_threshold})"
            else:
                priority_icon = "🟢"
                priority_text = "Low Priority"
                priority_color = "#28a745"
                priority_bg = "#28a74522"
                threshold_desc = f"Below Flag Threshold ({flag_threshold})"
            
            with st.container():
                # Display case with proper priority styling
                st.markdown(f"""
                <div style='padding: 10px; border-left: 4px solid {priority_color}; background: {priority_bg}; margin-bottom: 10px; border-radius: 5px;'>
                    <h4 style='color: {priority_color}; margin: 0;'>{priority_icon} {priority_text} - Case #{case.cases_id}</h4>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"**Transaction:** ${case.transactions_amount or 0:.2f}")
                    st.write(f"**Risk Score:** {risk_score:.3f}")
                    st.write(f"**Status:** {case.transactions_status or 'Unknown'}")
                    st.write(f"**Created:** {case.cases_created_at.strftime('%Y-%m-%d %H:%M') if case.cases_created_at else 'Unknown'}")
                
                with col2:
                    # Show priority with colored text and dynamic thresholds
                    st.markdown(f"<span style='color: {priority_color}; font-weight: bold; font-size: 1.1em;'>{priority_icon} {priority_text}</span>", unsafe_allow_html=True)
                    st.write(threshold_desc)
                    
                    # Show current admin thresholds for reference
                    st.caption(f"Flag: {flag_threshold} | Block: {block_threshold}")
                    
                    if cyber_officials:
                        cyber_options = {f"{c.name or c.email}": c.id for c in cyber_officials}
                        selected_cyber = st.selectbox(
                            "Assign to", 
                            list(cyber_options.keys()), 
                            key=f"assign_{case.cases_id}"
                        )
                
                with col3:
                    if cyber_officials and st.button("📋 Assign", key=f"btn_assign_{case.cases_id}"):
                        cyber_id = cyber_options[selected_cyber]
                        with eng.begin() as conn:
                            conn.execute(
                                update(cases)
                                .where(cases.c.id == case.cases_id)
                                .values(assigned_to=cyber_id, status="In Review")
                            )
                            conn.execute(insert(audit_logs).values(
                                actor_user_id=st.session_state["user_id"],
                                action="assign_case",
                                entity_type="case",
                                entity_id=case.cases_id,
                                details=f"Assigned case #{case.cases_id} to {selected_cyber}"
                            ))
                        st.success(f"Case assigned to {selected_cyber}")
                        st.rerun()
                
                st.markdown("---")
    else:
        if not cyber_officials:
            st.warning("⚠️ No cyber officials available for case assignment")
        else:
            st.success("✅ No unassigned cases")
    
    # Case Statistics
    st.subheader("📊 Case Statistics")
    
    with eng.begin() as conn:
        all_cases = conn.execute(select(cases)).fetchall()
        resolved_cases = [c for c in all_cases if c.status == "Resolved"]
        in_review_cases = [c for c in all_cases if c.status == "In Review"]
        
        # Get resolution breakdown
        fraud_detected = len([c for c in resolved_cases if c.finding == "Fraudulent"])
        false_positives = len([c for c in resolved_cases if c.finding == "Safe"])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 Total Cases", len(all_cases))
    with col2:
        st.metric("🔍 In Review", len(in_review_cases))
    with col3:
        st.metric("✅ Resolved", len(resolved_cases))
    with col4:
        detection_rate = fraud_detected / len(resolved_cases) * 100 if resolved_cases else 0
        st.metric("🎯 Fraud Detection Rate", f"{detection_rate:.1f}%")

def render_system_settings():
    """System Settings Tab"""
    st.header("⚙️ System Settings")
    
    eng = get_engine()
    with eng.begin() as conn:
        cfg_row = conn.execute(select(settings).where(settings.c.key == "system")).fetchone()
        cfg = cfg_row.value if cfg_row else {}
    
    st.subheader("🛡️ Fraud Detection Configuration")
    
    with st.form("settings_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Transaction Limits**")
            tx_limit = st.number_input("Transaction Limit ($)", min_value=100.0, value=float(cfg.get("tx_limit_amount", 5000.0)), step=100.0)
            max_fail = st.number_input("Max Failed Attempts", min_value=1, value=int(cfg.get("max_failed_attempts", 3)))
            
            st.markdown("**Risk Thresholds**")
            flag_threshold = st.slider("Flag Threshold", 0.0, 1.0, float(cfg.get("flag_threshold", 0.4)), 0.01, 
                                     help="Above this score = Under Review (but processed)")
            block_threshold = st.slider("Block Threshold", 0.0, 1.0, float(cfg.get("block_threshold", 0.7)), 0.01,
                                      help="Above this score = Blocked (pending approval)")
        
        with col2:
            st.markdown("**Risk Locations**")
            unusual_locations = st.text_area(
                "Unusual Locations (one per line)", 
                value="\n".join(cfg.get("unusual_locations", ["Unknown", "High-Risk-Geo"])),
                height=100
            )
            
            st.markdown("**System Features**")
            enable_notif = st.toggle("Enable Notifications", value=bool(cfg.get("enable_notifications", True)))
            auto_block = st.toggle("Auto-block High Risk", value=bool(cfg.get("auto_block_high_risk", True)))
            
            st.markdown("**User Management**")
            default_balance = st.number_input("Default User Balance ($)", min_value=0.0, value=float(cfg.get("default_user_balance", 2000.0)), step=100.0)
        
        if st.form_submit_button("💾 Save Settings", type="primary"):
            new_cfg = {
                "tx_limit_amount": tx_limit,
                "max_failed_attempts": max_fail,
                "unusual_locations": [loc.strip() for loc in unusual_locations.split("\n") if loc.strip()],
                "enable_notifications": enable_notif,
                "auto_block_high_risk": auto_block,
                "flag_threshold": flag_threshold,
                "block_threshold": block_threshold,
                "default_user_balance": default_balance
            }
            
            with eng.begin() as conn:
                conn.execute(update(settings).where(settings.c.key == "system").values(value=new_cfg))
                conn.execute(insert(audit_logs).values(
                    actor_user_id=st.session_state["user_id"],
                    action="update_settings",
                    entity_type="settings",
                    entity_id=0,
                    details=f"Updated system settings - Flag: {flag_threshold}, Block: {block_threshold}, Tx Limit: ${tx_limit}"
                ))
            
            st.success("✅ Settings saved successfully!")
            st.rerun()
    
    # Show current configuration
    st.markdown("---")
    st.subheader("📋 Current Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"""
        **Risk Processing:**
        • Risk < {cfg.get('flag_threshold', 0.4):.2f} → ✅ **Process Immediately** (Success)
        • Risk {cfg.get('flag_threshold', 0.4):.2f} - {cfg.get('block_threshold', 0.7):.2f} → ⚠️ **Process but Flag** (Under Review)  
        • Risk > {cfg.get('block_threshold', 0.7):.2f} → 🚫 **Block until Approved** (Pending Approval)
        """)
    
    with col2:
        st.info(f"""
        **System Limits:**
        • Transaction Limit: ${cfg.get('tx_limit_amount', 5000):,.2f}
        • Max Failed Attempts: {cfg.get('max_failed_attempts', 3)}
        • Default User Balance: ${cfg.get('default_user_balance', 2000):,.2f}
        • Unusual Locations: {len(cfg.get('unusual_locations', []))} defined
        """)

def render_payment_monitoring():
    """Payment Monitoring Tab - NEW"""
    st.header("⏳ Payment Monitoring")
    
    eng = get_engine()
    
    # Pending Approvals Overview
    st.subheader("🚫 Blocked Payments (Pending Approval)")
    
    with eng.begin() as conn:
        pending_payments = conn.execute(
            select(transactions)
            .where(transactions.c.status == "Pending Approval")
            .order_by(desc(transactions.c.created_at))
        ).fetchall()
    
    if pending_payments:
        # Summary metrics - FIXED: Handle None values
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("⏳ Pending Count", len(pending_payments))
        
        with col2:
            total_blocked_amount = sum(p.amount or 0 for p in pending_payments)
            st.metric("💰 Total Blocked Amount", f"${total_blocked_amount:,.2f}")
        
        with col3:
            valid_risk_scores = [p.risk_score for p in pending_payments if p.risk_score is not None]
            avg_risk = sum(valid_risk_scores) / len(valid_risk_scores) if valid_risk_scores else 0
            st.metric("⚠️ Avg Risk Score", f"{avg_risk:.3f}")
        
        with col4:
            critical_count = len([p for p in pending_payments if (p.risk_score or 0) >= 0.9])
            st.metric("🚨 Critical Risk", critical_count)
        
        st.markdown("---")
        
        # Detailed pending payments view
        for payment in pending_payments:
            with st.expander(f"Payment #{payment.id} - ${payment.amount or 0:.2f} (Risk: {payment.risk_score or 0:.3f})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Transaction ID:** {payment.id}")
                    st.write(f"**Amount:** ${payment.amount or 0:.2f}")
                    st.write(f"**Risk Score:** {payment.risk_score or 0:.3f}")
                    st.write(f"**Sender ID:** {payment.sender_id or 'Unknown'}")
                    st.write(f"**Recipient ID:** {payment.recipient_id or 'Unknown'}")
                    st.write(f"**Created:** {payment.created_at or 'Unknown'}")
                    
                    # Get user details - FIXED: Handle None values
                    if payment.sender_id:
                        with eng.begin() as conn:
                            sender = conn.execute(select(users.c.name, users.c.email).where(users.c.id == payment.sender_id)).fetchone()
                            if sender:
                                st.write(f"**Sender:** {sender.name or 'Unknown'} ({sender.email or 'No Email'})")
                
                with col2:
                    st.write(f"**IP Address:** {payment.ip or 'Unknown'}")
                    st.write(f"**Device:** {payment.device or 'Unknown'}")
                    st.write(f"**Location:** {payment.location or 'Unknown'}")
                    
                    # Show risk factors
                    if payment.details and isinstance(payment.details, dict):
                        risk_factors = payment.details.get("risk_factors", [])
                        if risk_factors:
                            st.write("**Risk Factors:**")
                            for factor in risk_factors[:5]:
                                st.write(f"• {factor}")
                
                # Admin actions (override capability)
                st.write("**Admin Override Actions:**")
                override_col1, override_col2 = st.columns(2)
                
                with override_col1:
                    if st.button(f"✅ Force Approve", key=f"admin_approve_{payment.id}"):
                        # Admin can force approve high-risk payments
                        with eng.begin() as conn:
                            # Get current balances - FIXED: Handle None values
                            sender = conn.execute(select(users).where(users.c.id == payment.sender_id)).fetchone()
                            recipient = conn.execute(select(users).where(users.c.id == payment.recipient_id)).fetchone()
                            
                            sender_balance = float(sender.balance or 0) if sender else 0
                            payment_amount = float(payment.amount or 0)
                            
                            if sender and recipient and sender_balance >= payment_amount:
                                # Process payment
                                conn.execute(update(users).where(users.c.id == payment.sender_id).values(
                                    balance=sender_balance - payment_amount
                                ))
                                
                                recipient_balance = float(recipient.balance or 0)
                                conn.execute(update(users).where(users.c.id == payment.recipient_id).values(
                                    balance=recipient_balance + payment_amount
                                ))
                                
                                # Update status
                                conn.execute(update(transactions).where(transactions.c.id == payment.id).values(
                                    status="Success (Admin Override)"
                                ))
                                
                                conn.execute(insert(audit_logs).values(
                                    actor_user_id=st.session_state["user_id"],
                                    action="admin_force_approve",
                                    entity_type="transaction",
                                    entity_id=payment.id,
                                    details=f"Admin force approved payment #{payment.id} for ${payment_amount} (Risk: {payment.risk_score or 0:.3f})"
                                ))
                                
                                st.success("✅ Payment force approved by admin!")
                            else:
                                st.error("❌ Cannot process - insufficient balance")
                        
                        st.rerun()
                
                with override_col2:
                    if st.button(f"❌ Force Reject", key=f"admin_reject_{payment.id}"):
                        with eng.begin() as conn:
                            # Update status
                            conn.execute(update(transactions).where(transactions.c.id == payment.id).values(
                                status="Rejected (Admin Override)"
                            ))
                            
                            conn.execute(insert(audit_logs).values(
                                actor_user_id=st.session_state["user_id"],
                                action="admin_force_reject",
                                entity_type="transaction",
                                entity_id=payment.id,
                                details=f"Admin force rejected payment #{payment.id} for ${payment.amount or 0} (Risk: {payment.risk_score or 0:.3f})"
                            ))
                        
                        st.warning("❌ Payment force rejected by admin!")
                        st.rerun()
    else:
        st.success("✅ No payments are currently blocked")
    
    # Recent payment approvals/rejections
    st.subheader("📈 Recent Payment Decisions")
    
    with eng.begin() as conn:
        recent_decisions = conn.execute(
            select(audit_logs)
            .where(audit_logs.c.action.in_(["approve_payment", "reject_payment", "admin_force_approve", "admin_force_reject"]))
            .order_by(desc(audit_logs.c.created_at))
            .limit(10)
        ).fetchall()
    
    if recent_decisions:
        decisions_data = []
        for decision in recent_decisions:
            action_display = (decision.action or "unknown_action").replace('_', ' ').title()
            
            # Extract amount from details string if possible - FIXED: Handle None
            amount = "Unknown"
            if decision.details and isinstance(decision.details, str):
                if '$' in decision.details:
                    try:
                        parts = decision.details.split('$')
                        if len(parts) > 1:
                            amount = f"${parts[1].split(' ')[0]}"
                    except:
                        pass
            
            decisions_data.append({
                "Action": action_display,
                "Amount": amount,
                "Date": decision.created_at.strftime("%Y-%m-%d %H:%M") if decision.created_at else "Unknown",
                "Actor": f"User {decision.actor_user_id or 'Unknown'}"
            })
        
        decisions_df = pd.DataFrame(decisions_data)
        st.dataframe(decisions_df, use_container_width=True)
    else:
        st.info("No recent payment decisions recorded")

def run():
    role_guard(["admin", "cyber"])

    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.title("System Administration")
    
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, type="secondary"):
            st.rerun()

    # Initialize tab state
    if "admin_tab" not in st.session_state:
        st.session_state.admin_tab = 0

    # Tab navigation - UPDATED with new Payment Monitoring tab
    tab_names = [
        "🎯 Overview", 
        "👥 Users", 
        "💰 Balances", 
        "📊 Transactions", 
        "🕵️ Cases", 
        "⚙️ Settings",
        "⏳ Payment Monitoring"  # NEW TAB
    ]
    selected_tabs = st.tabs(tab_names)

    # Tab content
    with selected_tabs[0]:
        render_admin_overview()

    with selected_tabs[1]:
        render_user_management()

    with selected_tabs[2]:
        render_balance_management()

    with selected_tabs[3]:
        render_transaction_monitoring()

    with selected_tabs[4]:
        render_case_management()

    with selected_tabs[5]:
        render_system_settings()
    
    with selected_tabs[6]:
        render_payment_monitoring()

if __name__ == "__main__":
    run()
