"""
Test script for Ollama risk assessor function.

Run this when Ollama (gemma:2b) is running on localhost:11434
"""

import json
import sys
from services.ollama_risk_assessor import assess_risk_with_ollama, RiskAssessmentResult


def test_risk_assessment():
    """Test the assess_risk_with_ollama function."""
    
    # Sample email text (delivery change notification)
    email_text = """
    Dear Customer,
    
    We regret to inform you that due to unforeseen supply chain disruptions,
    we will be unable to deliver your order on the originally scheduled date
    of January 15, 2025.
    
    The new estimated delivery date is January 28, 2025 (13 days delay).
    
    We understand the inconvenience this may cause. Please contact us if you
    have any questions or concerns.
    
    Best regards,
    Supplier ABC Corp
    """
    
    # Sample purchase order data
    purchase_order = {
        "po_number": "PO-2025-0042",
        "supplier_name": "Supplier ABC Corp",
        "priority": "high",
        "expected_delivery": "2025-01-15",
        "total_value": 50000,
        "currency": "USD"
    }
    
    # Sample historical context
    historical_context = {
        "supplier_reliability_score": 0.65,
        "past_issues": 3,
        "avg_delay_days": 5.2
    }
    
    # Call the function
    print("Testing assess_risk_with_ollama()...")
    print("-" * 60)
    
    result = assess_risk_with_ollama(
        email_text=email_text,
        purchase_order=purchase_order,
        historical_context=historical_context,
        ollama_url="http://localhost:11434",
        model="gemma:2b"
    )
    
    # Display results
    print(f"Risk Level: {result.risk_level}")
    print(f"Risk Score: {result.risk_score:.2f}")
    print(f"Is Fallback: {result.is_fallback}")
    
    if result.error:
        print(f"Error: {result.error}")
    
    print("\nRisk Drivers:")
    for driver in result.drivers:
        print(f"  - {driver}")
    
    print("\nRecommended Actions:")
    for action in result.recommended_actions:
        print(f"  - {action}")
    
    print("\n" + "-" * 60)
    print(f"Result as dict: {json.dumps(result.to_dict(), indent=2)}")
    
    return result


if __name__ == "__main__":
    try:
        result = test_risk_assessment()
        
        # Verify result structure
        assert result.risk_level in {"low", "medium", "high", "critical"}
        assert 0.0 <= result.risk_score <= 1.0
        assert isinstance(result.drivers, list)
        assert isinstance(result.recommended_actions, list)
        
        print("\n✓ All validations passed!")
        sys.exit(0)
    
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
