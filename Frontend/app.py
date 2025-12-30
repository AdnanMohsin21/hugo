import streamlit as st
import pandas as pd
import sys
import os
from PIL import Image
from datetime import datetime

# ============================================
# 1. SETUP PATHS & BACKEND CONNECTION
# ============================================
# Get the absolute path to the "Backend" folder
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
backend_path = os.path.join(root_dir, 'Backend')

# Add Backend to python path so we can import 'main.py'
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Load environment variables from .env
from pathlib import Path
env_file = Path(backend_path) / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ.setdefault(key, value)

# Import Hugo Agent
HUGO_AVAILABLE = False
try:
    from main import HugoAgent, extract_valid_po_reference
    HUGO_AVAILABLE = True
    print(f"✅ Hugo imported successfully from: {backend_path}")
except Exception as e:
    print(f"❌ Hugo import failed: {e}")
    HUGO_AVAILABLE = False

# ============================================
# 2. SAMPLE EMAIL QUEUE (SCENARIOS)
# ============================================
SAMPLE_EMAILS = [
    {
        "sender": "logistics@acme-motors.com",
        "subject": "Delivery Delay - PO-2025-00001",
        "body": """Dear Procurement Team,

We regret to inform you that Purchase Order PO-2025-00001 for 500W Brushless Motors will be delayed by 14 days.

Original delivery: 2025-02-15
New delivery: 2025-03-01

Reason: Supply chain disruption in semiconductor components.

Best regards,
ACME Motors Logistics"""
    },
    {
        "sender": "warehouse@voltway.co",
        "subject": "URGENT: Warehouse Capacity Alert",
        "body": """Procurement Team,

Current warehouse utilization: 92%

We have excessive inventory levels detected:
- Battery packs: 2,000 units (90 days cover)
- Motor units: 1,500 units (75 days cover)

Safety stock levels are too high. Recommend redistribution.

Warehouse Manager"""
    },
    {
        "sender": "sales@voltway.co",
        "subject": "Stock Conflict: Premium Orders vs Fleet Contract",
        "body": """Procurement Team,

We have a critical priority conflict:

WEBSHOP: 50 Premium S3 scooters ordered (€60,000 revenue, 45% margin)
FLEET CONTRACT: 200 Standard S2 scooters promised (€160,000, 15% margin, penalties for delays)

Parts shortage detected. Only enough inventory for 150 total units this month.

Need priority decision ASAP.

Sales Team"""
    },
    {
        "sender": "operations@voltway.co",
        "subject": "URGENT: Cancel O5021 (Carbon Fiber Frame)",
        "body": """Hello SupC Team,

Please cancel Purchase Order O5021 for Carbon Fiber Frame (part P303).
We’ve decided to delay the V1→V2 upgrade rollout, so we no longer need these frames.

Let me know if there are any cancellation fees. If so, please send an updated invoice.

Thanks,
Jordan Lee
Warehouse Manager
Voltway"""
    },
    {
        "sender": "shipping@supC.com",
        "subject": "Early Partial Shipment for O5075 – 12-inch Alloy Wheel",
        "body": """Hello Voltway Team,

Good news—PO O5075 (12-inch Alloy Wheel, part P330) has partially shipped ahead of schedule.
We’ve dispatched 40 of 60 wheels today via Express Freight (Tracking #XJ123456789).
Expected delivery: 2025-04-18 (instead of the original 2025-04-22).
The remaining 20 units will ship on 2025-04-25.

Cheers,
Elena Rodriguez
Logistics Coordinator
SupC"""
    },
    {
        "sender": "sales@supA.com",
        "subject": "Q2 Discount on S2 V1 Li-Ion 36V 10Ah Battery Pack",
        "body": """Hello Voltway Purchasing,

To support your Q2 ramp-up, we’re offering a 5% discount on the S2 V1 Li-Ion 36V 10Ah Battery Pack (part P309) for any order of 200+ units placed by 2025-05-05.
Regular price: $65.00 → Discounted price: $61.75 ea.
Minimum order qty still applies (50 units).

Let me know if you’d like to set up a blanket PO or discuss scheduling.

Best,
Sonia Patel
Account Executive
SupA"""
    },
    {
        "sender": "qa-team@supA.com",
        "subject": "URGENT: Quality Alert on S3 V2 Carbon Fiber Frame",
        "body": """Hi Engineering Team,

During our final QC check, we identified hairline cracks on several units of the S3 V2 Carbon Fiber Frame (part P323).
Affected batch: PO O5023, shipped 2025-04-10.

We recommend halting assembly on incoming frames from this batch and returning the lot for inspection.
Please advise on next steps for containment and replacement orders.

Regards,
Mark Nguyen
QA Lead
SupA"""
    },
    {
        "sender": "sales@supB.com",
        "subject": "Price Update for Li-Po 48V 12Ah Battery Pack",
        "body": """Hello Voltway Team,

Effective 2025-05-01, the unit price for Li-Po 48V 12Ah Battery Pack (used in all V2 models, part P302) will increase from $78.50 to $85.00.
This is due to raw material cost increases for cobalt and specialized cell coatings.
If you’d like to lock in current pricing for any upcoming orders, please confirm by 2025-04-15.

Regards,
Jin Wu
Account Manager
SupB"""
    }
]

# ============================================
# 3. HELPER FUNCTIONS
# ============================================
def generate_blind_spot_impact(is_blind_spot: bool, change, po_reference: str, matched_po) -> str:
    """Generate impact message for blind spot scenario."""
    if is_blind_spot:
        delay_text = f"{change.delay_days}-day delay" if change.delay_days else "delivery change"
        return f"🚨 BLIND SPOT ALERT: Supplier reports {delay_text} for PO {po_reference}, but this PO is NOT found in ERP system. Manual intervention required to update records and assess impact."
    elif matched_po:
        return f"Supplier reports {change.delay_days}-day delay for PO {matched_po.po_number}. Impact: {change.supplier_reason or 'Supply chain disruption detected. Production may be affected.'}"
    else:
        return "Delivery change detected. Unable to match to purchase order."

# ============================================
# 4. APP CONFIG & SESSION STATE
# ============================================
st.set_page_config(page_title="Hugo AI - Procurement Watchdog", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    .stTabs [data-baseweb="tab-list"] { justify-content: center; width: 100%; gap: 20px; }
    .stTabs [data-baseweb="tab"] { height: 40px; background-color: #F4F5F7; border-radius: 8px; padding: 12px 30px; font-weight: 900; color: #5E6C84; border: 1px solid #dfe1e6; }
    .stTabs [aria-selected="true"] { background-color: #FFFFFF; color: #0052CC; border: 2px solid #0052CC; }
    .footer { width: 100%; text-align: center; padding: 20px; margin-top: 50px; border-top: 1px solid #eaeaea; color: #6B778C; font-size: 14px; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "queue_index" not in st.session_state:
    st.session_state.queue_index = 0
if "current_email" not in st.session_state:
    st.session_state.current_email = SAMPLE_EMAILS[0]
if "processed_alerts" not in st.session_state:
    st.session_state.processed_alerts = []
if "risk_analysis" not in st.session_state:
    st.session_state.risk_analysis = None
if "hoarding_results" not in st.session_state:
    st.session_state.hoarding_results = None
if "priority_conflicts" not in st.session_state:
    st.session_state.priority_conflicts = None

# Initialize Hugo Agent (Cached)
@st.cache_resource
def init_hugo():
    if HUGO_AVAILABLE:
        try:
            agent = HugoAgent(simulation_mode=False)
            print("✅ Hugo Agent initialized")
            return agent
        except Exception as e:
            print(f"❌ Init failed: {e}")
            return None
    return None

if "hugo_agent" not in st.session_state:
    st.session_state.hugo_agent = init_hugo()

# ============================================
# 5. HEADER & METRICS
# ============================================
col_logo, col_space, col_m1, col_m2, col_m3, col_status = st.columns([2, 1.5, 1, 1, 1, 1])

with col_logo:
    try:
        logo_path = os.path.join(current_dir, 'logo.png')
        image = Image.open(logo_path)
        st.image(image, width=400) 
    except:
        st.markdown("### 🤖 HUGO AI")

def metric_below(label, value, delta):
    st.markdown(f"""<div style="text-align: center;margin-top: 50px"><div style="font-size: 34px; font-weight: 700; color: #091E42;">{value}<span style="font-size: 18px; color: #006644; font-weight: 600;">{delta}</span></div><div style="font-size: 22px; font-weight: 600; color: #5E6C84; margin-top: -5px;">{label}</div></div>""", unsafe_allow_html=True)

with col_m1:
    metric_below("Alerts", str(len(st.session_state.processed_alerts)), "+0")
with col_m2:
    po_count = 0
    if st.session_state.hugo_agent:
        try: po_count = len(st.session_state.hugo_agent.get_open_orders())
        except: pass
    metric_below("Active POs", str(po_count), "+0")
with col_m3:
    status = "ONLINE" if HUGO_AVAILABLE and st.session_state.hugo_agent else "OFFLINE"
    metric_below("Hugo Status", status, "")
with col_status:
    color = "#0f2f57" if (HUGO_AVAILABLE and st.session_state.hugo_agent) else "#cc0000"
    st.markdown(f'<div style="text-align: right; margin-top: 50px; font-size: 20px; font-weight: 900; color: {color};">{status}</div>', unsafe_allow_html=True)

st.divider()

# TABS
tab_ops, tab_hoarding, tab_priority, tab_data, tab_hub = st.tabs([
    " 📡 BLIND SPOT ", 
    " 📦 HOARDING ISSUE ", 
    " ⚔️ PRIORITY WARS ", 
    " 💾 DATA NEXUS ",
    " 🧠 INTELLIGENCE HUB " 
])

# ==========================================
# TAB 1: BLIND SPOT DETECTION (QUEUE + SYNCED TEXT AREA)
# ==========================================
with tab_ops:
    st.markdown("### 🔍 Blind Spot Detection")
    st.caption("Detects supplier delays NOT reflected in ERP system using hybrid LLM + deterministic architecture")
    
    c_left, c_right = st.columns([1, 1.2], gap="large")
    
    with c_left:
        with st.container(border=True):
            st.subheader("📨 Incoming Supplier Email")
            
            # --- SIMULATION BUTTON ---
            # FIX: We now force the session_state update for the text area
            if st.button("🎲 Simulate Next Email (Queue)", use_container_width=True):
                # 1. Calculate next index
                current_idx = st.session_state.queue_index
                next_idx = (current_idx + 1) % len(SAMPLE_EMAILS)
                st.session_state.queue_index = next_idx
                
                # 2. Get the new email
                new_email = SAMPLE_EMAILS[next_idx]
                st.session_state.current_email = new_email
                
                # 3. FORCE UPDATE THE TEXT AREA WIDGET
                # This explicitly tells Streamlit: "Change the text box value now!"
                st.session_state["blind_spot_email_input"] = new_email['body']
                
                st.rerun()

            curr = st.session_state.current_email
            st.info(f"**From:** {curr['sender']}\n\n**Subject:** {curr['subject']}")
            
            # --- SYNCED TEXT AREA ---
            # Note: We use the key "blind_spot_email_input" which we updated above
            email_text = st.text_area("Email Content (Editable):", value=curr['body'], height=250, key="blind_spot_email_input")
            
            if st.button("🔄 ANALYZE WITH HUGO AI", type="primary", use_container_width=True):
                if HUGO_AVAILABLE and st.session_state.hugo_agent:
                    with st.spinner("🧠 Hugo analyzing email..."):
                        try:
                            # 1. Regex Extraction
                            po_reference = extract_valid_po_reference(curr['subject'], email_text)
                            
                            # 2. Agent Processing (Sends the TEXT AREA content to backend)
                            alert = st.session_state.hugo_agent.process_single_email_from_text(
                                sender=curr['sender'],
                                subject=curr['subject'],
                                body=email_text 
                            )
                            
                            # 3. Logic for Risk Analysis
                            change = alert.delivery_change
                            risk = alert.risk_assessment
                            has_valid_po = po_reference is not None
                            is_unmapped = alert.matched_po is None
                            is_blind_spot = has_valid_po and is_unmapped
                            
                            if change.detected or is_blind_spot:
                                st.session_state.risk_analysis = {
                                    "type": "blind_spot",
                                    "title": "🚨 BLIND SPOT DETECTED" if is_blind_spot else f"{change.change_type.value.upper()} Detected" if change.change_type else "Change Detected",
                                    "severity": "CRITICAL" if is_blind_spot else ("CRITICAL" if (change.delay_days and change.delay_days >= 7) else "HIGH"),
                                    "delay_days": change.delay_days or 0,
                                    "po_reference": po_reference or "No PO found",
                                    "po_number": alert.matched_po.po_number if alert.matched_po else "❌ NOT IN ERP",
                                    "confidence": f"{change.confidence:.0%}",
                                    "impact": generate_blind_spot_impact(is_blind_spot, change, po_reference, alert.matched_po),
                                    "action_1": "🔄 Update ERP System" if is_blind_spot else "✈️ Expedite Shipment",
                                    "action_2": "📞 Contact Supplier",
                                    "risk_score": risk.risk_score if risk else 0.8,
                                    "recommended_actions": risk.recommended_actions if risk else []
                                }
                                st.session_state.processed_alerts.append(alert)
                                st.success("Analysis Complete")
                            else:
                                st.info("ℹ️ No significant delivery change detected.")
                                st.session_state.risk_analysis = None
                                
                        except Exception as e:
                            st.error(f"❌ Hugo analysis failed: {e}")
                            import traceback
                            st.code(traceback.format_exc())
                else:
                    st.error("❌ Hugo backend offline.")

    with c_right:
        if st.session_state.risk_analysis:
            res = st.session_state.risk_analysis
            with st.container(border=True):
                if res['severity'] == "CRITICAL":
                    st.error(f"🚨 **{res['title']}**")
                else:
                    st.warning(f"⚠️ **{res['title']}**")
                
                m1, m2 = st.columns(2)
                m1.metric("Delay Detected", f"{res['delay_days']} days", delta="CRITICAL")
                
                po_in_erp = res.get('po_number', 'N/A')
                if po_in_erp == "❌ NOT IN ERP":
                    m2.metric("ERP Status", "BLIND SPOT", delta="⚠️ Manual Fix", delta_color="inverse")
                else:
                    m2.metric("Matched PO", po_in_erp)
                
                st.divider()
                st.markdown(f"**Impact:** {res['impact']}")
                
                st.markdown("#### Recommended Actions")
                b1, b2 = st.columns(2)
                if b1.button(res['action_1'], use_container_width=True): st.toast(f"✅ {res['action_1']} initiated!")
                if b2.button(res['action_2'], use_container_width=True): st.toast(f"✅ {res['action_2']} logged!")
        else:
             with st.container(border=True):
                st.info("👈 Click 'Simulate Next Email' then 'Analyze' to begin.")

# ==========================================
# TAB 2: HOARDING ISSUE DETECTION
# ==========================================
with tab_hoarding:
    st.markdown("### 📦 Hoarding Issue Detection")
    st.caption("Identifies excess inventory tying up capital and storage.")
    
    if st.button("🔍 RUN HOARDING ANALYSIS", type="primary", use_container_width=True):
        if HUGO_AVAILABLE and st.session_state.hugo_agent:
            with st.spinner("📊 Analyzing inventory..."):
                try:
                    res = st.session_state.hugo_agent.hoarding_detector.analyze_all_materials()
                    st.session_state.hoarding_results = res
                    st.success(f"Found {len([r for r in res if r.risk_level in ['HIGH', 'MEDIUM']])} at-risk materials")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
        else:
            st.error("❌ Hugo offline")
    
    if st.session_state.hoarding_results:
        results = st.session_state.hoarding_results
        high_risk = [r for r in results if r.risk_level == "HIGH"]
        medium_risk = [r for r in results if r.risk_level == "MEDIUM"]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("🔴 High Risk", len(high_risk), delta="Critical")
        col2.metric("🟡 Medium Risk", len(medium_risk), delta="Warning")
        col3.metric("📦 Total Excess", sum(r.excess_units for r in results), delta="Capital tied")
        
        st.divider()
        if high_risk:
            st.markdown("### 🔴 High Risk Materials")
            for r in high_risk[:5]:
                with st.expander(f"**{r.material}** - Excess: {r.excess_units} units"):
                    st.markdown(f"Confidence: {r.confidence}")

# ==========================================
# TAB 3: PRIORITY WARS
# ==========================================
with tab_priority:
    st.markdown("### ⚔️ Priority Wars Resolution")
    st.caption("Resolves stock allocation conflicts between order types.")
    
    if st.button("⚔️ DETECT PRIORITY CONFLICTS", type="primary", use_container_width=True):
        if HUGO_AVAILABLE and st.session_state.hugo_agent:
            with st.spinner("⚔️ Analyzing conflicts..."):
                try:
                    recommendations = st.session_state.hugo_agent.inventory_balancer.analyze_inventory()
                    conflicts = st.session_state.hugo_agent.inventory_balancer.detect_priority_conflicts(recommendations)
                    st.session_state.priority_conflicts = conflicts
                    if conflicts: st.success(f"Found {len(conflicts)} conflicts")
                    else: st.info("No conflicts detected")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
        else:
            st.error("❌ Hugo offline")
    
    if st.session_state.priority_conflicts:
        conflicts = st.session_state.priority_conflicts
        for idx, conflict in enumerate(conflicts, 1):
            with st.expander(f"Conflict #{idx}: {conflict.material}"):
                st.metric("Shortage", f"{conflict.total_demand - conflict.available_stock} units", delta="Conflict", delta_color="inverse")
                st.write(f"Summary: {conflict.summary}")

# ==========================================
# TAB 4: DATA NEXUS
# ==========================================
with tab_data:
    st.markdown("### 💾 Purchase Orders from CSV")
    if HUGO_AVAILABLE and st.session_state.hugo_agent:
        try:
            orders = st.session_state.hugo_agent.get_open_orders()
            if orders:
                po_data = pd.DataFrame([{
                    "PO": po.po_number, "Supplier": po.supplier_name, "Material": po.material_id, "Qty": po.quantity
                } for po in orders])
                st.dataframe(po_data, use_container_width=True)
            else:
                st.info("No POs found.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    st.divider()
    st.markdown("### 📜 Alert History")
    if st.session_state.processed_alerts:
        alert_data = [{
            "Time": a.processed_at.strftime("%H:%M:%S"),
            "Sender": a.email.sender,
            "Subject": a.email.subject[:40]
        } for a in st.session_state.processed_alerts]
        st.dataframe(pd.DataFrame(alert_data), use_container_width=True)

# ==========================================
# TAB 5: INTELLIGENCE HUB (RAG CHAT)
# ==========================================
with tab_hub:
    st.markdown("### 🧠 Intelligence Hub")
    st.caption("Ask Hugo anything about your supply chain. He uses RAG to retrieve data from your CSVs and emails.")

    # 1. Initialize Chat History
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "Hello! I'm Hugo. Ask me about stock levels, delayed orders, or supplier risks."}
        ]

    # 2. Display Previous Messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 3. Handle User Input
    if prompt := st.chat_input("Ex: 'Do we have enough motors for the next 3 months?'"):
        st.chat_message("user").markdown(prompt)
        st.session_state.chat_history.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            if HUGO_AVAILABLE and st.session_state.hugo_agent:
                with st.spinner("Thinking..."):
                    try:
                        agent = st.session_state.hugo_agent
                        # Tries typical RAG method names
                        if hasattr(agent, 'chat'): response = agent.chat(prompt)
                        elif hasattr(agent, 'ask'): response = agent.ask(prompt)
                        elif hasattr(agent, 'query'): response = agent.query(prompt)
                        else: response = "⚠️ Error: `chat()` method not found in HugoAgent."
                        
                        message_placeholder.markdown(response)
                        full_response = response
                    except Exception as e:
                        full_response = f"❌ Error: {e}"
                        message_placeholder.markdown(full_response)
            else:
                full_response = "❌ Offline."
                message_placeholder.markdown(full_response)
            
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})

# --- FOOTER ---
st.markdown('<div class="footer">< Developed by Al Amin and Adnan Mohsin @ 2025  ></div>', unsafe_allow_html=True)