"""
Test and examples for Hugo Alert Decision module.

Demonstrates intelligent alert triggering based on supplier changes
and operational context.
"""

from services.alert_decision import (
    should_trigger_alert,
    ChangeEvent,
    OperationalContext,
    AlertDecision
)
from datetime import datetime


def test_alert_scenarios():
    """Test alert decision with realistic supplier change scenarios."""
    
    print("=" * 70)
    print("HUGO ALERT DECISION - TEST SCENARIOS")
    print("=" * 70)
    print()
    
    # Scenario 1: Minor delay with good inventory
    print("Scenario 1: Minor Delay with Good Inventory")
    print("-" * 70)
    
    change1 = ChangeEvent(
        change_type="delay",
        delay_days=2,
        affected_items=["NON-CRITICAL-PART"],
        supplier_name="Supplier ABC",
        po_priority="normal",
        order_value=5000
    )
    
    context1 = OperationalContext(
        inventory_level=20.0,  # 20 days of supply
        supplier_reliability_score=0.85,
        days_until_deadline=30,
        alternate_suppliers_available=True
    )
    
    decision1 = should_trigger_alert(change1, context1)
    print(f"Alert Triggered: {decision1.trigger_alert}")
    print(f"Urgency: {decision1.urgency}")
    print(f"Reason: {decision1.reason}")
    print()
    
    # Scenario 2: Critical delay with low inventory
    print("Scenario 2: Critical Order, 10-Day Delay, Low Inventory")
    print("-" * 70)
    
    change2 = ChangeEvent(
        change_type="delay",
        delay_days=10,
        affected_items=["CRITICAL-BATTERY"],
        supplier_name="Supplier XYZ",
        po_priority="critical",
        order_value=50000,
        po_number="PO-2025-001",
        supplier_reason="Manufacturing equipment failure"
    )
    
    context2 = OperationalContext(
        inventory_level=3.0,  # 3 days of supply
        min_inventory_level=5.0,
        supplier_reliability_score=0.60,
        supplier_past_issues=3,
        current_production_rate=100,
        days_until_delivery=10,
        days_until_deadline=12,
        alternate_suppliers_available=False
    )
    
    decision2 = should_trigger_alert(change2, context2)
    print(f"Alert Triggered: {decision2.trigger_alert}")
    print(f"Urgency: {decision2.urgency}")
    print(f"Should Escalate: {decision2.should_escalate}")
    print(f"Reason: {decision2.reason}")
    if decision2.recommended_actions:
        print("Recommended Actions:")
        for action in decision2.recommended_actions:
            print(f"  - {action}")
    print()
    
    # Scenario 3: Early delivery (might not need alert)
    print("Scenario 3: Early Delivery (5 Days)")
    print("-" * 70)
    
    change3 = ChangeEvent(
        change_type="early",
        delay_days=-5,
        affected_items=["STANDARD-PART"],
        supplier_name="Supplier ABC",
        po_priority="normal",
        order_value=10000
    )
    
    context3 = OperationalContext(
        inventory_level=15.0,
        supplier_reliability_score=0.90
    )
    
    decision3 = should_trigger_alert(change3, context3)
    print(f"Alert Triggered: {decision3.trigger_alert}")
    print(f"Urgency: {decision3.urgency}")
    print(f"Reason: {decision3.reason}")
    print()
    
    # Scenario 4: Partial shipment of critical item
    print("Scenario 4: Partial Shipment - 50% Quantity")
    print("-" * 70)
    
    change4 = ChangeEvent(
        change_type="partial_shipment",
        quantity_change=-50,
        affected_items=["CRITICAL-MOTOR"],
        supplier_name="Motor Corp",
        po_priority="high",
        order_value=75000,
        po_number="PO-2025-005"
    )
    
    context4 = OperationalContext(
        inventory_level=2.5,
        current_production_rate=200,
        active_orders_count=8,
        orders_at_risk=3,
        supplier_reliability_score=0.50
    )
    
    decision4 = should_trigger_alert(change4, context4)
    print(f"Alert Triggered: {decision4.trigger_alert}")
    print(f"Urgency: {decision4.urgency}")
    print(f"Should Escalate: {decision4.should_escalate}")
    print(f"Reason: {decision4.reason}")
    print()
    
    # Scenario 5: Cancellation
    print("Scenario 5: Complete Cancellation")
    print("-" * 70)
    
    change5 = ChangeEvent(
        change_type="cancellation",
        affected_items=["CONTROLLER-X"],
        supplier_name="Electronics Inc",
        po_priority="critical",
        order_value=100000,
        po_number="PO-2025-010"
    )
    
    context5 = OperationalContext(
        production_capacity=500,
        current_production_rate=450,
        active_orders_count=15,
        days_until_deadline=7
    )
    
    decision5 = should_trigger_alert(change5, context5)
    print(f"Alert Triggered: {decision5.trigger_alert}")
    print(f"Urgency: {decision5.urgency}")
    print(f"Should Escalate: {decision5.should_escalate}")
    print(f"Reason: {decision5.reason}")
    if decision5.recommended_actions:
        print("Recommended Actions:")
        for action in decision5.recommended_actions:
            print(f"  - {action}")
    print()


def example_integration_with_detector():
    """Example of integrating alert decision with delivery detector."""
    
    print("\n" + "=" * 70)
    print("INTEGRATION EXAMPLE: Detector -> Alert Decision")
    print("=" * 70 + "\n")
    
    # This shows how alert decision would be called from the detector
    
    code = '''
# In DeliveryDetector or processing pipeline:

from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

def process_delivery_change(email, detected_change):
    """Process detected change and decide on alert."""
    
    # Convert detected change to ChangeEvent
    change_event = ChangeEvent(
        change_type=detected_change.change_type.value,
        delay_days=detected_change.delay_days,
        affected_items=detected_change.affected_items,
        supplier_name=detected_change.supplier_name,
        confidence=detected_change.confidence,
        supplier_reason=detected_change.supplier_reason
    )
    
    # Get operational context (from ERP/inventory systems)
    context = OperationalContext(
        inventory_level=get_inventory_level(),
        supplier_reliability_score=get_supplier_score(detected_change.supplier_name),
        days_until_deadline=calculate_days_until_deadline(),
        # ... other context fields
    )
    
    # Ask Ollama if this warrants an alert
    decision = should_trigger_alert(change_event, context)
    
    # Handle decision
    if decision.trigger_alert:
        if decision.urgency == "critical":
            escalate_to_management(decision)
        else:
            notify_operations(decision)
        
        # Log for audit
        log_alert_decision(detected_change, decision)
    else:
        # Monitor but don't alert
        log_monitoring_event(detected_change, decision)
    
    return decision
'''
    
    print(code)


def example_high_level_flow():
    """Show high-level flow of alert decision in pipeline."""
    
    print("\n" + "=" * 70)
    print("HIGH-LEVEL ALERT PIPELINE FLOW")
    print("=" * 70 + "\n")
    
    flow = '''
┌────────────────────────────────┐
│  Email from Supplier            │
└───────────┬──────────────────────┘
            │
            ▼
┌────────────────────────────────┐
│  DeliveryDetector (Ollama)      │
│  Extract: change_type,          │
│          delay_days, items, etc │
└───────────┬──────────────────────┘
            │
            ▼
┌────────────────────────────────┐
│  ChangeEvent Created            │
└───────────┬──────────────────────┘
            │
            ▼
┌────────────────────────────────┐
│  Gather OperationalContext      │
│  - Inventory levels             │
│  - Production capacity          │
│  - Supplier history             │
│  - Order deadlines              │
└───────────┬──────────────────────┘
            │
            ▼
┌────────────────────────────────┐
│  should_trigger_alert()         │
│  (Ollama evaluates impact)      │
└───────────┬──────────────────────┘
            │
            ▼
┌────────────────────────────────┐
│  AlertDecision                  │
│  - trigger_alert: bool          │
│  - urgency: low|med|high|crit   │
│  - reason: explanation          │
│  - recommended_actions: list    │
└───────────┬──────────────────────┘
            │
      ┌─────┴─────┐
      │            │
      ▼            ▼
   ALERT       MONITOR
  Trigger     (No Action)
  ├─ Send notification
  ├─ Log event
  └─ Escalate if critical
'''
    
    print(flow)


if __name__ == "__main__":
    print("\nNOTE: This test requires Ollama running on localhost:11434")
    print("Start Ollama with: ollama run gemma:2b\n")
    
    try:
        test_alert_scenarios()
        example_integration_with_detector()
        example_high_level_flow()
    except Exception as e:
        print(f"Test failed (Ollama likely not running): {e}")
        print("\nTo run tests, start Ollama first:")
        print("  $ ollama run gemma:2b")
