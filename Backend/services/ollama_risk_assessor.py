"""
Hugo - Ollama Risk Assessment Service

Dedicated risk assessment using Ollama (gemma:2b) with pure LLM reasoning.
No heuristics or rule-based fallbacks - all reasoning comes from the model.

Design principles:
- Risk level and risk_score are determined by Ollama reasoning only
- Robust JSON parsing with graceful degradation
- Structured outputs for decision-making
"""

import json
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime

from services.json_repair import attempt_json_repair, clean_json_text

logger = logging.getLogger("hugo.risk_assessor")


class RiskAssessmentResult:
    """Structured risk assessment result."""
    
    def __init__(
        self,
        risk_level: str,
        risk_score: float,
        drivers: list[str],
        recommended_actions: list[str],
        raw_response: str = "",
        error: Optional[str] = None
    ):
        self.risk_level = risk_level  # low, medium, high, critical
        self.risk_score = risk_score  # 0.0-1.0
        self.drivers = drivers  # list of risk factors
        self.recommended_actions = recommended_actions  # actionable items
        self.raw_response = raw_response
        self.error = error
        self.is_fallback = error is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "drivers": self.drivers,
            "recommended_actions": self.recommended_actions,
            "is_fallback": self.is_fallback,
            "error": self.error
        }


def assess_risk_with_ollama(
    email_text: str,
    purchase_order: Optional[Dict[str, Any]] = None,
    historical_context: Optional[Dict[str, Any]] = None,
    ollama_url: str = "http://localhost:11434",
    model: str = "gemma:2b"
) -> RiskAssessmentResult:
    """
    Assess operational risk using Ollama as the sole reasoning engine.
    
    All risk determination comes from LLM reasoning, not heuristics.
    
    Args:
        email_text: Supplier email content (delivery change notification)
        purchase_order: PO data with keys:
            - po_number, supplier_name, priority, expected_delivery, total_value
        historical_context: Historical data with keys:
            - supplier_reliability_score, past_issues, avg_delay_days
        ollama_url: Ollama API endpoint
        model: Model name (gemma:2b)
    
    Returns:
        RiskAssessmentResult with risk_level, risk_score, drivers, actions
    """
    
    # Build the assessment prompt
    prompt = _build_assessment_prompt(email_text, purchase_order, historical_context)
    
    try:
        # Call Ollama API
        response = _call_ollama(prompt, ollama_url, model)
        
        # Parse response
        result = _parse_ollama_response(response, ollama_url, model)
        
        # Validate required fields
        if not _validate_result(result):
            return _safe_default(
                error="Invalid response structure from Ollama",
                raw_response=response
            )
        
        logger.info(f"Risk assessment: {result['risk_level']} (score: {result['risk_score']})")
        
        return RiskAssessmentResult(
            risk_level=result.get("risk_level", "medium").lower(),
            risk_score=float(result.get("risk_score", 0.5)),
            drivers=result.get("drivers", []),
            recommended_actions=result.get("recommended_actions", []),
            raw_response=response
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return _safe_default(error=f"JSON parse error: {str(e)}")
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Ollama connection error: {e}")
        return _safe_default(error=f"Cannot reach Ollama at {ollama_url}")
    
    except requests.exceptions.Timeout as e:
        logger.error(f"Ollama timeout: {e}")
        return _safe_default(error="Ollama request timed out")
    
    except Exception as e:
        logger.error(f"Unexpected error in risk assessment: {e}")
        return _safe_default(error=str(e))


def _build_assessment_prompt(
    email_text: str,
    purchase_order: Optional[Dict[str, Any]],
    historical_context: Optional[Dict[str, Any]]
) -> str:
    """Build the risk assessment prompt for Ollama."""
    
    # Format PO data
    po_info = "No PO data available"
    if purchase_order:
        po_info = f"""PO Number: {purchase_order.get('po_number', 'Unknown')}
Supplier: {purchase_order.get('supplier_name', 'Unknown')}
Priority: {purchase_order.get('priority', 'normal')}
Expected Delivery: {purchase_order.get('expected_delivery', 'Unknown')}
Value: {purchase_order.get('total_value', 'Unknown')} {purchase_order.get('currency', 'USD')}"""
    
    # Format historical context
    history_info = "No historical data available"
    if historical_context:
        reliability = historical_context.get('supplier_reliability_score', 0.5)
        history_info = f"""Supplier Reliability Score: {reliability:.2f}/1.0
Past Issues: {historical_context.get('past_issues', 0)}
Average Delay: {historical_context.get('avg_delay_days', 0):.1f} days"""
    
    prompt = f"""You are an operations risk analyst for a manufacturing company.

Analyze this supplier email notification for delivery changes and assess operational risk.

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "risk_level": "low" | "medium" | "high" | "critical",
    "risk_score": 0.0-1.0,
    "drivers": ["string"],
    "recommended_actions": ["string"]
}}

=== SUPPLIER EMAIL ===
{email_text}

=== PURCHASE ORDER CONTEXT ===
{po_info}

=== HISTORICAL SUPPLIER DATA ===
{history_info}

=== TASK ===
Determine the operational risk level and provide structured reasoning.

Consider:
1. Severity of the delivery change (delay, cancellation, etc.)
2. Impact on production (priority of items, criticality)
3. Supplier reliability and historical performance
4. Business impact (timeline, cost, alternatives)

Risk Level Definitions:
- LOW (0.0-0.3): Minor impact, non-critical items, adequate buffers, early delivery
- MEDIUM (0.3-0.6): Moderate impact, <7 day delay, some operational adjustment needed
- HIGH (0.6-0.85): Significant disruption, 7-14 day delay, critical timeline impact
- CRITICAL (0.85-1.0): Production stoppage risk, >14 day delay, critical components, unreliable supplier

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null.
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else."""
    
    return prompt


def _call_ollama(
    prompt: str,
    ollama_url: str,
    model: str
) -> str:
    """
    Call Ollama API with non-streaming response.
    
    Args:
        prompt: The prompt to send
        ollama_url: Ollama endpoint (e.g., http://localhost:11434)
        model: Model name (e.g., gemma:2b)
    
    Returns:
        Response text from Ollama
    
    Raises:
        requests.exceptions.RequestException: On API errors
    """
    
    url = f"{ollama_url.rstrip('/')}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.2  # Low temperature for consistent reasoning
    }
    
    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()
    
    result = response.json()
    return result.get("response", "").strip()


def _parse_ollama_response(response: str, ollama_url: str, model: str) -> Dict[str, Any]:
    """
    Parse JSON from Ollama response with automatic repair.
    
    If initial parsing fails, attempts to repair the JSON
    by asking Ollama to fix it.
    
    Args:
        response: Raw response from Ollama
        ollama_url: Ollama endpoint (for repair if needed)
        model: Model name (for repair if needed)
    
    Returns:
        Parsed JSON dict
    
    Raises:
        json.JSONDecodeError: If JSON parsing fails even after repair
    """
    
    text = clean_json_text(response)
    
    # Try parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Initial JSON parsing failed, attempting repair")
        
        # Try to repair using Ollama
        repaired = attempt_json_repair(response, e, ollama_url, model)
        
        if repaired is not None:
            return repaired
        
        # Repair failed, raise original error
        raise e


def _validate_result(result: Dict[str, Any]) -> bool:
    """
    Validate that result has required fields.
    
    Args:
        result: Parsed JSON result
    
    Returns:
        True if valid, False otherwise
    """
    
    required_keys = {"risk_level", "risk_score", "drivers", "recommended_actions"}
    
    if not isinstance(result, dict):
        return False
    
    if not required_keys.issubset(result.keys()):
        return False
    
    # Validate types
    if not isinstance(result.get("risk_level"), str):
        return False
    
    if not isinstance(result.get("risk_score"), (int, float)):
        return False
    
    if not isinstance(result.get("drivers"), list):
        return False
    
    if not isinstance(result.get("recommended_actions"), list):
        return False
    
    # Validate risk_level value
    valid_levels = {"low", "medium", "high", "critical"}
    if result.get("risk_level", "").lower() not in valid_levels:
        return False
    
    # Validate risk_score range
    score = result.get("risk_score")
    if not (0.0 <= score <= 1.0):
        return False
    
    return True


def _safe_default(
    error: Optional[str] = None,
    raw_response: str = ""
) -> RiskAssessmentResult:
    """
    Return a safe default assessment when Ollama fails.
    
    This is a true fallback - not a heuristic assessment.
    Uses conservative (MEDIUM) risk to ensure visibility.
    
    Args:
        error: Error message
        raw_response: Raw response that failed parsing
    
    Returns:
        RiskAssessmentResult with safe defaults
    """
    
    logger.warning(f"Using safe default assessment. Error: {error}")
    
    return RiskAssessmentResult(
        risk_level="medium",
        risk_score=0.5,
        drivers=["Unable to assess risk - Ollama unavailable"],
        recommended_actions=["Manual review required", "Contact supplier for details"],
        raw_response=raw_response,
        error=error
    )


# Export public API
__all__ = [
    "RiskAssessmentResult",
    "assess_risk_with_ollama",
]
