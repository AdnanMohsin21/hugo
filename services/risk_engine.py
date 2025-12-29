"""
Hugo - Inbox Watchdog Agent
Risk Engine Service

HYBRID ARCHITECTURE: LLM extracts semantic signals only. Python computes risk scores deterministically.
LLMs are constrained to semantic understanding only. All decisions are deterministic.
"""

from typing import Optional

from models.schemas import (
    DeliveryChange,
    PurchaseOrder,
    HistoricalContext,
    RiskAssessment,
    Signal
)
from utils.helpers import setup_logging
from services.signal_extractor import SignalExtractor
from services.deterministic_logic import (
    compute_risk_score,
    classify_risk_level,
    build_risk_assessment
)

logger = setup_logging()

# LLMs are constrained to semantic understanding only. All decisions are deterministic.


class RiskEngine:
    """
    Assesses operational risk using hybrid architecture.
    
    LLM extracts semantic signals only. Python computes risk_score, risk_level, and all values deterministically.
    """
    
    def __init__(self):
        """Initialize risk engine with signal extractor."""
        self.signal_extractor = SignalExtractor()
        logger.info("Risk engine initialized (hybrid architecture)")
    
    def assess_risk(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder] = None,
        context: Optional[HistoricalContext] = None,
        email_body: str = "",
        signal: Optional[Signal] = None
    ) -> RiskAssessment:
        """
        Assess operational risk using hybrid architecture.
        
        Args:
            change: Detected delivery change (with calculated delay_days, quantity_change)
            po: Matched purchase order
            context: Historical context from vector store
            email_body: Original email body
            signal: Optional pre-extracted signal (to avoid re-extraction)
        
        Returns:
            RiskAssessment with computed values
        """
        try:
            # Get signal (extract if not provided)
            if signal is None:
                # Build signal from change data (fallback if signal not provided)
                # In production, signal should be passed from DeliveryDetector
                from models.schemas import UrgencyLevel, CommitmentConfidence, SupplierSentiment
                signal = Signal(
                    delay_mentioned=change.delay_days is not None and change.delay_days > 0,
                    quantity_change_mentioned=change.quantity_change is not None,
                    eta_changed=change.delay_days is not None,
                    urgency_level=UrgencyLevel.HIGH if change.confidence >= 0.8 else UrgencyLevel.MEDIUM if change.confidence >= 0.6 else UrgencyLevel.LOW,
                    commitment_confidence=CommitmentConfidence.STRONG if change.confidence >= 0.8 else CommitmentConfidence.WEAK if change.confidence < 0.5 else CommitmentConfidence.MEDIUM,
                    supplier_sentiment=SupplierSentiment.NEUTRAL,
                    ambiguity_detected=change.confidence < 0.6
                )
            
            # Compute risk score deterministically in Python
            risk_score = compute_risk_score(
                signal=signal,
                delay_days=change.delay_days,
                quantity_change=change.quantity_change,
                po=po,
                context=context
            )
            
            # Classify risk level deterministically
            risk_level = classify_risk_level(risk_score)
            
            # Build risk assessment
            risk_assessment = build_risk_assessment(
                signal=signal,
                delay_days=change.delay_days,
                quantity_change=change.quantity_change,
                risk_score=risk_score,
                risk_level=risk_level,
                po=po,
                context=context
            )
            
            logger.info(f"Risk assessment: {risk_level.value} (score: {risk_score:.2f})")
            return risk_assessment
            
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            # Return conservative default
            from models.schemas import RiskLevel
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                risk_score=0.5,
                impact_summary="Unable to assess risk due to error",
                affected_operations=["Supply Chain"],
                recommended_actions=["Manual review required"],
                reasoning=f"Error during assessment: {e}"
            )
    
