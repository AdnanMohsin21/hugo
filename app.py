import streamlit as st
import pandas as pd
import time
import json

# --- 1. SETUP & PAGE CONFIG ---
st.set_page_config(
    page_title="Voltway Ops: Hugo Agent",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CONNECTING TO MEMBER A (THE ENGINE) ---
# This block allows you to run even if Member A isn't done yet.
try:
    from logic_core import VoltwayEngine, parse_email_to_json
    HAS_BACKEND = True
except ImportError:
    HAS_BACKEND = False
    st.toast("⚠️ specific logic_core.py not found. Running in Simulation Mode.", icon="🛠️")

    # MOCK CLASSES FOR SIMULATION
    class VoltwayEngine:
        def get_stock_status(self):
            return pd.DataFrame({
                "material_id": ["M-500", "F-200"],
                "name": ["Motor Controller", "Frame Type-A"],
                "current_stock": [50, 20],
                "incoming_date": ["2025-10-30", "2025-11-05"]
            })
        def check_delay_impact(self, mat_id, days):
            # Simulation of a crash
            return {
                "status": "CRITICAL",
                "material": "Motor Controller",
                "shortage_qty": 120,
                "affected_clients": ["Lime Fleet", "Webshop"],
                "impact_msg": f"Critical Stockout! Short by 120 units."
            }
    
    def parse_email_to_json(text):
        time.sleep(1.5) # Fake AI delay
        return {"material_id": "M-500", "delay_days": 14}


# --- 3. SESSION STATE INITIALIZATION ---
if "engine" not in st.session_state:
    st.session_state.engine = VoltwayEngine()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "risk_analysis" not in st.session_state:
    st.session_state.risk_analysis = None

# --- 4. SIDEBAR NAVIGATION ---
st.sidebar.title("⚡ Hugo - AI Procurement Agent")
st.sidebar.caption("v2.1.0 | Connected to ERP")
st.sidebar.markdown("---")
st.sidebar.metric("System Health", "98.2%", "+0.1%")
st.sidebar.metric("Active POs", "142", "5")

# --- 5. MAIN DASHBOARD TABS ---
st.title("🚀 Operations Command Center")

# The "Trinity" Workflow
tab_monitor, tab_chat, tab_data = st.tabs(["📡 Reactive Monitor", "🧠 Analytical Chat", "💾 ERP Data View"])

# === TAB 1: THE BLIND SPOT (REACTIVE INTELLIGENCE) ===
with tab_monitor:
    st.subheader("Live Supply Chain Intelligence")
    
    # A. THE TRIGGER (Supplier Email)
    col_trigger, col_status = st.columns([1, 2])
    
    # ... inside tab_monitor ...
    
    with col_trigger:
        st.info("👇 **Scenario:** Live connection to 'procurement@voltway.com'")
        email_text = st.text_area(
            "Incoming Inbox Stream:", 
            value="From: logistics@maersk.com \nSubject: Shipment #404 Update \n\nUrgent: The container with M-500 Motors is held at customs. Estimated release is in 14 days.",
            height=150
        )
        
        # CHANGED: Professional Button Label
        if st.button("🔄 Analyze & Sync Email", type="primary", help="Parse unstructured text and update ERP database"):
            with st.spinner("Hugo is parsing email context & cross-referencing ERP..."):
                # 1. AI Extraction
                extracted_data = parse_email_to_json(email_text)
                
                # 2. Impact Calculation
                if "error" not in extracted_data:
                    impact = st.session_state.engine.check_delay_impact(
                        extracted_data.get("material_id", "M-500"), 
                        extracted_data.get("delay_days", 0)
                    )
                    st.session_state.risk_analysis = impact
                    st.toast("Sync Complete: ERP Database Updated", icon="✅")
                else:
                    st.error("AI Parse Error")

    # B. THE VISUALIZATION (Risk Card)
    with col_status:
        if st.session_state.risk_analysis:
            res = st.session_state.risk_analysis
            
            if res['status'] == "CRITICAL":
                # ... inside the if res['status'] == "CRITICAL": block ...
        
        # 1. THE CRISIS VISUALS
                st.error(f"🛑 **CRITICAL RISK DETECTED**: {res['material']}")
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Shortage", f"-{res['shortage_qty']} Units")
                m2.metric("Impacted Orders", str(len(res['affected_clients'])))
                m3.metric("Stockout Date", "Oct 29") 
                
                st.write(f"**Affected Clients:** {', '.join(res['affected_clients'])}")
                
                # 2. THE OPERATIONAL DECISION (Pure Business Logic)
                st.markdown("---")
                st.subheader("⚡ Recommended Action")
                
                c1, c2 = st.columns(2)
                
                # Option A: The "Save the Contract" Move
                with c1:
                    st.warning("**Option A: Expedite Air Freight**")
                    st.caption("⏱️ Arrival: **2 Days** (Fixes immediate shortage)")
                    st.write("**Cost:** $5,000 (Expedite Fee)")
                    if st.button("🚀 Authorize Air Freight"):
                        st.toast("Expedite Order Sent. Logistics notified.", icon="✈️")
                
                # Option B: The "Accept Delay" Move
                with c2:
                    st.info("**Option B: Reschedule Production**")
                    st.caption("⏱️ Arrival: **14 Days** (Standard)")
                    st.write("**Impact:** Miss 'Lime Fleet' Deadline")
                    if st.button("📅 Reschedule Production"):
                        st.success("Production Plan Updated. Clients notified of delay.")
                        st.session_state.risk_analysis = None # Clear Alert
            else:
                st.success(f"✅ Analysis Result: {res['impact_msg']}")
        else:
            st.info("System Normal. Monitoring 24/7.")
            # Ghost Mode: Show a healthy progress bar
            st.progress(100, text="Production Line A: Running Smoothly")

# === TAB 2: ANALYTICAL REASONING (CHAT) ===
with tab_chat:
    st.subheader("💬 Ask Hugo")
    st.caption("Example: 'How does the M-500 delay affect the Lime contract?'")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask about inventory..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Simple Rule-Based Response (Vibe Code this later with Vertex AI)
        response = "I am analyzing the latest ERP data..."
        if "Lime" in prompt:
            response = "The **Lime Fleet** order requires 100 units. With the 14-day delay, we will miss their deadline by 4 days unless we switch to Air Freight."
        elif "green" in prompt.lower() or "carbon" in prompt.lower():
            response = "Choosing Rail over Air Freight for this order saves **4,380 kg of CO2**, equivalent to planting 200 trees."
        
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# === TAB 3: DATA INTEGRATION (SOURCE OF TRUTH) ===
with tab_data:
    st.subheader("💾 Live ERP Database")
    st.caption("This data updates in real-time when you approve actions.")
    
    # Show the "Real" Data from Member A
    if HAS_BACKEND:
        df = st.session_state.engine.get_stock_status()
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Backend Logic not connected. Showing Mock Data.")
        st.dataframe(st.session_state.engine.get_stock_status(), use_container_width=True)