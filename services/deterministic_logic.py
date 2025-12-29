"""
Hugo - Deterministic Logic Service

Python-based deterministic calculations, risk scoring, and alert generation.
LLMs are constrained to semantic understanding only. All decisions are deterministic.

This module contains ALL business logic - calculations, risk scores, alerts, metrics.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
import re

from models.schemas import (
    Signal, DeliveryChange, ChangeType, RiskAssessment, RiskLevel,
    PurchaseOrder, HistoricalContext, UrgencyLevel, CommitmentConfidence, SupplierSentiment
)
from utils.helpers import setup_logging

logger = setup_logging()

# LLMs are constrained to semantic understanding only. All decisions are deterministic.


def calculate_delay_days(
    signal: Signal,
    po: Optional[PurchaseOrder],
    email_body: str,
    today: datetime
) -> Optional[int]:
    """
    Calculate delay days deterministically from signal and context.
    
    Args:
        signal: Semantic signals from LLM
        po: Purchase order with expected delivery date
        email_body: Email body text for date extraction
        today: Current date
    
    Returns:
        Delay days (positive=delay, negative=early, None if cannot determine)
    """
    if not signal.eta_changed and not signal.delay_mentioned:
        return None
    
    # Try to extract dates from email body
    date_patterns = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY or DD/MM/YYYY
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',  # YYYY-MM-DD
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}',
    ]
    
    dates_found = []
    for pattern in date_patterns:
        matches = re.findall(pattern, email_body.lower())
        dates_found.extend(matches)
    
    # If we have PO expected date and found dates, calculate difference
    if po and po.expected_delivery and dates_found:
        try:
            # Try to parse first date found
            # Simple heuristic: if delay_mentioned and eta_changed, likely a delay
            if signal.delay_mentioned and signal.eta_changed:
                # Conservative estimate: if weak commitment, assume longer delay
                if signal.commitment_confidence == CommitmentConfidence.WEAK:
                    return 7  # Conservative delay estimate
                elif signal.commitment_confidence == CommitmentConfidence.MEDIUM:
                    return 3
                else:
                    return 1
        except Exception:
            pass
    
    # If urgency is high and delay mentioned, assume significant delay
    if signal.urgency_level == UrgencyLevel.HIGH and signal.delay_mentioned:
        return 7
    
    # If delay mentioned but no specific date, use conservative default
    if signal.delay_mentioned:
        # CRITICAL: Default to 1 day if delay detected but no date provided
        return 1
    
    return None


def calculate_quantity_change(
    signal: Signal,
    email_body: str
) -> Optional[int]:
    """
    Calculate quantity change deterministically from signal and email text.
    
    Args:
        signal: Semantic signals from LLM
        email_body: Email body text
    
    Returns:
        Quantity change (positive=increase, negative=decrease, None if cannot determine)
    """
    if not signal.quantity_change_mentioned:
        return None
    
    # Extract numeric quantities from email
    patterns = [
        r'reduced?\s+by\s+(\d+)',
        r'decreased?\s+by\s+(\d+)',
        r'increased?\s+by\s+(\d+)',
        r'(\d+)\s+less',
        r'(\d+)\s+more',
        r'quantity.*?(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, email_body.lower())
        if match:
            value = int(match.group(1))
            if 'reduc' in pattern or 'decreas' in pattern or 'less' in pattern:
                return -value
            elif 'increas' in pattern or 'more' in pattern:
                return value
            else:
                # Default: if negative sentiment, assume reduction
                if signal.supplier_sentiment == SupplierSentiment.NEGATIVE:
                    return -value
                return value
    
    # If quantity change mentioned but no number found, use signal-based estimate
    if signal.supplier_sentiment == SupplierSentiment.NEGATIVE:
        return -10  # Conservative reduction estimate
    elif signal.supplier_sentiment == SupplierSentiment.POSITIVE:
        return 10  # Conservative increase estimate
    
    return None


def compute_risk_score(
    signal: Signal,
    delay_days: Optional[int],
    quantity_change: Optional[int],
    po: Optional[PurchaseOrder],
    context: Optional[HistoricalContext]
) -> float:
    """
    Compute risk score deterministically from signals and context.
    
    Risk score rules:
    - delay_mentioned + weak commitment = higher risk
    - urgency high + ambiguity = higher risk
    - sentiment negative increases risk
    - Historical reliability affects score
    
    Args:
        signal: Semantic signals
        delay_days: Calculated delay days
        quantity_change: Calculated quantity change
        po: Purchase order
        context: Historical context
    
    Returns:
        Risk score between 0.0 and 1.0
    """
    base_score = 0.0
    
    # Signal-based risk factors
    if signal.delay_mentioned:
        base_score += 0.3
    
    if signal.quantity_change_mentioned:
        base_score += 0.2
    
    if signal.eta_changed:
        base_score += 0.15
    
    # Commitment confidence affects risk
    if signal.commitment_confidence == CommitmentConfidence.WEAK:
        base_score += 0.2
    elif signal.commitment_confidence == CommitmentConfidence.MEDIUM:
        base_score += 0.1
    
    # Urgency level affects risk
    if signal.urgency_level == UrgencyLevel.HIGH:
        base_score += 0.2
    elif signal.urgency_level == UrgencyLevel.MEDIUM:
        base_score += 0.1
    
    # Ambiguity increases risk
    if signal.ambiguity_detected:
        base_score += 0.15
    
    # Sentiment affects risk
    if signal.supplier_sentiment == SupplierSentiment.NEGATIVE:
        base_score += 0.15
    elif signal.supplier_sentiment == SupplierSentiment.POSITIVE:
        base_score -= 0.1
    
    # Delay days multiplier
    if delay_days is not None:
        if delay_days >= 7:
            base_score += 0.3
        elif delay_days >= 3:
            base_score += 0.2
        elif delay_days > 0:
            base_score += 0.1
    
    # Quantity change multiplier
    if quantity_change is not None and quantity_change < 0:
        abs_change = abs(quantity_change)
        if abs_change >= 20:
            base_score += 0.25
        elif abs_change >= 10:
            base_score += 0.15
        else:
            base_score += 0.1
    
    # PO priority affects risk
    if po and po.priority == "critical":
        base_score += 0.2
    elif po and po.priority == "high":
        base_score += 0.1
    
    # Historical reliability affects risk
    if context:
        reliability_factor = 1.0 - context.supplier_reliability_score
        base_score += reliability_factor * 0.2
        
        if context.total_past_issues > 5:
            base_score += 0.1
    
    # Normalize to 0.0-1.0 range
    risk_score = min(max(base_score, 0.0), 1.0)
    
    return risk_score


def classify_risk_level(risk_score: float) -> RiskLevel:
    """
    Classify risk level from risk score.
    
    Args:
        risk_score: Risk score between 0.0 and 1.0
    
    Returns:
        RiskLevel enum
    """
    if risk_score >= 0.75:
        return RiskLevel.CRITICAL
    elif risk_score >= 0.55:
        return RiskLevel.HIGH
    elif risk_score >= 0.35:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def build_delivery_change(
    signal: Signal,
    delay_days: Optional[int],
    quantity_change: Optional[int],
    email_body: str,
    po: Optional[PurchaseOrder]
) -> DeliveryChange:
    """
    Build DeliveryChange object from signals and calculated values.
    
    Args:
        signal: Semantic signals
        delay_days: Calculated delay days
        quantity_change: Calculated quantity change
        email_body: Email body
        po: Purchase order
    
    Returns:
        DeliveryChange object
    """
    # Determine if change detected
    detected = (
        signal.delay_mentioned or
        signal.quantity_change_mentioned or
        signal.eta_changed
    )
    
    # Determine change type
    change_type = None
    if delay_days is not None:
        if delay_days > 0:
            change_type = ChangeType.DELAY
        elif delay_days < 0:
            change_type = ChangeType.EARLY
    elif quantity_change is not None:
        change_type = ChangeType.QUANTITY_CHANGE
    elif detected:
        change_type = ChangeType.OTHER
    
    # Calculate confidence from signal
    confidence = 0.5  # Base confidence
    if signal.commitment_confidence == CommitmentConfidence.STRONG:
        confidence = 0.9
    elif signal.commitment_confidence == CommitmentConfidence.MEDIUM:
        confidence = 0.7
    else:
        confidence = 0.5
    
    if signal.ambiguity_detected:
        confidence *= 0.7  # Reduce confidence if ambiguous
    
    # Extract affected items (simple keyword-based)
    affected_items = []
    item_keywords = ['item', 'sku', 'part', 'product', 'component']
    for keyword in item_keywords:
        pattern = rf'{keyword}\s+([A-Z0-9-]+)'
        matches = re.findall(pattern, email_body, re.IGNORECASE)
        affected_items.extend(matches[:5])  # Limit to 5 items
    
    # Extract PO reference
    po_reference = None
    if po:
        po_reference = po.po_number
    else:
        # Try to extract from email
        po_pattern = r'PO[#:\s]*([A-Z0-9-]+)'
        match = re.search(po_pattern, email_body, re.IGNORECASE)
        if match:
            po_reference = match.group(1)
    
    return DeliveryChange(
        detected=detected,
        change_type=change_type,
        original_date=None,
        new_date=None,
        delay_days=delay_days,
        affected_items=list(set(affected_items)),  # Remove duplicates
        quantity_change=quantity_change,
        supplier_reason=None,  # Not extracted in signal-based approach
        po_reference=po_reference,
        confidence=confidence,
        raw_extract=f"signals: delay={signal.delay_mentioned}, qty={signal.quantity_change_mentioned}, eta={signal.eta_changed}"
    )


def build_risk_assessment(
    signal: Signal,
    delay_days: Optional[int],
    quantity_change: Optional[int],
    risk_score: float,
    risk_level: RiskLevel,
    po: Optional[PurchaseOrder],
    context: Optional[HistoricalContext]
) -> RiskAssessment:
    """
    Build RiskAssessment object from calculated values.
    
    Args:
        signal: Semantic signals
        delay_days: Calculated delay days
        quantity_change: Calculated quantity change
        risk_score: Computed risk score
        risk_level: Classified risk level
        po: Purchase order
        context: Historical context
    
    Returns:
        RiskAssessment object
    """
    # Generate impact summary
    impact_parts = []
    if delay_days and delay_days > 0:
        impact_parts.append(f"{delay_days} day delay")
    if quantity_change and quantity_change < 0:
        impact_parts.append(f"quantity reduction of {abs(quantity_change)}")
    if signal.urgency_level == UrgencyLevel.HIGH:
        impact_parts.append("high urgency")
    
    impact_summary = "Operational impact detected. " + ", ".join(impact_parts) if impact_parts else "Minor operational impact expected."
    
    # Determine affected operations
    affected_ops = ["Supply Chain"]
    if delay_days and delay_days >= 3:
        affected_ops.append("Production Planning")
    if po and po.priority in ["critical", "high"]:
        affected_ops.append("Operations Management")
    
    # Generate recommended actions
    actions = []
    if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
        actions.append("Contact supplier immediately")
        actions.append("Assess alternative suppliers")
        actions.append("Notify production planning")
    elif risk_level == RiskLevel.MEDIUM:
        actions.append("Monitor situation closely")
        actions.append("Document supplier communication")
    else:
        actions.append("Acknowledge and track change")
    
    # Calculate urgency hours
    urgency_hours = None
    if risk_level == RiskLevel.CRITICAL:
        urgency_hours = 4
    elif risk_level == RiskLevel.HIGH:
        urgency_hours = 12
    elif risk_level == RiskLevel.MEDIUM:
        urgency_hours = 24
    
    # Generate reasoning
    reasoning_parts = []
    if signal.delay_mentioned:
        reasoning_parts.append("Delay mentioned in supplier communication")
    if signal.commitment_confidence == CommitmentConfidence.WEAK:
        reasoning_parts.append("Weak commitment confidence")
    if signal.ambiguity_detected:
        reasoning_parts.append("Ambiguity detected in communication")
    
    reasoning = ". ".join(reasoning_parts) if reasoning_parts else "Standard operational risk assessment."
    
    return RiskAssessment(
        risk_level=risk_level,
        risk_score=risk_score,
        impact_summary=impact_summary,
        affected_operations=affected_ops,
        recommended_actions=actions,
        urgency_hours=urgency_hours,
        financial_impact_estimate=None,  # Not calculated deterministically
        reasoning=reasoning
    )
