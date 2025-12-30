"""
Hugo - Risk Engine Service
Assesses operational risk for delivery changes.
"""

import logging
from typing import Optional

from models.schemas import DeliveryChange, PurchaseOrder, HistoricalContext, Signal, RiskAssessment, RiskLevel
from services.deterministic_logic import compute_risk_score, classify_risk_level, build_risk_assessment
from utils.helpers import setup_logging

logger = setup_logging()


class RiskEngine:
    """Risk assessment engine for delivery changes."""
    
    def __init__(self):
        """Initialize risk engine."""
        logger.info("Risk engine initialized (hybrid architecture)")
    
    def assess_risk(self, change: DeliveryChange, po: Optional[PurchaseOrder], 
                   context: Optional[HistoricalContext], email_body: str, 
                   signal: Signal) -> RiskAssessment:
        """
        Assess risk for delivery change.
        
        Args:
            change: Delivery change object
            po: Purchase order
            context: Historical context
            email_body: Email body text
            signal: Extracted signals
        
        Returns:
            Risk assessment
        """
        try:
            # Compute risk score deterministically
            risk_score = compute_risk_score(
                signal=signal,
                delay_days=change.delay_days,
                quantity_change=change.quantity_change,
                po=po,
                context=context
            )
            
            # Classify risk level
            risk_level = classify_risk_level(risk_score)
            
            # Build risk assessment
            assessment = build_risk_assessment(
                signal=signal,
                delay_days=change.delay_days,
                quantity_change=change.quantity_change,
                risk_score=risk_score,
                risk_level=risk_level,
                po=po,
                context=context
            )
            
            logger.info(f"Risk assessment: {risk_level.value} (score: {risk_score:.2f})")
            return assessment
            
        except Exception as e:
            logger.error(f"Error in risk assessment: {e}")
            # Return conservative default
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                risk_score=0.5,
                impact_summary="Unable to complete full risk assessment.",
                affected_operations=["Supply Chain"],
                recommended_actions=["Manual review required"],
                urgency_hours=24,
                financial_impact_estimate=None,
                reasoning="Risk assessment failed - manual review needed."
            )
