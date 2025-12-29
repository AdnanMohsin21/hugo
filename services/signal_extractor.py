"""
Hugo - Signal Extraction Service

LLM-based semantic signal extraction only.
LLMs are constrained to semantic understanding only. All decisions are deterministic.

This service extracts ONLY semantic signals from emails - no numbers, no calculations, no decisions.
"""

import logging
from typing import Optional
from datetime import datetime

from models.schemas import Email, Signal, UrgencyLevel, CommitmentConfidence, SupplierSentiment
from services.huggingface_llm import HuggingFaceLLM
from utils.helpers import setup_logging

logger = setup_logging()

# Signal extraction prompt - LLM outputs ONLY semantic signals
SIGNAL_EXTRACTION_PROMPT = """Extract semantic signals from this supplier email.

You are a semantic signal extractor. Extract ONLY semantic understanding.

TODAY: {today} ({day_of_week})

=== EMAIL ===
From: {sender}
Subject: {subject}
Body: {body}

=== CONTEXT (READ-ONLY) ===
{rag_context}

=== EXTRACTION RULES ===
Output ONLY these 3 lines, nothing else:
delay_mentioned: true / false
quantity_changed: true / false
eta_changed: true / false

CRITICAL: Return ONLY those 3 lines. Do NOT use JSON. Do NOT output reasoning or explanations."""


class SignalExtractor:
    """
    Extracts semantic signals from supplier emails using LLM.
    
    LLMs are constrained to semantic understanding only. All decisions are deterministic.
    This class extracts ONLY semantic signals - no numbers, no calculations, no decisions.
    """
    
    def __init__(self):
        """Initialize signal extractor with Hugging Face LLM."""
        self.llm = HuggingFaceLLM()
        logger.info("SignalExtractor initialized")
    
    def extract_signals(
        self,
        email: Email,
        rag_context: Optional[str] = None
    ) -> Signal:
        """
        Extract semantic signals from email.
        
        Args:
            email: Email to analyze
            rag_context: Optional RAG context (PO metadata, ERP data, SLA terms)
        
        Returns:
            Signal object with semantic understanding
        """
        today = datetime.now()
        day_of_week = today.strftime("%A")
        
        context_text = rag_context or "No additional context available"
        
        try:
            prompt = SIGNAL_EXTRACTION_PROMPT.format(
                sender=f"{email.sender_name or ''} <{email.sender}>",
                subject=email.subject,
                body=email.body[:4000],
                today=today.strftime("%Y-%m-%d"),
                day_of_week=day_of_week,
                rag_context=context_text
            )
            
            response = self.llm.generate(prompt)
            
            if not response:
                logger.warning("LLM unavailable — deterministic fallback used")
                return self._fallback_heuristic(email)
            
            # Simple line-by-line parsing for boolean signals
            signals = {}
            for line in response.lower().split('\n'):
                if ':' in line:
                    parts = [s.strip() for s in line.split(':', 1)]
                    if len(parts) == 2:
                        key, val = parts
                        # Map LLM prompt keys to schema keys
                        if key == "quantity_changed":
                            key = "quantity_change_mentioned"
                        signals[key] = 'true' in val
            
            # If LLM fails OR returns empty signals, apply fallback heuristics
            if not response or not any(signals.values()):
                if not response:
                    logger.warning("LLM unavailable — deterministic fallback used")
                else:
                    logger.debug("LLM returned all FALSE - checking heuristics as backup")
                
                heuristic_signals = self._get_heuristic_signals(email)
                if any(heuristic_signals.values()):
                    if not response:
                        logger.info("LLM unavailable — deterministic fallback used")
                    else:
                        logger.info("Heuristics detected signal missed by LLM")
                    signals.update({k: v for k, v in heuristic_signals.items() if v})

            logger.info(f"Extracted signals: {signals}")
            
            # Parse signal with validation
            return Signal(
                delay_mentioned=signals.get("delay_mentioned", False),
                quantity_change_mentioned=signals.get("quantity_change_mentioned", False),
                eta_changed=signals.get("eta_changed", False),
                # Use defaults for the rest
                urgency_level=UrgencyLevel.LOW,
                commitment_confidence=CommitmentConfidence.MEDIUM,
                supplier_sentiment=SupplierSentiment.NEUTRAL,
                ambiguity_detected=False
            )
            
        except Exception as e:
            logger.error(f"Signal extraction failed: {e}")
            logger.warning("LLM unavailable — deterministic fallback used")
            return self._fallback_heuristic(email)
            
    def _get_heuristic_signals(self, email: Email) -> dict[str, bool]:
        """Apply lightweight keyword heuristics to infer boolean signals."""
        body = email.body.lower()
        subject = email.subject.lower()
        content = f"{subject} {body}"
        
        delay_keywords = ["delay", "late", "postponed", "rescheduled", "pushed back", "slipped"]
        quantity_keywords = ["reduced", "short", "less", "cut", "partial", "shortage", "unavailable"]
        eta_keywords = ["new date", "revised eta", "expected by", "estimated delivery", "updated date"]
        
        return {
            "delay_mentioned": any(k in content for k in delay_keywords),
            "quantity_change_mentioned": any(k in content for k in quantity_keywords),
            "eta_changed": any(k in content for k in eta_keywords)
        }

    def _fallback_heuristic(self, email: Email) -> Signal:
        """Return signals based on keyword heuristics."""
        h = self._get_heuristic_signals(email)
        return Signal(
            delay_mentioned=h["delay_mentioned"],
            quantity_change_mentioned=h["quantity_change_mentioned"],
            eta_changed=h["eta_changed"],
            urgency_level=UrgencyLevel.LOW,
            commitment_confidence=CommitmentConfidence.MEDIUM,
            supplier_sentiment=SupplierSentiment.NEUTRAL,
            ambiguity_detected=False
        )

    def _default_signal(self) -> Signal:
        """Return conservative default signal when extraction fails."""
        return Signal(
            delay_mentioned=False,
            quantity_change_mentioned=False,
            eta_changed=False,
            urgency_level=UrgencyLevel.LOW,
            commitment_confidence=CommitmentConfidence.MEDIUM,
            supplier_sentiment=SupplierSentiment.NEUTRAL,
            ambiguity_detected=False
        )
