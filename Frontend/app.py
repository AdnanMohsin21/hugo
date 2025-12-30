import streamlit as st
import pandas as pd
import sys
import os
from PIL import Image
from datetime import datetime

# ============================================
# BACKEND INTEGRATION - PRODUCTION READY
# ============================================
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_path = os.path.join(parent_dir, 'Backend')

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

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
HugoAgent = None

try:
    from main import HugoAgent, extract_valid_po_reference
    HUGO_AVAILABLE = True
    print(f"✅ Hugo imported successfully from: {backend_path}")
except Exception as e:
    print(f"❌ Hugo import failed: {e}")
    import traceback
    traceback.print_exc()
    HUGO_AVAILABLE = False

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Hugo AI - Procurement Watchdog",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    .stTabs [data-baseweb="tab-list"] { justify-content: center; width: 100%; gap: 20px; }
    .stTabs [data-baseweb="tab"] {
        height: 40px; background-color: #F4F5F7; border-radius: 8px;
        padding: 12px 30px; font-size: 1.3rem; font-weight: 900;
        color: #5E6C84; border: 1px solid #dfe1e6;
        box-shadow: 0px 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF; color: #0052CC;
        border: 2px solid #0052CC; box-shadow: 0px 4px 8px rgba(0,82,204,0.15);
    }
    .footer {
        width: 100%; text-align: center; padding: 20px; margin-top: 50px;
        border-top: 1px solid #eaeaea; color: #6B778C; font-size: 14px; font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# --- SCENARIO EMAILS ---
BLIND_SPOT_EMAIL = {
    "sender": "logistics@acme-motors.com",
    "subject": "Delivery Delay - PO-2025-00001",
    "body": """Dear Procurement Team,

We regret to inform you that Purchase Order PO-2025-00001 for 500W Brushless Motors will be delayed by 14 days.

Original delivery: 2025-02-15
New delivery: 2025-03-01

Reason: Supply chain disruption in semiconductor components.

Best regards,
ACME Motors Logistics"""
}

HOARDING_EMAIL = {
    "sender": "warehouse@voltway.co",
    "subject": "URGENT: Warehouse Capacity Alert",
    "body": """Procurement Team,

Current warehouse utilization: 92%

We have excessive inventory levels detected:
- Battery packs: 2,000 units (90 days cover)
- Motor units: 1,500 units (75 days cover)

Safety stock levels are too high. Recommend redistribution.

Warehouse Manager"""
}

PRIORITY_WARS_EMAIL = {
    "sender": "sales@voltway.co",
    "subject": "Stock Conflict: Premium Orders vs Fleet Contract",
    "body": """Procurement Team,

We have a critical priority conflict:

WEBSHOP: 50 Premium S3 scooters ordered (€60,000 revenue, 45% margin)
FLEET CONTRACT: 200 Standard S2 scooters promised (€160,000, 15% margin, penalties for delays)

Parts shortage detected. Only enough inventory for 150 total units this month.

Need priority decision ASAP.

Sales Team"""
}

# --- HELPER FUNCTIONS ---
def generate_blind_spot_impact(is_blind_spot: bool, change, po_reference: str, matched_po) -> str:
    """Generate impact message for blind spot scenario."""
    if is_blind_spot:
        delay_text = f"{change.delay_days}-day delay" if change.delay_days else "delivery change"
        return f"🚨 BLIND SPOT ALERT: Supplier reports {delay_text} for PO {po_reference}, but this PO is NOT found in ERP system. Manual intervention required to update records and assess impact."
    elif matched_po:
        return f"Supplier reports {change.delay_days}-day delay for PO {matched_po.po_number}. Impact: {change.supplier_reason or 'Supply chain disruption detected. Production may be affected.'}"
    else:
        return "Delivery change detected. Unable to match to purchase order."

# --- INITIALIZE HUGO ---
@st.cache_resource
def init_hugo():
    """Initialize Hugo Agent with simulation mode for demo."""
    if HUGO_AVAILABLE:
        try:
            # Use simulation mode with mock data
            agent = HugoAgent(simulation_mode=False)
            print("✅ Hugo Agent initialized")
            return agent
        except Exception as e:
            print(f"❌ Init failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    return None

# --- SESSION STATE ---
if "hugo_agent" not in st.session_state: 
    st.session_state.hugo_agent = init_hugo()
if "messages" not in st.session_state: 
    st.session_state.messages = []
if "risk_analysis" not in st.session_state: 
    st.session_state.risk_analysis = None
if "current_scenario" not in st.session_state: 
    st.session_state.current_scenario = "Blind Spot"
if "current_email" not in st.session_state: 
    st.session_state.current_email = BLIND_SPOT_EMAIL
if "processed_alerts" not in st.session_state:
    st.session_state.processed_alerts = []
if "hoarding_results" not in st.session_state:
    st.session_state.hoarding_results = None
if "priority_conflicts" not in st.session_state:
    st.session_state.priority_conflicts = None

# --- HEADER ---
col_logo, col_space, col_m1, col_m2, col_m3, col_status = st.columns([2, 1.5, 1, 1, 1, 1])

with col_logo:
    try:
        image = Image.open('logo.png')
        st.image(image, width=680) 
    except:
        st.markdown("### 🤖 HUGO AI - Procurement Watchdog")

def metric_below(label, value, delta):
    st.markdown(f"""
    <div style="text-align: center;margin-top: 50px">
        <div style="font-size: 34px; font-weight: 700; color: #091E42;">{value} 
        <span style="font-size: 18px; color: #006644; font-weight: 600;">{delta}</span></div>
        <div style="font-size: 22px; font-weight: 600; color: #5E6C84; margin-top: -5px;">{label}</div>
    </div>
    """, unsafe_allow_html=True)

with col_m1:
    metric_below("Alerts", str(len(st.session_state.processed_alerts)), "+0")

with col_m2:
    po_count = 0
    if st.session_state.hugo_agent:
        try:
            po_count = len(st.session_state.hugo_agent.get_open_orders())
        except:
            pass
    metric_below("Active POs", str(po_count), "+0")

with col_m3:
    status = "ONLINE" if HUGO_AVAILABLE and st.session_state.hugo_agent else "OFFLINE"
    metric_below("Hugo Status", status, "")

with col_status:
    color = "#0f2f57" if (HUGO_AVAILABLE and st.session_state.hugo_agent) else "#cc0000"
    st.markdown(f'<div style="text-align: right; margin-top: 50px; font-size: 20px; font-weight: 900; color: {color};">{status}</div>', unsafe_allow_html=True)

st.divider()

# --- TABS ---
tab_ops, tab_hoarding, tab_priority, tab_data = st.tabs([
    "  📡 BLIND SPOT  ", 
    "  📦 HOARDING ISSUE  ", 
    "  ⚔️ PRIORITY WARS  ", 
    "  💾 DATA NEXUS  "
])

# ==========================================
# TAB 1: BLIND SPOT DETECTION
# ==========================================
with tab_ops:
    st.markdown("### 🔍 Blind Spot Detection")
    st.caption("Detects supplier delays NOT reflected in ERP system using hybrid LLM + deterministic architecture")
    
    c_left, c_right = st.columns([1, 1.2], gap="large")
    
    with c_left:
        with st.container(border=True):
            st.subheader("📨 Incoming Supplier Email")
            
            curr = BLIND_SPOT_EMAIL
            st.info(f"**From:** {curr['sender']}\n\n**Subject:** {curr['subject']}")
            
            email_text = st.text_area("Email Content:", value=curr['body'], height=200, key="blind_spot_email")
            
            if st.button("🔄 ANALYZE WITH HUGO AI", type="primary", use_container_width=True):
                if HUGO_AVAILABLE and st.session_state.hugo_agent:
                    with st.spinner("🧠 Hugo analyzing email (LLM signal extraction + deterministic logic)..."):
                        try:
                            # Extract PO reference using Hugo's regex
                            po_reference = extract_valid_po_reference(curr['subject'], email_text)
                            
                            # Process email through Hugo's pipeline
                            alert = st.session_state.hugo_agent.process_single_email_from_text(
                                sender=curr['sender'],
                                subject=curr['subject'],
                                body=email_text
                            )
                            
                            change = alert.delivery_change
                            risk = alert.risk_assessment
                            
                            # Check if this is a blind spot
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
                                st.success("✅ Analysis complete! Blind spot detected." if is_blind_spot else "✅ Analysis complete!")
                            else:
                                st.info("ℹ️ No significant delivery change detected.")
                                st.session_state.risk_analysis = None
                                
                        except Exception as e:
                            st.error(f"❌ Hugo analysis failed: {e}")
                            with st.expander("🐛 See error details"):
                                import traceback
                                st.code(traceback.format_exc())
                else:
                    st.error("❌ Hugo backend offline. Check terminal for errors.")
                    st.code(f"Backend path: {backend_path}")

    with c_right:
        if st.session_state.risk_analysis and st.session_state.risk_analysis.get("type") == "blind_spot":
            res = st.session_state.risk_analysis
            
            with st.container(border=True):
                if res['severity'] == "CRITICAL":
                    st.error(f"🚨 **{res['title']}**")
                else:
                    st.warning(f"⚠️ **{res['title']}**")
                
                m1, m2 = st.columns(2)
                m1.metric("Delay Detected", f"{res['delay_days']} days", delta="CRITICAL")
                
                # Show blind spot status
                po_in_erp = res.get('po_number', 'N/A')
                if po_in_erp == "❌ NOT IN ERP":
                    m2.metric("ERP Status", "BLIND SPOT", delta="⚠️ Manual Fix Required", delta_color="inverse")
                else:
                    m2.metric("Matched PO", po_in_erp)
                
                st.caption(f"**PO Reference in Email:** {res.get('po_reference', 'None')} | **Detection Confidence:** {res.get('confidence', 'N/A')}")
                
                st.divider()
                st.markdown(f"**Impact:** {res['impact']}")
                
                st.markdown("#### Recommended Actions")
                b1, b2 = st.columns(2)
                if b1.button(res['action_1'], use_container_width=True, key="bs_a1"):
                    st.toast(f"✅ {res['action_1']} initiated!")
                if b2.button(res['action_2'], use_container_width=True, key="bs_a2"):
                    st.toast(f"✅ {res['action_2']} logged!")
        else:
            with st.container(border=True):
                st.success("✅ No Blind Spots Detected")
                st.caption("All supplier communications are tracked in ERP system.")
                st.info("💡 **What is a Blind Spot?**\n\nA blind spot occurs when a supplier mentions a valid PO number in their email (e.g., PO-2025-00001), but this PO is not found in your ERP system. This indicates a data synchronization issue requiring manual intervention.")

# ==========================================
# TAB 2: HOARDING ISSUE DETECTION
# ==========================================
with tab_hoarding:
    st.markdown("### 📦 Hoarding Issue Detection")
    st.caption("Identifies excess inventory tying up capital and storage using statistical analysis of demand vs stock")
    
    if st.button("🔍 RUN HOARDING ANALYSIS", type="primary", use_container_width=True, key="hoarding_btn"):
        if HUGO_AVAILABLE and st.session_state.hugo_agent:
            with st.spinner("📊 Analyzing inventory levels across all materials..."):
                try:
                    hoarding_results = st.session_state.hugo_agent.hoarding_detector.analyze_all_materials()
                    st.session_state.hoarding_results = hoarding_results
                    
                    high_medium = len([r for r in hoarding_results if r.risk_level in ['HIGH', 'MEDIUM']])
                    st.success(f"✅ Analysis complete! Found {high_medium} at-risk materials")
                except Exception as e:
                    st.error(f"❌ Analysis failed: {e}")
                    with st.expander("🐛 See error details"):
                        import traceback
                        st.code(traceback.format_exc())
        else:
            st.error("❌ Hugo offline")
    
    if st.session_state.hoarding_results:
        results = st.session_state.hoarding_results
        
        # Filter by risk
        high_risk = [r for r in results if r.risk_level == "HIGH"]
        medium_risk = [r for r in results if r.risk_level == "MEDIUM"]
        low_risk = [r for r in results if r.risk_level == "LOW"]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("🔴 High Risk", len(high_risk), delta="Critical")
        col2.metric("🟡 Medium Risk", len(medium_risk), delta="Warning")
        col3.metric("📦 Total Excess", sum(r.excess_units for r in results), delta="Capital tied")
        
        st.divider()
        
        # High risk materials
        if high_risk:
            st.markdown("### 🔴 High Risk Materials")
            for result in high_risk[:5]:
                with st.expander(f"**{result.material}** - Excess: {result.excess_units} units"):
                    actions = st.session_state.hugo_agent.hoarding_detector.get_redistribution_actions(result)
                    col_a, col_b = st.columns(2)
                    col_a.metric("Risk Level", result.risk_level)
                    col_b.metric("Confidence", result.confidence)
                    col_a.metric("Excess Units", result.excess_units)
                    
                    st.markdown("**Recommended Actions:**")
                    for action in actions[:3]:
                        st.markdown(f"- {action}")
        
        # Medium risk
        if medium_risk:
            st.markdown("### 🟡 Medium Risk Materials")
            medium_data = pd.DataFrame([{
                "Material": r.material,
                "Excess Units": r.excess_units,
                "Confidence": r.confidence
            } for r in medium_risk[:10]])
            st.dataframe(medium_data, use_container_width=True)

# ==========================================
# TAB 3: PRIORITY WARS
# ==========================================
with tab_priority:
    st.markdown("### ⚔️ Priority Wars Resolution")
    st.caption("Resolves stock allocation conflicts between order types using BOM-based part demand calculation")
    
    if st.button("⚔️ DETECT PRIORITY CONFLICTS", type="primary", use_container_width=True, key="priority_btn"):
        if HUGO_AVAILABLE and st.session_state.hugo_agent:
            with st.spinner("⚔️ Analyzing order conflicts with BOM mapping..."):
                try:
                    # Run inventory balancer
                    recommendations = st.session_state.hugo_agent.inventory_balancer.analyze_inventory()
                    
                    # Detect conflicts
                    conflicts = st.session_state.hugo_agent.inventory_balancer.detect_priority_conflicts(recommendations)
                    st.session_state.priority_conflicts = conflicts
                    
                    if conflicts:
                        st.success(f"✅ Found {len(conflicts)} priority conflicts")
                    else:
                        st.info("ℹ️ No priority conflicts detected - all orders can be fulfilled")
                except Exception as e:
                    st.error(f"❌ Analysis failed: {e}")
                    with st.expander("🐛 See error details"):
                        import traceback
                        st.code(traceback.format_exc())
        else:
            st.error("❌ Hugo offline")
    
    if st.session_state.priority_conflicts:
        conflicts = st.session_state.priority_conflicts
        
        st.markdown(f"### Found {len(conflicts)} Priority Conflicts")
        st.info("**Priority Rules:** Fleet Framework > Fleet Spot > Webshop")
        
        for idx, conflict in enumerate(conflicts, 1):
            with st.expander(f"⚔️ Conflict #{idx}: Part **{conflict.material}**"):
                col_metric1, col_metric2, col_metric3 = st.columns(3)
                col_metric1.metric("Total Demand", f"{conflict.total_demand} units")
                col_metric2.metric("Available Stock", f"{conflict.available_stock} units")
                shortage = conflict.total_demand - conflict.available_stock
                col_metric3.metric("Shortage", f"{shortage} units", delta="⚠️ Conflict", delta_color="inverse")
                
                st.divider()
                
                allocation = conflict.allocation
                fulfilled = allocation.get("fulfilled", [])
                delayed = allocation.get("delayed", [])
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**✅ WINNERS (Fulfilled Orders)**")
                    if fulfilled:
                        for order in fulfilled[:5]:
                            st.success(f"🏆 Order `{order.order_id}` ({order.order_type}): **{order.allocated_quantity} units**")
                        if len(fulfilled) > 5:
                            st.caption(f"... and {len(fulfilled) - 5} more fulfilled orders")
                    else:
                        st.info("None")
                
                with col2:
                    st.markdown("**❌ LOSERS (Delayed Orders)**")
                    if delayed:
                        for order in delayed[:5]:
                            st.error(f"💔 Order `{order.order_id}` ({order.order_type}): **DELAYED**")
                        if len(delayed) > 5:
                            st.caption(f"... and {len(delayed) - 5} more delayed orders")
                    else:
                        st.success("None - All orders fulfilled! 🎉")
                
                st.divider()
                st.caption(f"**Summary:** {conflict.summary}")

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
                    "PO Number": po.po_number,
                    "Supplier": po.supplier_name,
                    "Material": po.material_id,
                    "Quantity": po.quantity,
                    "Priority": po.priority.upper()
                } for po in orders])
                
                st.dataframe(po_data, use_container_width=True, height=400)
                st.caption(f"📊 Loaded {len(orders)} purchase orders from `material_orders.csv`")
            else:
                st.info("No purchase orders found in CSV. Check `Backend/hugo_data_samples/material_orders.csv`")
        except Exception as e:
            st.error(f"Error loading PO data: {e}")
    else:
        st.warning("Backend offline - cannot load purchase orders.")
    
    st.divider()
    
    # Show alert history
    st.markdown("### 📜 Alert History")
    if st.session_state.processed_alerts:
        alert_data = []
        for alert in st.session_state.processed_alerts:
            alert_data.append({
                "Time": alert.processed_at.strftime("%H:%M:%S"),
                "Sender": alert.email.sender,
                "Subject": alert.email.subject[:50],
                "Type": alert.delivery_change.change_type.value if alert.delivery_change.change_type else "N/A",
                "Risk": alert.risk_assessment.risk_level.value.upper() if alert.risk_assessment else "N/A"
            })
        df = pd.DataFrame(alert_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No alerts processed yet. Analyze an email in the Blind Spot tab to generate alerts.")

# --- FOOTER ---
st.markdown('<div class="footer">< Developed by Al Amin and Adnan Mohsin @ 2025 - Powered by Hugo AI | Hybrid LLM + Deterministic Architecture ></div>', unsafe_allow_html=True)