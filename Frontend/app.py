import streamlit as st
import pandas as pd
import sys
import os
from PIL import Image
from datetime import datetime

# ============================================
# BACKEND INTEGRATION - FIX PATH FOR YOUR STRUCTURE
# ============================================
# Your structure: Frontend/ and backend/ are siblings
# We need to go UP one level, then into backend/

# Get the parent directory (one level up from Frontend/)
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(parent_dir, 'backend')

# Add backend to Python path
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Import Hugo Agent
try:
    from main import HugoAgent
    HUGO_AVAILABLE = True
    print(f"✅ Hugo imported successfully from: {backend_path}")
except Exception as e:
    print(f"⚠️ Hugo Backend not available: {e}")
    print(f"Attempted path: {backend_path}")
    HUGO_AVAILABLE = False

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Hugo AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CUSTOM CSS (The Styling Engine) ---
st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        justify-content: center;
        width: 100%;
        gap: 20px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre-wrap;
        background-color: #F4F5F7;
        border-radius: 8px;
        padding-top: 12px;
        padding-bottom: 12px;
        padding-left: 30px;
        padding-right: 30px;
        font-size: 1.3rem;
        font-weight: 900;
        color: #5E6C84;
        border: 1px solid #dfe1e6;
        box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
    }

    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF;
        color: #0052CC;
        border: 2px solid #0052CC;
        box-shadow: 0px 4px 8px rgba(0,82,204,0.15);
    }
    
    .footer {
        width: 100%;
        text-align: center;
        padding: 20px;
        margin-top: 50px;
        border-top: 1px solid #eaeaea;
        color: #6B778C;
        font-size: 14px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. BACKEND SETUP ---

# A. SAMPLE EMAILS FOR DEMO (fallback if Gmail not configured)
SIMULATION_EMAILS = [
    {
        "sender": "logistics@supA.com", 
        "subject": "Delay on O5007 – S1 V1 500W Brushless Motor",
        "body": "Hi Team,\n\nI'm writing to let you know that Purchase Order O5007 (S1 V1 500W Brushless Motor, part P300) is now delayed.\nOur production line experienced a tooling issue last week, so the expected delivery date has shifted from 2025-03-20 to 2025-04-05.\n\nWe apologize for the inconvenience.\n\nBest,\nAna Torres"
    },
    {
        "sender": "sales@supB.com", 
        "subject": "Price Update for Li-Po 48V 12Ah Battery Pack",
        "body": "Hello Voltway Team,\n\nEffective 2025-05-01, the unit price for Li-Po 48V 12Ah Battery Pack (part P302) will increase from $78.50 to $85.00.\nThis is due to raw material cost increases for cobalt.\n\nRegards,\nJin Wu"
    },
    {
        "sender": "qa-team@supA.com", 
        "subject": "URGENT: Quality Alert on S3 V2 Carbon Fiber Frame",
        "body": "Hi Engineering Team,\n\nDuring our final QC check, we identified hairline cracks on several units of the S3 V2 Carbon Fiber Frame (part P323).\nAffected batch: PO O5023, shipped 2025-04-10.\n\nWe recommend halting assembly on incoming frames.\n\nRegards,\nMark Nguyen"
    },
    {
        "sender": "shipping@supC.com", 
        "subject": "Early Partial Shipment for O5075 – 12-inch Alloy Wheel",
        "body": "Hello Voltway Team,\n\nGood news—PO O5075 (12-inch Alloy Wheel, part P330) has partially shipped ahead of schedule.\nWe've dispatched 40 of 60 wheels today via Express Freight.\nExpected delivery: 2025-04-18.\n\nCheers,\nElena Rodriguez"
    },
    {
        "sender": "operations@voltway.co", 
        "subject": "URGENT: Cancel O5021 (Carbon Fiber Frame)",
        "body": "Hello SupC Team,\n\nPlease cancel Purchase Order O5021 for Carbon Fiber Frame (part P303).\nWe've decided to delay the V1→V2 upgrade rollout.\n\nThanks,\nJordan Lee"
    }
]

# B. INITIALIZE HUGO AGENT
@st.cache_resource
def init_hugo():
    """Initialize Hugo Agent (cached for performance)"""
    if HUGO_AVAILABLE:
        try:
            agent = HugoAgent()
            print("✅ Hugo Agent initialized successfully")
            return agent
        except Exception as e:
            print(f"❌ Failed to initialize Hugo: {e}")
            import traceback
            traceback.print_exc()
            return None
    return None

# C. SESSION STATE INITIALIZATION
if "hugo_agent" not in st.session_state: 
    st.session_state.hugo_agent = init_hugo()
if "messages" not in st.session_state: 
    st.session_state.messages = []
if "risk_analysis" not in st.session_state: 
    st.session_state.risk_analysis = None
if "email_index" not in st.session_state: 
    st.session_state.email_index = 0
if "current_email" not in st.session_state: 
    st.session_state.current_email = SIMULATION_EMAILS[0]
if "processed_alerts" not in st.session_state:
    st.session_state.processed_alerts = []

# --- 4. THE HEADER SECTION ---
col_logo, col_space, col_m1, col_m2, col_m3, col_status = st.columns([2, 1.5, 1, 1, 1, 1])

with col_logo:
    try:
        image = Image.open('logo.png')
        st.image(image, width=680) 
    except FileNotFoundError:
        st.markdown("### 🤖 HUGO AI - Procurement Watchdog")

def metric_below(label, value, delta):
    st.markdown(f"""
    <div style="text-align: center;margin-top: 50px">
        <div style="font-size: 34px; font-weight: 700; color: #091E42;">{value} <span style="font-size: 18px; color: #006644; font-weight: 600;">{delta}</span></div>
        <div style="font-size: 22px; font-weight: 600; color: #5E6C84; margin-top: -5px;">{label}</div>
    </div>
    """, unsafe_allow_html=True)

with col_m1:
    metric_below("Alerts", str(len(st.session_state.processed_alerts)), "+0")
with col_m2:
    # Get open POs count from Hugo if available
    po_count = 0
    if st.session_state.hugo_agent:
        try:
            po_count = len(st.session_state.hugo_agent.get_open_orders())
        except:
            po_count = 0
    metric_below("Active POs", str(po_count), "+0")
with col_m3:
    status = "ONLINE" if HUGO_AVAILABLE and st.session_state.hugo_agent else "OFFLINE"
    metric_below("Hugo Status", status, "")

with col_status:
    status_color = "#0f2f57" if (HUGO_AVAILABLE and st.session_state.hugo_agent) else "#cc0000"
    st.markdown(f'<div style="text-align: right; margin-top: 50px; font-size: 20px; font-weight: 900; color: {status_color};">{status}</div>', unsafe_allow_html=True)

st.divider()

# --- 5. CENTERED NAVIGATION TABS ---
tab_ops, tab_brain, tab_data = st.tabs(["  📡 LIVE OPERATIONS  ", "  🧠 INTELLIGENCE HUB  ", "  💾 DATA NEXUS  "])

# ==========================================
# === TAB 1: LIVE OPERATIONS ===
# ==========================================
with tab_ops:
    st.markdown("<br>", unsafe_allow_html=True)
    
    c_left, c_right = st.columns([1, 1.2], gap="large")
    
    with c_left:
        with st.container(border=True):
            col_head, col_sim = st.columns([2, 1])
            with col_head:
                st.subheader("Incoming Stream")
            with col_sim:
                if st.button("🎲 Simulate Emails", type="secondary", use_container_width=True):
                    st.session_state.email_index = (st.session_state.email_index + 1) % len(SIMULATION_EMAILS)
                    st.session_state.current_email = SIMULATION_EMAILS[st.session_state.email_index]
                    st.session_state.risk_analysis = None
                    st.rerun()

            curr = st.session_state.current_email
            st.info(f"📨 **Inbox:** New Message from *{curr['sender']}*\n\n**Subject:** {curr['subject']}")
            
            email_text = st.text_area("Content:", value=curr['body'], height=150)
            
            if st.button("🔄 ANALYZE & SYNC", type="primary", use_container_width=True):
                if HUGO_AVAILABLE and st.session_state.hugo_agent:
                    with st.spinner("🧠 Hugo is analyzing..."):
                        try:
                            # Use Hugo's real AI processing
                            alert = st.session_state.hugo_agent.process_single_email_from_text(
                                sender=curr['sender'],
                                subject=curr['subject'],
                                body=email_text
                            )
                            
                            # Convert Hugo's AlertResult to our format
                            change = alert.delivery_change
                            risk = alert.risk_assessment
                            
                            # Determine severity and type
                            if change.detected:
                                severity = "CRITICAL" if (change.delay_days and change.delay_days >= 7) else "HIGH" if change.delay_days else "WARNING"
                                
                                st.session_state.risk_analysis = {
                                    "type": change.change_type.value if change.change_type else "general",
                                    "title": f"{change.change_type.value.title() if change.change_type else 'Update'} Detected",
                                    "severity": severity,
                                    "metric_label": "Delay" if change.delay_days else "Change Confidence",
                                    "metric_val": f"{change.delay_days} days" if change.delay_days else f"{change.confidence:.0%}",
                                    "impact": risk.impact_summary if risk else (change.supplier_reason or "Impact assessment in progress"),
                                    "action_1": risk.recommended_actions[0] if risk and risk.recommended_actions else "✈️ Expedite Shipment",
                                    "action_2": risk.recommended_actions[1] if risk and len(risk.recommended_actions) > 1 else "📅 Reschedule Build",
                                    "po_number": alert.matched_po.po_number if alert.matched_po else "N/A",
                                    "risk_score": risk.risk_score if risk else 0.5
                                }
                                
                                # Add to processed alerts
                                st.session_state.processed_alerts.append(alert)
                                st.success("✅ Analysis complete!")
                            else:
                                st.session_state.risk_analysis = {
                                    "type": "general",
                                    "title": "No Risk Detected",
                                    "severity": "LOW",
                                    "metric_label": "Confidence",
                                    "metric_val": f"{change.confidence:.0%}",
                                    "impact": "Email processed. No immediate action required.",
                                    "action_1": "📂 Archive",
                                    "action_2": "↩️ Reply"
                                }
                                st.info("ℹ️ No significant risk detected.")
                        except Exception as e:
                            st.error(f"❌ Hugo analysis failed: {e}")
                            import traceback
                            st.code(traceback.format_exc())
                            st.session_state.risk_analysis = None
                else:
                    st.error("❌ Hugo backend is not available. Check terminal for errors.")
                    st.info(f"Backend path attempted: {backend_path}")

    with c_right:
        if st.session_state.risk_analysis:
            res = st.session_state.risk_analysis
            
            box_color = "red" if res['severity'] == "CRITICAL" else "orange" if res['severity'] in ["HIGH", "WARNING"] else "green"
            
            with st.container(border=True):
                if box_color == "red": 
                    st.error(f"🚨 **{res['title']}**")
                elif box_color == "orange": 
                    st.warning(f"⚠️ **{res['title']}**")
                else: 
                    st.success(f"✅ **{res['title']}**")
                
                m1, m2 = st.columns(2)
                m1.metric(res['metric_label'], res['metric_val'], delta=res['severity'], delta_color="inverse")
                
                # Show PO number if available
                if 'po_number' in res and res['po_number'] != "N/A":
                    m2.metric("Matched PO", res['po_number'])
                else:
                    m2.write(f"**Impact:** {res['impact'][:50]}...")
                
                st.divider()
                st.markdown("#### Recommended Action")
                
                b1, b2 = st.columns(2)
                if b1.button(res['action_1'], use_container_width=True):
                    st.toast(f"Action '{res['action_1']}' executed successfully!")
                if b2.button(res['action_2'], use_container_width=True):
                    st.session_state.risk_analysis = None
                    st.rerun()
        else:
            with st.container(border=True):
                st.success("✅ Operations Normal")
                st.caption("No active threats detected in the supply chain.")
                if not HUGO_AVAILABLE:
                    st.warning("⚠️ Hugo backend is offline. Running in demo mode.")

# ==========================================
# === TAB 2: INTELLIGENCE HUB ===
# ==========================================
with tab_brain:
    st.markdown("<br>", unsafe_allow_html=True)
    
    c_chat, c_context = st.columns([2, 1])
    
    with c_chat:
        with st.container(border=True):
            st.markdown("### 💬 Ask Hugo")
            
            chat_box = st.container(height=400)
            with chat_box:
                for msg in st.session_state.messages:
                    st.chat_message(msg["role"]).write(msg["content"])
            
            if prompt := st.chat_input("Query operations (e.g. 'Show me recent alerts')..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with chat_box:
                    st.chat_message("user").write(prompt)
                
                # Hugo-powered response
                response = "I'm analyzing your query..."
                
                if HUGO_AVAILABLE and st.session_state.hugo_agent:
                    try:
                        prompt_lower = prompt.lower()
                        
                        # Query routing based on keywords
                        if "alert" in prompt_lower or "recent" in prompt_lower:
                            if st.session_state.processed_alerts:
                                response = f"Found {len(st.session_state.processed_alerts)} recent alerts:\n\n"
                                for i, alert in enumerate(st.session_state.processed_alerts[-3:], 1):
                                    response += f"{i}. {alert.email.subject} - {alert.delivery_change.change_type.value if alert.delivery_change.change_type else 'Update'}\n"
                            else:
                                response = "No alerts processed yet. Click 'Simulate Emails' and 'Analyze' to generate alerts."
                        
                        elif "po" in prompt_lower or "order" in prompt_lower:
                            orders = st.session_state.hugo_agent.get_open_orders()
                            response = f"Found {len(orders)} open purchase orders.\n\n"
                            for po in orders[:3]:
                                response += f"• PO {po.po_number}: {po.supplier_name} - ${po.total_value:,.2f}\n"
                        
                        elif "supplier" in prompt_lower or "vendor" in prompt_lower:
                            response = "Supplier analysis available. Which supplier would you like information about?"
                        
                        else:
                            response = "I can help you with:\n• Recent alerts\n• Purchase orders\n• Supplier history\n• Risk assessments"
                    
                    except Exception as e:
                        response = f"Error processing query: {e}"
                else:
                    response = "Hugo backend is offline. Please check backend configuration."
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                with chat_box:
                    st.chat_message("assistant").write(response)
    
    with c_context:
        st.info("💡 **Hugo Capabilities:**\n\n- 📧 Email Analysis\n- 🎯 Risk Detection\n- 📊 PO Matching\n- 🔍 Supplier History\n- ⚠️ Alert Generation")
        
        if HUGO_AVAILABLE and st.session_state.hugo_agent:
            st.success("✅ Backend Connected")
        else:
            st.error("❌ Backend Offline")
            with st.expander("Debug Info"):
                st.code(f"Backend path: {backend_path}")
                st.code(f"HUGO_AVAILABLE: {HUGO_AVAILABLE}")
                st.code(f"Agent initialized: {st.session_state.hugo_agent is not None}")

# ==========================================
# === TAB 3: DATA NEXUS ===
# ==========================================
with tab_data:
    st.markdown("<br>", unsafe_allow_html=True)
    
    tab_po, tab_alerts, tab_history = st.tabs(["Purchase Orders", "Alert History", "Supplier Data"])
    
    with tab_po:
        st.markdown("### 💾 Open Purchase Orders")
        if HUGO_AVAILABLE and st.session_state.hugo_agent:
            try:
                orders = st.session_state.hugo_agent.get_open_orders()
                if orders:
                    po_data = pd.DataFrame([{
                        "PO Number": po.po_number,
                        "Supplier": po.supplier_name,
                        "Value": po.total_value,
                        "Priority": po.priority.upper(),
                        "Expected Date": po.expected_delivery_date.strftime("%Y-%m-%d") if po.expected_delivery_date else "N/A"
                    } for po in orders])
                    
                    st.dataframe(po_data, use_container_width=True, height=400)
                else:
                    st.info("No open purchase orders found.")
            except Exception as e:
                st.error(f"Failed to load PO data: {e}")
                st.code(str(e))
        else:
            st.warning("Hugo backend not available.")
    
    with tab_alerts:
        st.markdown("### ⚠️ Processed Alerts")
        if st.session_state.processed_alerts:
            alert_data = []
            for alert in st.session_state.processed_alerts:
                alert_data.append({
                    "Timestamp": alert.processed_at.strftime("%H:%M:%S"),
                    "Sender": alert.email.sender,
                    "Type": alert.delivery_change.change_type.value if alert.delivery_change.change_type else "General",
                    "Severity": alert.risk_assessment.risk_level.value.upper() if alert.risk_assessment else "N/A",
                    "PO": alert.matched_po.po_number if alert.matched_po else "Unmapped"
                })
            
            df = pd.DataFrame(alert_data)
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("No alerts processed yet. Process some emails in the Live Operations tab.")
    
    with tab_history:
        st.markdown("### 📚 Supplier Historical Data")
        st.info("Historical incident data will appear here after processing alerts.")

# --- 6. FOOTER ---
st.markdown('<div class="footer">< Developed by Al Amin and Adnan Mohsin @ 2025 - Powered by Hugo AI ></div>', unsafe_allow_html=True)