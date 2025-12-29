"""
Hugo - Alert Decision Intelligence Service

Uses Ollama to intelligently evaluate supplier change events and determine
whether they warrant operational alerts.

Reactive intelligence: Every supplier change event is evaluated by Ollama
to decide if it requires human attention based on operational impact.
"""

import json
import logging
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from services.json_repair import attempt_json_repair, clean_json_text

logger = logging.getLogger("hugo.alert_decision")


@dataclass
class ChangeEvent:
    """Supplier change event from detection pipeline."""
    
    change_type: str  # delay, early, partial_shipment, cancellation, etc.
    delay_days: Optional[int] = None
    affected_items: Optional[list] = None
    supplier_name: Optional[str] = None
    po_number: Optional[str] = None
    po_priority: Optional[str] = None  # low, normal, high, critical
    order_value: Optional[float] = None
    detected_at: Optional[datetime] = None
    confidence: Optional[float] = None
    supplier_reason: Optional[str] = None


@dataclass
class OperationalContext:
    """Operational context to inform alert decision."""
    
    # Production
    production_capacity: Optional[int] = None
    current_production_rate: Optional[int] = None
    
    # Orders
    active_orders_count: Optional[int] = None
    orders_at_risk: Optional[int] = None
    
    # Inventory
    inventory_level: Optional[float] = None  # Days of supply
    min_inventory_level: Optional[float] = None
    
    # Supply chain
    supplier_reliability_score: Optional[float] = None  # 0-1
    supplier_past_issues: Optional[int] = None
    alternate_suppliers_available: Optional[bool] = None
    
    # Timing
    days_until_delivery: Optional[int] = None
    days_until_deadline: Optional[int] = None


@dataclass
class AlertDecision:
    """Alert decision output from Ollama."""
    
    trigger_alert: bool
    urgency: str  # low, medium, high, critical
    reason: str
    should_escalate: bool = False
    recommended_actions: Optional[list] = None
    raw_response: str = ""
    error: Optional[str] = None
    is_fallback: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trigger_alert": self.trigger_alert,
            "urgency": self.urgency,
            "reason": self.reason,
            "should_escalate": self.should_escalate,
            "recommended_actions": self.recommended_actions or [],
            "is_fallback": self.is_fallback,
            "error": self.error
        }


def should_trigger_alert(
    change_event: ChangeEvent,
    context: Optional[OperationalContext] = None,
    ollama_url: str = "http://localhost:11434",
    model: str = "gemma:2b"
) -> AlertDecision:
    """
    Determine whether a supplier change event warrants an operational alert.
    
    Uses Ollama to evaluate the operational impact and urgency of any detected
    supplier change (delay, early delivery, partial shipment, etc.).
    
    Args:
        change_event: Detected supplier change event
            - change_type: Type of change (delay, early, partial_shipment, etc.)
            - delay_days: Days of delay/early (positive=delay, negative=early)
            - affected_items: List of affected part numbers/descriptions
            - supplier_name: Name of supplier
            - po_number: Associated purchase order
            - po_priority: Priority level of order (low/normal/high/critical)
            - order_value: Value of affected order
            - supplier_reason: Why supplier made the change
        
        context: Operational context to inform decision
            - production_capacity: Units/week capacity
            - current_production_rate: Current actual rate
            - active_orders_count: Total active orders
            - orders_at_risk: Orders impacted by this change
            - inventory_level: Days of supply available
            - supplier_reliability_score: Historical reliability (0-1)
            - supplier_past_issues: Count of previous issues
            - alternate_suppliers_available: Can we switch?
            - days_until_delivery: Time until scheduled delivery
            - days_until_deadline: Time until order is needed
        
        ollama_url: Ollama API endpoint
        model: Model name (gemma:2b)
    
    Returns:
        AlertDecision with:
        - trigger_alert: bool - Whether to trigger alert
        - urgency: str - Urgency level (low/medium/high/critical)
        - reason: str - Explanation of decision
        - should_escalate: bool - Whether to escalate to management
        - recommended_actions: list - Suggested actions
    
    Examples:
        >>> change = ChangeEvent(
        ...     change_type="delay",
        ...     delay_days=10,
        ...     affected_items=["CRITICAL-PART-001"],
        ...     po_priority="critical"
        ... )
        >>> ctx = OperationalContext(
        ...     inventory_level=2.0,
        ...     supplier_reliability_score=0.4,
        ...     days_until_deadline=12
        ... )
        >>> decision = should_trigger_alert(change, ctx)
        >>> if decision.trigger_alert:
        ...     print(f"Alert triggered: {decision.reason}")
    """
    
    # Build evaluation prompt
    prompt = _build_alert_evaluation_prompt(change_event, context)
    
    try:
        # Call Ollama
        response = _call_ollama_for_decision(prompt, ollama_url, model)
        
        # Parse decision with repair
        decision_data = _parse_alert_decision(response, ollama_url, model)
        
        # Validate decision
        if not _validate_decision(decision_data):
            return _safe_default_decision(
                change_event=change_event,
                error="Invalid response structure from Ollama"
            )
        
        logger.info(
            f"Alert decision: {decision_data['trigger_alert']} "
            f"(urgency: {decision_data['urgency']}) "
            f"for {change_event.change_type} event"
        )
        
        return AlertDecision(
            trigger_alert=decision_data.get("trigger_alert", False),
            urgency=decision_data.get("urgency", "medium").lower(),
            reason=decision_data.get("reason", "Unknown reason"),
            should_escalate=decision_data.get("should_escalate", False),
            recommended_actions=decision_data.get("recommended_actions"),
            raw_response=response
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in alert decision: {e}")
        return _safe_default_decision(change_event, error=f"JSON parse error: {str(e)}")
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot reach Ollama: {e}")
        return _safe_default_decision(change_event, error=f"Cannot reach Ollama")
    
    except requests.exceptions.Timeout as e:
        logger.error(f"Ollama timeout: {e}")
        return _safe_default_decision(change_event, error="Ollama timeout")
    
    except Exception as e:
        logger.error(f"Unexpected error in alert decision: {e}")
        return _safe_default_decision(change_event, error=str(e))


def _build_alert_evaluation_prompt(
    change_event: ChangeEvent,
    context: Optional[OperationalContext]
) -> str:
    """Build the alert evaluation prompt for Ollama."""
    
    # Format change event
    change_info = f"""
Change Type: {change_event.change_type.upper()}
"""
    
    if change_event.delay_days is not None:
        if change_event.delay_days > 0:
            change_info += f"Delay: {change_event.delay_days} days\n"
        elif change_event.delay_days < 0:
            change_info += f"Early: {abs(change_event.delay_days)} days\n"
    
    if change_event.affected_items:
        change_info += f"Affected Items: {', '.join(change_event.affected_items[:5])}\n"
    
    if change_event.supplier_name:
        change_info += f"Supplier: {change_event.supplier_name}\n"
    
    if change_event.po_number:
        change_info += f"PO: {change_event.po_number}\n"
    
    if change_event.po_priority:
        change_info += f"Priority: {change_event.po_priority}\n"
    
    if change_event.order_value:
        change_info += f"Value: ${change_event.order_value:,.0f}\n"
    
    if change_event.supplier_reason:
        change_info += f"Reason: {change_event.supplier_reason}\n"
    
    if change_event.confidence is not None:
        change_info += f"Detection Confidence: {change_event.confidence:.0%}\n"
    
    # Format operational context
    context_info = "No operational context available"
    if context:
        context_lines = []
        
        if context.production_capacity:
            context_lines.append(f"  Production Capacity: {context.production_capacity} units/week")
        
        if context.current_production_rate:
            context_lines.append(f"  Current Rate: {context.current_production_rate} units/week")
        
        if context.active_orders_count:
            context_lines.append(f"  Active Orders: {context.active_orders_count}")
        
        if context.orders_at_risk:
            context_lines.append(f"  Orders At Risk: {context.orders_at_risk}")
        
        if context.inventory_level is not None:
            context_lines.append(f"  Inventory Level: {context.inventory_level:.1f} days of supply")
        
        if context.min_inventory_level is not None:
            context_lines.append(f"  Min Inventory: {context.min_inventory_level:.1f} days")
        
        if context.supplier_reliability_score is not None:
            context_lines.append(f"  Supplier Reliability: {context.supplier_reliability_score:.0%}")
        
        if context.supplier_past_issues:
            context_lines.append(f"  Past Issues: {context.supplier_past_issues}")
        
        if context.alternate_suppliers_available is not None:
            alt = "Yes" if context.alternate_suppliers_available else "No"
            context_lines.append(f"  Alternate Suppliers: {alt}")
        
        if context.days_until_delivery is not None:
            context_lines.append(f"  Days Until Delivery: {context.days_until_delivery}")
        
        if context.days_until_deadline is not None:
            context_lines.append(f"  Days Until Needed: {context.days_until_deadline}")
        
        if context_lines:
            context_info = "\n".join(context_lines)
    
    prompt = f"""You are an operations alert intelligence system. Evaluate whether this supplier change event warrants an operational alert.

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "trigger_alert": true | false,
    "urgency": "low" | "medium" | "high" | "critical",
    "reason": "string (1-2 sentences)",
    "should_escalate": true | false,
    "recommended_actions": ["string"] | null
}}

=== SUPPLIER CHANGE EVENT ===
{change_info}

=== OPERATIONAL CONTEXT ===
{context_info}

=== EVALUATION CRITERIA ===
Consider:
1. Impact on production (can we still build products?)
2. Inventory buffer (do we have enough stock?)
3. Order priority (is this for a critical order?)
4. Supplier reliability (is this expected behavior?)
5. Timeline (how urgent is this?)
6. Alternatives (can we switch suppliers?)

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null.
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else.

Decision Guidelines:
- Base decision on operational impact, not just delay duration
- A 2-day early delivery with adequate inventory may not warrant alert
- A critical order with unknown delay may warrant high urgency alert
- Escalate if production risk is high or supplier is unreliable"""
    
    return prompt


def _call_ollama_for_decision(
    prompt: str,
    ollama_url: str,
    model: str
) -> str:
    """
    Call Ollama for alert decision.
    
    Args:
        prompt: Evaluation prompt
        ollama_url: Ollama endpoint
        model: Model name
    
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
        "temperature": 0.2  # Low temperature for consistent decisions
    }
    
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    
    result = response.json()
    return result.get("response", "").strip()


def _parse_alert_decision(response: str, ollama_url: str, model: str) -> Dict[str, Any]:
    """
    Parse JSON alert decision from Ollama with automatic repair.
    
    If initial parsing fails, attempts to repair the JSON
    by asking Ollama to fix it.
    
    Args:
        response: Raw response text
        ollama_url: Ollama endpoint (for repair if needed)
        model: Model name (for repair if needed)
    
    Returns:
        Parsed decision dict
    
    Raises:
        json.JSONDecodeError: If parsing fails even after repair
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


def _validate_decision(decision: Dict[str, Any]) -> bool:
    """
    Validate alert decision structure.
    
    Args:
        decision: Parsed decision dict
    
    Returns:
        True if valid, False otherwise
    """
    
    required_keys = {"trigger_alert", "urgency", "reason"}
    
    if not isinstance(decision, dict):
        return False
    
    if not required_keys.issubset(decision.keys()):
        return False
    
    # Validate types
    if not isinstance(decision.get("trigger_alert"), bool):
        return False
    
    if not isinstance(decision.get("reason"), str):
        return False
    
    # Validate urgency value
    valid_urgencies = {"low", "medium", "high", "critical"}
    if decision.get("urgency", "").lower() not in valid_urgencies:
        return False
    
    return True


def _safe_default_decision(
    change_event: ChangeEvent,
    error: Optional[str] = None
) -> AlertDecision:
    """
    Return safe default when Ollama fails.
    
    Attempts simplified Ollama reasoning first, then falls back to conservative logic.
    Never relies solely on hardcoded heuristics - always tries LLM first.
    
    Args:
        change_event: The change event
        error: Error message from primary attempt
    
    Returns:
        AlertDecision with attempted LLM reasoning or conservative defaults
    """
    
    logger.warning(f"Primary Ollama call failed ({error}). Attempting simplified fallback reasoning.")
    
    # Try one more time with a minimal fallback prompt
    fallback_prompt = f"""Quick alert decision (fallback). Rate LOW|MEDIUM|HIGH|CRITICAL.
Change: {change_event.change_type}
Delay: {change_event.delay_days or 'none'} days
Priority: {change_event.po_priority or 'normal'}
Alert needed? {{
  "trigger_alert": true,
  "urgency": "medium",
  "reason": "fallback"
}}"""
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "gemma:2b", "prompt": fallback_prompt, "stream": False},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        decision_data = _parse_alert_decision(result.get("response", ""))
        
        if _validate_decision(decision_data):
            logger.info(f"Fallback Ollama reasoning succeeded: {decision_data['trigger_alert']} (urgency: {decision_data['urgency']})")
            return AlertDecision(
                trigger_alert=decision_data.get("trigger_alert", True),
                urgency=decision_data.get("urgency", "medium").lower(),
                reason=decision_data.get("reason", "Fallback LLM assessment"),
                should_escalate=decision_data.get("should_escalate", False),
                recommended_actions=decision_data.get("recommended_actions"),
                raw_response=result.get("response", ""),
                error=None,
                is_fallback=False  # Ollama succeeded on fallback
            )
    except Exception as fallback_error:
        logger.error(f"Fallback Ollama attempt also failed: {fallback_error}. Using conservative safety defaults.")
    
    # Only use conservative defaults if both Ollama attempts fail
    logger.warning("All Ollama attempts failed. Using conservative safety defaults (better to over-alert).")
    
    urgency = "medium"
    if change_event.po_priority == "critical":
        urgency = "high"
    elif change_event.change_type == "cancellation":
        urgency = "high"
    
    return AlertDecision(
        trigger_alert=True,
        urgency=urgency,
        reason=f"Unable to evaluate with LLM: {error or 'Ollama unavailable'}. Defaulting to alert for safety.",
        should_escalate=(urgency in ["high", "critical"]),
        recommended_actions=["Manual review required - LLM unavailable", "Contact supplier"],
        error=error,
        is_fallback=True
    )


# Export public API
__all__ = [
    "ChangeEvent",
    "OperationalContext",
    "AlertDecision",
    "should_trigger_alert",
]
