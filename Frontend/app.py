import streamlit as st
import pandas as pd
import time
import json
from PIL import Image

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
    /* 1. Reduce top padding so the logo sits high */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    
    /* 2. CENTER THE TABS & MAKE THEM MODERN */
    .stTabs [data-baseweb="tab-list"] {
        justify-content: center;
        width: 100%;
        gap: 20px; /* Space between tabs */
    }

    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre-wrap;
        background-color: #F4F5F7;
        border-radius: 8px; /* Rounded modern tabs */
        padding-top: 12px;
        padding-bottom: 12px;
        padding-left: 30px;
        padding-right: 30px;
        font-size: 1.3rem; /* BIGGER TEXT */
        font-weight: 900;
        color: #5E6C84;
        border: 1px solid #dfe1e6;
        box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
    }

    /* 3. ACTIVE TAB STYLING */
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF;
        color: #0052CC; /* Hugo Blue */
        border: 2px solid #0052CC;
        box-shadow: 0px 4px 8px rgba(0,82,204,0.15);
    }

    # /* 4. ONLINE STATUS */
    # .online-status {
    #     font-weight: 900;
    #     color: #0f2f57;
    #     font-size: 20px;
    #     text-align: right;
    #     margin-top: 50px;
    # }
    
    /* 5. FOOTER STYLING */
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

# --- 3. BACKEND SETUP (Simulation) ---

# A. THE REAL SAMPLE DATA (10 Emails)
SIMULATION_EMAILS = [
    {
        "id": 1, "sender": "logistics@supA.com", "subject": "Delay on O5007 – S1 V1 500W Brushless Motor",
        "body": "Hi Team,\n\nI’m writing to let you know that Purchase Order O5007 (S1 V1 500W Brushless Motor, part P300) is now delayed.\nOur production line experienced a tooling issue last week, so the expected delivery date has shifted from 2025-03-20 to 2025-04-05.\n\nWe apologize for the inconvenience.\n\nBest,\nAna Torres"
    },
    {
        "id": 2, "sender": "sales@supB.com", "subject": "Price Update for Li-Po 48V 12Ah Battery Pack",
        "body": "Hello Voltway Team,\n\nEffective 2025-05-01, the unit price for Li-Po 48V 12Ah Battery Pack (part P302) will increase from $78.50 to $85.00.\nThis is due to raw material cost increases for cobalt.\n\nRegards,\nJin Wu"
    },
    {
        "id": 3, "sender": "qa-team@supA.com", "subject": "URGENT: Quality Alert on S3 V2 Carbon Fiber Frame",
        "body": "Hi Engineering Team,\n\nDuring our final QC check, we identified hairline cracks on several units of the S3 V2 Carbon Fiber Frame (part P323).\nAffected batch: PO O5023, shipped 2025-04-10.\n\nWe recommend halting assembly on incoming frames.\n\nRegards,\nMark Nguyen"
    },
    {
        "id": 4, "sender": "shipping@supC.com", "subject": "Early Partial Shipment for O5075 – 12-inch Alloy Wheel",
        "body": "Hello Voltway Team,\n\nGood news—PO O5075 (12-inch Alloy Wheel, part P330) has partially shipped ahead of schedule.\nWe’ve dispatched 40 of 60 wheels today via Express Freight.\nExpected delivery: 2025-04-18.\n\nCheers,\nElena Rodriguez"
    },
    {
        "id": 5, "sender": "contracts@fleet-giant.com", "subject": "Amendment to Framework Contract FC-#S60034",
        "body": "Hi Voltway,\n\nUnder contract FC-#S60034, we’d like to adjust the monthly minimum quantity for S2_V2 scooters from 200 units to 150 units starting May 2025.\nThis is due to slower fleet rollout in the West Coast region.\n\nCheers,\nMarisol Delgado"
    },
    {
        "id": 6, "sender": "product-updates@supA.com", "subject": "Discontinuation of LCD Dashboard Display",
        "body": "Hi Engineers,\n\nWe’re discontinuing the LCD Dashboard Display (part P312) at the end of Q2 2025, replacing it with an OLED unit.\nLast buy date is 2025-06-15.\n\nThanks,\nRaj Patel"
    },
    {
        "id": 7, "sender": "operations@voltway.co", "subject": "URGENT: Cancel O5021 (Carbon Fiber Frame)",
        "body": "Hello SupC Team,\n\nPlease cancel Purchase Order O5021 for Carbon Fiber Frame (part P303).\nWe’ve decided to delay the V1→V2 upgrade rollout.\n\nThanks,\nJordan Lee"
    },
    {
        "id": 8, "sender": "proposals@supD.com", "subject": "Proposal: Digital Controller ZX2 for S-Series",
        "body": "Hello Voltway Team,\n\nWe’d like to propose our new Digital Controller ZX2 as an upgrade path for your Analog Controller ZX (P301).\nBenefits: 20% improved throttle response.\n\nBest regards,\nMia Chen"
    },
    {
        "id": 9, "sender": "shipping@supB.com", "subject": "Partial Shipment for O5045 – Mechanical Disc Brake",
        "body": "Hi there,\n\nThis is to confirm we’ve shipped 60 of 100 units for PO O5045 (Mechanical Disc Brake, part P313).\nExpected arrival: 2025-04-15.\n\nThanks,\nSamir Khan"
    },
    {
        "id": 10, "sender": "sales@supA.com", "subject": "Q2 Discount on S2 V1 Li-Ion 36V 10Ah Battery Pack",
        "body": "Hello Voltway Purchasing,\n\nWe’re offering a 5% discount on the S2 V1 Li-Ion 36V 10Ah Battery Pack (part P309) for any order of 200+ units placed by 2025-05-05.\n\nBest,\nSonia Patel"
    }
]

# B. ENGINE LOGIC (Updated to handle different email types)
class VoltwayEngine:
    def get_stock_status(self): 
        return pd.DataFrame({
            "Material": ["M-500", "F-20", "B-100", "P302", "P323"], 
            "Stock": [50, 20, 200, 15, 80], 
            "Status": ["OK", "LOW", "OK", "CRITICAL", "OK"]
        })

    def analyze_risk(self, email_text):
        """Simple keyword-based logic to simulate AI analysis"""
        text = email_text.lower()
        
        if "delay" in text:
            return {
                "type": "delay",
                "title": "Supply Chain Delay",
                "severity": "CRITICAL",
                "metric_label": "Shortage Forecast",
                "metric_val": "-120 Units",
                "impact": "Production Line 1 halted for 3 days.",
                "action_1": "✈️ Expedite Air Freight",
                "action_2": "📅 Reschedule Build"
            }
        elif "price" in text or "cost" in text or "discount" in text:
            return {
                "type": "finance",
                "title": "Cost Fluctuation",
                "severity": "WARNING",
                "metric_label": "Cost Impact",
                "metric_val": "+8.5%",
                "impact": "Projected margin reduction for Q2.",
                "action_1": "💰 Approve Price Hike",
                "action_2": "🔍 Find Alternate Vendor"
            }
        elif "quality" in text or "cracks" in text or "defect" in text:
            return {
                "type": "quality",
                "title": "Quality Defect Alert",
                "severity": "HIGH",
                "metric_label": "Affected Batch",
                "metric_val": "100% Recall",
                "impact": "Safety risk. Immediate containment required.",
                "action_1": "🛑 Halt Assembly",
                "action_2": "📦 Return to Vendor"
            }
        elif "shipment" in text or "shipped" in text:
            return {
                "type": "logistics",
                "title": "Shipment Update",
                "severity": "NORMAL",
                "metric_label": "Arrival ETA",
                "metric_val": "On Time",
                "impact": "Inventory levels will normalize next week.",
                "action_1": "✅ Acknowledge Receipt",
                "action_2": "🚛 Update Warehouse"
            }
        else:
             return {
                "type": "general",
                "title": "General Update",
                "severity": "LOW",
                "metric_label": "Action Required",
                "metric_val": "None",
                "impact": "Information only. No immediate risk.",
                "action_1": "📂 Archive",
                "action_2": "↩️ Reply"
            }

# C. SESSION STATE INITIALIZATION
if "engine" not in st.session_state: st.session_state.engine = VoltwayEngine()
if "messages" not in st.session_state: st.session_state.messages = []
if "risk_analysis" not in st.session_state: st.session_state.risk_analysis = None
# New State for Email Simulation
if "email_index" not in st.session_state: st.session_state.email_index = 0
if "current_email" not in st.session_state: st.session_state.current_email = SIMULATION_EMAILS[0]


# --- 4. THE HEADER SECTION ---
col_logo, col_space, col_m1, col_m2, col_m3, col_status = st.columns([2, 1.5, 1, 1, 1, 1])

with col_logo:
    try:
        image = Image.open('logo.png') # Ensure this file exists!
        st.image(image, width=680) 
    except FileNotFoundError:
        st.error("⚠️ logo.png not found.")

# Helper to put label BELOW number
def metric_below(label, value, delta):
    st.markdown(f"""
    <div style="text-align: center;margin-top: 50px">
        <div style="font-size: 34px; font-weight: 700; color: #091E42;">{value} <span style="font-size: 18px; color: #006644; font-weight: 600;">{delta}</span></div>
        <div style="font-size: 22px; font-weight: 600; color: #5E6C84; margin-top: -5px;">{label}</div>
    </div>
    """, unsafe_allow_html=True)

# The Right-aligned Metrics
with col_m1:
    metric_below("Sales", "98.2%", "+0.4%")
with col_m2:
    metric_below("Active POs", "142", "+12")
with col_m3:
    metric_below("ERP Link", "ONLINE", "")

with col_status:
    st.markdown('<div class="online-status">ONLINE</div>', unsafe_allow_html=True)

st.divider()

# --- 5. CENTERED NAVIGATION TABS ---
tab_ops, tab_brain, tab_data = st.tabs(["  📡 LIVE OPERATIONS  ", "  🧠 INTELLIGENCE HUB  ", "  💾 DATA NEXUS  "])

# ==========================================
# === TAB 1: LIVE OPERATIONS ===
# ==========================================
with tab_ops:
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Using 'gap="large"' to separate the work areas
    c_left, c_right = st.columns([1, 1.2], gap="large")
    
    with c_left:
        with st.container(border=True):
            # Header with Simulation Button
            col_head, col_sim = st.columns([2, 1])
            with col_head:
                st.subheader("Incoming Stream")
            with col_sim:
                # BUTTON TO TOSS UP NEW EMAILS
                if st.button("🎲 Simulate Emails", type="secondary", use_container_width=True):
                    # Increment index, loop back to 0 if at end
                    st.session_state.email_index = (st.session_state.email_index + 1) % len(SIMULATION_EMAILS)
                    st.session_state.current_email = SIMULATION_EMAILS[st.session_state.email_index]
                    # Reset analysis when new email comes in
                    st.session_state.risk_analysis = None
                    st.rerun()

            # Dynamic Email Display
            curr = st.session_state.current_email
            st.info(f"📨 **Inbox:** New Message from *{curr['sender']}*\n\n**Subject:** {curr['subject']}")
            
            # Text area bound to state
            email_text = st.text_area("Content:", value=curr['body'], height=150)
            
            if st.button("🔄 ANALYZE & SYNC", type="primary", use_container_width=True):
                # Call the new smart engine logic
                st.session_state.risk_analysis = st.session_state.engine.analyze_risk(email_text)

    with c_right:
        # Result Card (Dynamic)
        if st.session_state.risk_analysis:
            res = st.session_state.risk_analysis
            
            # Dynamic Color based on severity
            box_color = "red" if res['severity'] == "CRITICAL" else "orange" if res['severity'] == "HIGH" else "green"
            
            with st.container(border=True):
                # Dynamic Header
                if box_color == "red": st.error(f"🚨 **{res['title']}**")
                elif box_color == "orange": st.warning(f"⚠️ **{res['title']}**")
                else: st.success(f"✅ **{res['title']}**")
                
                # Dynamic Metrics
                m1, m2 = st.columns(2)
                m1.metric(res['metric_label'], res['metric_val'], delta=res['severity'], delta_color="inverse")
                m2.write(f"**Impact:** {res['impact']}")
                
                st.divider()
                st.markdown("#### Recommended Action")
                
                # Dynamic Buttons
                b1, b2 = st.columns(2)
                if b1.button(res['action_1'], use_container_width=True):
                    st.toast(f"Action '{res['action_1']}' executed successfully!")
                if b2.button(res['action_2'], use_container_width=True):
                    st.session_state.risk_analysis = None # Clear
        else:
            # Idle State
            with st.container(border=True):
                st.success("✅ Operations Normal")
                st.caption("No active threats detected in the supply chain.")

# ==========================================
# === TAB 2: INTELLIGENCE HUB ===
# ==========================================
with tab_brain:
    st.markdown("<br>", unsafe_allow_html=True)
    
    c_chat, c_context = st.columns([2, 1])
    
    with c_chat:
        with st.container(border=True):
            st.markdown("### 💬 Ask Hugo")
            
            # Chat History Container
            chat_box = st.container(height=400)
            with chat_box:
                for msg in st.session_state.messages:
                    st.chat_message(msg["role"]).write(msg["content"])
            
            # Input Area
            if prompt := st.chat_input("Query operations (e.g. 'How many motors do we have?')..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                chat_box.chat_message("user").write(prompt)
                
                # Simulated Response
                response = "Analyzing ERP data..." 
                if "delay" in prompt: response = "Delay impact confirmed: -120 units for PO-FLEET-001."
                elif "motor" in prompt.lower(): response = "Current Stock: 50 Units. Incoming: 0 (Delayed)."
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                chat_box.chat_message("assistant").write(response)
    
    with c_context:
        st.info("💡 **Capabilities:**\n\n- Inventory Checks\n- Risk Assessment\n- Supplier History\n- Demand Forecasting")

# ==========================================
# === TAB 3: DATA NEXUS ===
# ==========================================
with tab_data:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 💾 Live ERP Inventory")
    
    st.dataframe(
        st.session_state.engine.get_stock_status(), 
        use_container_width=True, 
        height=500,
        column_config={
             "Stock": st.column_config.ProgressColumn("Stock Level", format="%d", min_value=0, max_value=200),
             "Status": st.column_config.TextColumn("Health Status"),
        }
    )

# --- 6. FOOTER ---
st.markdown('<div class="footer"><  Developed by Al Amin and Adnan Mohsin @ 2025 ></div>', unsafe_allow_html=True)