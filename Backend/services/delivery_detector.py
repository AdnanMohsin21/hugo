"""
Hugo - Inbox Watchdog Agent
Delivery Change Detector

HYBRID ARCHITECTURE: LLM extracts semantic signals only. Python computes all values deterministically.
LLMs are constrained to semantic understanding only. All decisions are deterministic.
"""

from typing import Optional
from datetime import datetime

from models.schemas import Email, DeliveryChange, PurchaseOrder, Signal
from utils.helpers import setup_logging
from services.signal_extractor import SignalExtractor
from services.deterministic_logic import (
    calculate_delay_days,
    calculate_quantity_change,
    build_delivery_change
)

logger = setup_logging()

# LLMs are constrained to semantic understanding only. All decisions are deterministic.


class DeliveryDetector:
    """
    Detects delivery changes using hybrid architecture.
    
    LLM extracts semantic signals only. Python computes delay_days, quantity_change, and all values deterministically.
    """
    
    def __init__(self):
        """Initialize detector with signal extractor."""
        self.signal_extractor = SignalExtractor()
        logger.info("DeliveryDetector initialized (hybrid architecture)")
    
    def detect_changes(
        self,
        email: Email,
        po: Optional[PurchaseOrder] = None,
        rag_context: Optional[str] = None
    ) -> tuple[DeliveryChange, Signal]:
        """
        Analyze an email for delivery changes using hybrid architecture.
        
        Args:
            email: Parsed Email object
            po: Optional purchase order for context
            rag_context: Optional RAG context (PO metadata, ERP data)
        
        Returns:
            Tuple of (DeliveryChange, Signal)
        """
        try:
            # Step 1: Extract semantic signals from LLM
            signal = self.signal_extractor.extract_signals(email, rag_context)
            logger.info(f"Signals extracted: delay={signal.delay_mentioned}, qty={signal.quantity_change_mentioned}, eta={signal.eta_changed}")
            
            # Step 2: Calculate delay_days deterministically in Python
            today = datetime.now()
            delay_days = calculate_delay_days(signal, po, email.body, today)
            
            # Step 3: Calculate quantity_change deterministically in Python
            quantity_change = calculate_quantity_change(signal, email.body)
            
            # Step 4: Build DeliveryChange from signals and calculated values
            delivery_change = build_delivery_change(
                signal=signal,
                delay_days=delay_days,
                quantity_change=quantity_change,
                email_body=email.body,
                po=po
            )
            
            logger.info(f"Delivery change detected: {delivery_change.detected}, type: {delivery_change.change_type}")
            return delivery_change, signal
            
        except Exception as e:
            logger.error(f"Unexpected error in detect_changes: {e}")
            from models.schemas import Signal as FallbackSignal
            return DeliveryChange(
                detected=False,
                confidence=0.0,
                raw_extract=f"Error: {e}"
            ), FallbackSignal()
    
    def _parse_date_string(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse a date string in YYYY-MM-DD format.
        
        Args:
            date_str: Date string or None
        
        Returns:
            datetime object or None
        """
        if not date_str or date_str == "null":
            return None
        
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}")
            return None
    
    def batch_detect(self, emails: list[Email]) -> list[DeliveryChange]:
        """
        Process multiple emails for delivery changes.
        
        Args:
            emails: List of Email objects
        
        Returns:
            List of DeliveryChange results
        """
        results = []
        for email in emails:
            logger.info(f"Processing email: {email.subject[:50]}...")
            result, _ = self.detect_changes(email)
            results.append(result)
            
            if result.detected:
                logger.info(f"  → Detected: {result.change_type.value if result.change_type else 'unknown'} (confidence: {result.confidence:.0%})")
            else:
                logger.info(f"  → No delivery change detected")
        
        return results
