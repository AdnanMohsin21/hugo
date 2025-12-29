"""
Integration example: Using assess_risk_with_ollama in the Hugo pipeline

This shows how to integrate the new pure-Ollama risk assessment function
into the existing Hugo agent workflow.
"""

from services.ollama_risk_assessor import assess_risk_with_ollama, RiskAssessmentResult
from models.schemas import DeliveryChange, PurchaseOrder
from typing import Optional


def assess_delivery_risk(
    email_text: str,
    delivery_change: Optional[DeliveryChange] = None,
    purchase_order: Optional[PurchaseOrder] = None,
    supplier_reliability: float = 0.5,
    past_issues: int = 0,
    avg_delay_days: float = 0.0
) -> RiskAssessmentResult:
    """
    Assess risk for a detected delivery change using pure Ollama reasoning.
    
    This is the main integration point for Ollama-powered risk assessment.
    
    Args:
        email_text: Original supplier email content
        delivery_change: Detected delivery change details
        purchase_order: Associated PO information
        supplier_reliability: Historical reliability score (0-1)
        past_issues: Number of past issues with supplier
        avg_delay_days: Average historical delay in days
    
    Returns:
        RiskAssessmentResult with Ollama-determined risk level and actions
    
    Example:
        >>> result = assess_delivery_risk(
        ...     email_text="We must delay shipment 10 days...",
        ...     purchase_order=po,
        ...     supplier_reliability=0.65
        ... )
        >>> print(f"Risk: {result.risk_level}")
        Risk: high
        >>> print(f"Score: {result.risk_score}")
        Score: 0.72
    """
    
    # Build PO context dict
    po_data = None
    if purchase_order:
        po_data = {
            "po_number": purchase_order.po_number,
            "supplier_name": purchase_order.supplier_name,
            "priority": purchase_order.priority,
            "expected_delivery": purchase_order.expected_delivery.isoformat() if purchase_order.expected_delivery else None,
            "total_value": purchase_order.total_value,
            "currency": purchase_order.currency
        }
    
    # Build historical context dict
    history_data = {
        "supplier_reliability_score": supplier_reliability,
        "past_issues": past_issues,
        "avg_delay_days": avg_delay_days
    }
    
    # Call Ollama-powered risk assessment
    # NOTE: Risk level and risk_score are determined entirely by Ollama LLM
    # No Python heuristics involved - pure LLM reasoning
    result = assess_risk_with_ollama(
        email_text=email_text,
        purchase_order=po_data,
        historical_context=history_data,
        ollama_url="http://localhost:11434",
        model="gemma:2b"
    )
    
    return result


# Example usage in main pipeline:
if __name__ == "__main__":
    
    # Simulated delivery change scenario
    email = """
    Subject: Delivery Delay Notice
    
    Hello,
    
    Due to unexpected manufacturing delays at our facility, we will not be able
    to meet the originally scheduled delivery date of January 20, 2025.
    
    Your order will be ready for shipment on February 3, 2025 instead.
    
    We apologize for any inconvenience this may cause.
    
    Best regards,
    Supplier ABC
    """
    
    # Create mock PO
    class MockPO:
        po_number = "PO-2025-1234"
        supplier_name = "Supplier ABC"
        priority = "high"
        expected_delivery = None  # Would be datetime in real scenario
        total_value = 75000
        currency = "USD"
    
    # Assess risk
    print("Assessing delivery risk using Ollama...\n")
    result = assess_delivery_risk(
        email_text=email,
        purchase_order=MockPO(),
        supplier_reliability=0.60,
        past_issues=2,
        avg_delay_days=4.5
    )
    
    # Display results
    print("=" * 60)
    print(f"Risk Level:      {result.risk_level.upper()}")
    print(f"Risk Score:      {result.risk_score:.2f}")
    print(f"Is Fallback:     {result.is_fallback}")
    
    if result.error:
        print(f"Error Message:   {result.error}")
    
    print("\nRisk Drivers:")
    for driver in result.drivers:
        print(f"  • {driver}")
    
    print("\nRecommended Actions:")
    for action in result.recommended_actions:
        print(f"  → {action}")
    
    print("=" * 60)


# NOTES ON INTEGRATION
# ====================
#
# 1. This function returns RiskAssessmentResult instead of RiskAssessment
#    - Simpler structure, pure LLM reasoning
#    - Can be adapted to existing schemas as needed
#
# 2. Risk determination is 100% from Ollama
#    - No Python-side heuristics or rules
#    - Consistent with "all reasoning from LLM" requirement
#
# 3. Graceful degradation on Ollama failure
#    - Returns safe default (MEDIUM risk) with error message
#    - Logged for visibility
#    - is_fallback flag indicates when this happened
#
# 4. Can be called from existing pipeline
#    - Drop-in replacement for rule-based assessment
#    - Works with existing schemas (PurchaseOrder, DeliveryChange)
#    - Maintains compatibility with main agent
#
# 5. No external cloud dependencies
#    - Fully offline-capable
#    - Requires only local Ollama instance
#    - Hackathon-ready configuration
