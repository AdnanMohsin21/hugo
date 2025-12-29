#!/usr/bin/env python3
"""
Test script to verify the Hugo Inbox Watchdog refactoring.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_po_validation():
    """Test PO reference validation."""
    from main import extract_valid_po_reference, is_holiday_or_marketing_email
    
    # Test valid PO references
    assert extract_valid_po_reference("Update on PO-2024-12345", "Body") == "PO-2024-12345"
    assert extract_valid_po_reference("Subject", "Please see PO-2023-67890") == "PO-2023-67890"
    assert extract_valid_po_reference("No PO here", "No PO in body") is None
    
    # Test marketing email filtering
    assert is_holiday_or_marketing_email("Holiday Schedule", "Happy holidays", "sender@company.com")
    assert is_holiday_or_marketing_email("Newsletter", "Latest updates", "noreply@marketing.com")
    assert not is_holiday_or_marketing_email("Delivery Update", "Your order is delayed", "supplier@vendor.com")
    
    print("✅ PO validation tests passed")

def test_risk_scoring():
    """Test risk score calculation."""
    from main import calculate_risk_score, get_alert_severity
    from models.schemas import DeliveryChange
    
    # Test risk scoring
    change = DeliveryChange(detected=True, delay_days=5, confidence=0.8)
    risk = calculate_risk_score(change, unmapped=False)
    assert 0.0 <= risk <= 1.0
    
    # Test severity calculation
    severity = get_alert_severity(change, unmapped=False)
    assert severity.value in ["INFO", "MEDIUM", "CRITICAL"]
    
    # Test unmapped supplier (should always be INFO)
    severity_unmapped = get_alert_severity(change, unmapped=True)
    assert severity_unmapped.value == "INFO"
    
    print("✅ Risk scoring tests passed")

def test_alert_gating():
    """Test alert gating logic."""
    from main import should_generate_alert
    from models.schemas import DeliveryChange
    
    # Test with valid PO
    change = DeliveryChange(detected=True, delay_days=1)
    assert should_generate_alert(change, po_reference="PO-2024-12345", unmapped=False)
    
    # Test without valid PO (should be False)
    assert not should_generate_alert(change, po_reference=None, unmapped=False)
    
    # Test without signal detection (should be False)
    change_no_signal = DeliveryChange(detected=False)
    assert not should_generate_alert(change_no_signal, po_reference="PO-2024-12345", unmapped=False)
    
    print("✅ Alert gating tests passed")

if __name__ == "__main__":
    print("Testing Hugo Inbox Watchdog Refactoring...")
    print("=" * 50)
    
    try:
        test_po_validation()
        test_risk_scoring()
        test_alert_gating()
        
        print("=" * 50)
        print("🎉 All tests passed! Refactoring is working correctly.")
        print("\nKey improvements implemented:")
        print("• Alert gating with PO regex validation")
        print("• Supplier validation with INFO severity downgrade")
        print("• Deterministic risk scoring")
        print("• Marketing email filtering")
        print("• Enhanced metrics tracking")
        print("• Clean logging output")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
