"""
Hugo - Inbox Watchdog Agent
Delivery Change Detector

Uses Ollama (gemma:2b) to extract delivery changes from email content.
Includes retry logic for JSON parsing and handles vague date phrases.
"""

import json
import re
from typing import Optional
from datetime import datetime, timedelta
from calendar import monthrange

from config.settings import settings
from models.schemas import Email, DeliveryChange, ChangeType
from utils.helpers import setup_logging
from services.ollama_llm import OllamaLLM, OllamaConnectionError

logger = setup_logging()

# Maximum retry attempts for JSON parsing
MAX_RETRIES = 3

# Improved prompt for strict JSON extraction with vague date handling
EXTRACTION_PROMPT = """Extract delivery change information from this email. TODAY: {today} ({day_of_week})

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "detected": true | false,
    "order_id": "string" | null,
    "sku": ["string"] | [],
    "original_delivery_date": "YYYY-MM-DD" | null,
    "new_delivery_date": "YYYY-MM-DD" | null,
    "change_type": "delay" | "early" | "quantity_change" | "cancellation" | "partial_shipment" | "rescheduled" | "other" | null,
    "delay_days": number | null,
    "reason": "string" | null,
    "affected_items": ["string"],
    "quantity_change": number | null,
    "confidence": number (0.0-1.0)
}}

=== EMAIL ===
From: {sender}
Subject: {subject}
Body: {body}

=== EXTRACTION RULES ===
1. If no delivery change detected: set detected=false, all other fields null/empty
2. Confidence scoring: 0.9+ (explicit), 0.7-0.9 (clear), 0.5-0.7 (vague), 0.3-0.5 (uncertain)
3. For vague dates: "next Friday"=next Friday, "end of month"=month end, "in 2 weeks"=today+14 days
4. delay_days: positive=delay, negative=early, null if not applicable
5. quantity_change: positive=increase, negative=decrease, null if not applicable

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null or empty array [].
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else."""


# Retry prompt when JSON parsing fails
RETRY_PROMPT = """Your response was invalid JSON.
Error: {error}

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "detected": true | false,
    "order_id": "string" | null,
    "sku": ["string"] | [],
    "original_delivery_date": "YYYY-MM-DD" | null,
    "new_delivery_date": "YYYY-MM-DD" | null,
    "change_type": "delay" | "early" | "quantity_change" | "cancellation" | "partial_shipment" | "rescheduled" | "other" | null,
    "delay_days": number | null,
    "reason": "string" | null,
    "affected_items": ["string"],
    "quantity_change": number | null,
    "confidence": number (0.0-1.0)
}}

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null or empty array [].
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else.

NO markdown. ONLY JSON."""


class DeliveryDetector:
    """
    Detects delivery changes in supplier emails using Ollama (gemma:2b).
    
    Features:
    - Handles vague date phrases ("next Friday", "end of month")
    - Retry logic for JSON parsing failures
    - Confidence scoring (0-1)
    - Structured extraction of order_id, sku, dates, reason
    """
    
    def __init__(self):
        """Initialize detector with Ollama."""
        self.ollama = OllamaLLM(model="gemma:2b", base_url="http://localhost:11434")
        logger.info("DeliveryDetector initialized with Ollama (gemma:2b)")
    
    def detect_changes(self, email: Email) -> DeliveryChange:
        """
        Analyze an email for delivery changes using robust LLM generation.
        
        Args:
            email: Parsed Email object
        
        Returns:
            DeliveryChange with extracted information
        """
        # Get current date info for vague date resolution
        today = datetime.now()
        day_of_week = today.strftime("%A")
        
        # Format the extraction prompt
        prompt = EXTRACTION_PROMPT.format(
            sender=f"{email.sender_name or ''} <{email.sender}>",
            subject=email.subject,
            body=email.body[:4000],  # Limit body length
            today=today.strftime("%Y-%m-%d"),
            day_of_week=day_of_week
        )
        
        try:
            # Generate JSON with auto-repair and normalization
            result = self.ollama.generate_json(prompt)
            
            # Validate required fields
            if not result or not isinstance(result.get("detected"), bool):
                logger.warning("Extraction returned invalid structure even after repair")
                return DeliveryChange(
                    detected=False, 
                    confidence=0.0, 
                    raw_extract="Validation failed"
                )
            
            logger.info(f"Extraction successful")
            return self._build_delivery_change(result, "Raw response not available in robust mode")
            
        except OllamaConnectionError:
            logger.warning("Ollama connection failed - skipping email analysis")
            return DeliveryChange(
                detected=False, 
                confidence=0.0, 
                raw_extract="Ollama connection failed"
            )
            
        except Exception as e:
            logger.error(f"Unexpected error in detect_changes: {e}")
            return DeliveryChange(
                detected=False, 
                confidence=0.0, 
                raw_extract=f"Error: {e}"
            )
    
    def _parse_json_response(self, response: str, ollama_url: str, model: str) -> dict:
        """
        Parse JSON from LLM response, handling common issues.
        
        Args:
            response: Raw LLM response text
            ollama_url: Ollama API base URL
            model: Model name
        
        Returns:
            Parsed JSON dict
        
        Raises:
            json.JSONDecodeError: If parsing fails
        """
        text = clean_json_text(response)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parsing failed: {str(e)[:100]}")
            
            # Attempt to repair JSON with Ollama
            repaired = attempt_json_repair(response, e, ollama_url, model)
            if repaired is not None:
                return repaired
            
            # If repair failed, raise original error
            raise
    
    def _build_delivery_change(self, result: dict, raw: str) -> DeliveryChange:
        """
        Build DeliveryChange model from parsed result.
        
        Maps the new extraction format to the existing schema.
        """
        # Parse change type
        change_type = None
        if result.get("change_type"):
            try:
                change_type = ChangeType(result["change_type"])
            except ValueError:
                change_type = ChangeType.OTHER
        
        # Parse dates
        original_date = self._parse_date_string(result.get("original_delivery_date"))
        new_date = self._parse_date_string(result.get("new_delivery_date"))
        
        # Combine SKUs and affected items
        affected_items = result.get("affected_items", [])
        skus = result.get("sku", [])
        if skus and isinstance(skus, list):
            affected_items = skus + [item for item in affected_items if item not in skus]
        
        return DeliveryChange(
            detected=result.get("detected", False),
            change_type=change_type,
            original_date=original_date,
            new_date=new_date,
            delay_days=result.get("delay_days"),
            affected_items=affected_items,
            quantity_change=result.get("quantity_change"),
            supplier_reason=result.get("reason"),
            po_reference=result.get("order_id"),
            confidence=float(result.get("confidence", 0.0)),
            raw_extract=raw
        )
    
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
            result = self.detect_changes(email)
            results.append(result)
            
            if result.detected:
                logger.info(f"  → Detected: {result.change_type.value if result.change_type else 'unknown'} (confidence: {result.confidence:.0%})")
            else:
                logger.info(f"  → No delivery change detected")
        
        return results
