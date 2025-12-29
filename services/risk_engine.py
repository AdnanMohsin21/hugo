"""
Hugo - Inbox Watchdog Agent
Risk Engine Service

Uses Ollama (gemma:2b) to reason about operational risk based on
delivery changes, PO context, and historical data.
"""

import json
from typing import Optional
from datetime import datetime

from config.settings import settings
from models.schemas import (
    DeliveryChange, 
    PurchaseOrder, 
    HistoricalContext, 
    RiskAssessment,
    RiskLevel,
    ChangeType
)
from utils.helpers import setup_logging, format_currency
from services.ollama_llm import OllamaLLM, OllamaConnectionError

logger = setup_logging()

# ... (RISK_PROMPT and RiskEngine class definition unchanged) ...



# Risk assessment prompt template - optimized for gemma:2b
RISK_PROMPT = """Assess operational risk for this delivery change.

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "risk_level": "low" | "medium" | "high" | "critical",
    "risk_score": number (0.0-1.0),
    "impact_summary": "string (1-2 sentences)",
    "affected_operations": ["string"],
    "recommended_actions": ["string"],
    "urgency_hours": number | null,
    "financial_impact_estimate": number | null,
    "reasoning": "string (2-3 sentences)"
}}

=== DELIVERY CHANGE ===
Type: {change_type}
Delay: {delay_days} days
Items: {affected_items}
Reason: {supplier_reason}

=== PURCHASE ORDER ===
PO: {po_number}
Supplier: {supplier_name}
Value: {order_value}
Priority: {priority}
Expected: {expected_delivery}
Items: {po_items}

=== HISTORICAL DATA ===
Supplier Reliability: {reliability_score}/1.0
Past Issues: {past_issues}
Avg Delay: {avg_delay} days
Similar Incidents:
{similar_incidents}

=== RISK LEVEL GUIDELINES ===
- LOW: <3 day delay, minor impact, no critical components
- MEDIUM: 3-7 day delay, some disruption, <$10k impact
- HIGH: 7-14 day delay, significant disruption, $10k-$50k impact
- CRITICAL: >14 day delay OR production stoppage risk OR critical priority

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null or empty array [].
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else."""


class RiskEngine:
    """
    Assesses operational risk using Ollama (gemma:2b) reasoning.
    
    Combines delivery change, PO context, and historical data
    to generate actionable risk assessments.
    """
    
    def __init__(self):
        """Initialize Ollama model for risk reasoning."""
        self.ollama = OllamaLLM(model="gemma:2b", base_url="http://localhost:11434")
        logger.info("Risk engine initialized with Ollama (gemma:2b)")
    
    def assess_risk(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder] = None,
        context: Optional[HistoricalContext] = None,
        email_body: str = ""
    ) -> RiskAssessment:
        """
        Assess operational risk for a delivery change.
        
        Args:
            change: Detected delivery change
            po: Matched purchase order
            context: Historical context from vector store
            email_body: Original email body for keyword analysis
        
        Returns:
            RiskAssessment with analysis results
        """
        # 1. Deterministic Rules Check
        deterministic_risk = self._check_deterministic_rules(change, po, email_body)
        if deterministic_risk:
            logger.info(f"Deterministic alert triggered: {deterministic_risk.risk_level.value}")
            return deterministic_risk

        try:
            # Format similar incidents for prompt
            similar_text = "None found"
            if context and context.similar_incidents:
                similar_text = "\n".join([
                    f"- {inc.get('description', 'No description')}"
                    for inc in context.similar_incidents
                ])
            
            # Format resolution patterns
            resolution_text = "No patterns available"
            if context and context.resolution_patterns:
                resolution_text = "\n".join([f"- {r}" for r in context.resolution_patterns])
            
            # Format PO items
            po_items_text = "Unknown"
            if po and po.items:
                po_items_text = ", ".join([
                    f"{item.get('description', 'Item')} (x{item.get('quantity', 0)})"
                    for item in po.items
                ])
            
            # Build prompt
            prompt = RISK_PROMPT.format(
                change_type=change.change_type.value if change.change_type else "unknown",
                delay_days=change.delay_days or "N/A",
                affected_items=", ".join(change.affected_items) if change.affected_items else "Not specified",
                supplier_reason=change.supplier_reason or "Not provided",
                po_number=po.po_number if po else "Unknown",
                supplier_name=po.supplier_name if po else "Unknown",
                order_value=format_currency(po.total_value, po.currency) if po else "Unknown",
                priority=po.priority if po else "normal",
                expected_delivery=po.expected_delivery.strftime("%Y-%m-%d") if po else "Unknown",
                po_items=po_items_text,
                reliability_score=f"{context.supplier_reliability_score:.2f}" if context else "0.50",
                past_issues=context.total_past_issues if context else 0,
                avg_delay=f"{context.avg_delay_days:.1f}" if context else "0",
                similar_incidents=similar_text,
                resolution_patterns=resolution_text
            )
            
            # Generate risk assessment using Ollama
            result = self.ollama.generate_json(prompt)
            
            # If result is empty (repair failed), fallback
            if not result:
                logger.warning("Risk assessment returned empty result, using fallback")
                return self._rule_based_assessment(change, po, context)
                
            return self._parse_result(result)
            
        except OllamaConnectionError:
            logger.warning("Ollama connection failed - using rule-based fallback")
            return self._rule_based_assessment(change, po, context)
            
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return self._rule_based_assessment(change, po, context)

    def _check_deterministic_rules(
        self, 
        change: DeliveryChange, 
        po: Optional[PurchaseOrder],
        email_body: str
    ) -> Optional[RiskAssessment]:
        """
        Apply deterministic rules to trigger alerts without LLM.
        
        Rules:
        - Delay >= 3 days -> MEDIUM/HIGH
        - Partial shipment -> MEDIUM
        - Cancellation -> HIGH
        - Early >= 5 days -> MEDIUM
        - Null delay + Keywords -> MEDIUM
        """
        risk_level = None
        actions = []
        explanation = ""
        
        # Helper for keywords
        def has_keywords(text, keywords):
            text = text.lower()
            return any(k in text for k in keywords)

        # Rule 1: Delay >= 3 days
        if change.change_type == "delay" and change.delay_days is not None:
            if change.delay_days >= 7:
                 risk_level = RiskLevel.HIGH
                 explanation = f"Significant delay of {change.delay_days} days detected."
                 actions = ["Contact supplier for expedite", "Check inventory safety stock"]
            elif change.delay_days >= 3:
                 risk_level = RiskLevel.MEDIUM
                 explanation = f"Moderate delay of {change.delay_days} days detected."
                 actions = ["Monitor delivery status", "Update production schedule"]

        # Rule 2: Partial Shipment
        elif change.change_type == "partial_shipment":
            risk_level = RiskLevel.MEDIUM
            explanation = "Partial shipment detected. Potential for incomplete production analysis."
            actions = ["Confirm quantity of partial delivery", "Request date for balance"]

        # Rule 3: Cancellation
        elif change.change_type == "cancellation":
            risk_level = RiskLevel.HIGH  # Could be CRITICAL
            explanation = "Order cancellation detected. Immediate supply gap."
            actions = ["Identify alternative suppliers", "Escalate to procurement manager"]

        # Rule 4: Early >= 5 days
        elif change.change_type == "early" and change.delay_days is not None:
             # delay_days is usually negative for early
             earliness = abs(change.delay_days)
             if earliness >= 5:
                 risk_level = RiskLevel.MEDIUM
                 explanation = f"Order arriving {earliness} days early. Potential storage/inventory impact."
                 actions = ["Check warehouse capacity", "Hold shipment if necessary"]
        
        # Rule 5: Null delay but keywords present
        if not risk_level and (change.delay_days is None or change.delay_days == 0):
            keywords = ["delay", "postponed", "pushed", "backorder", "shortage"]
            if has_keywords(email_body, keywords) or (change.supplier_reason and has_keywords(change.supplier_reason, keywords)):
                risk_level = RiskLevel.MEDIUM
                explanation = "Delay inferred from email language (specific dates not extracted)."
                actions = ["Contact supplier to confirm dates", "Manual review of email"]

        if risk_level:
            # Construct deterministic assessment
            # Map risk level to score
            scores = {RiskLevel.LOW: 0.2, RiskLevel.MEDIUM: 0.5, RiskLevel.HIGH: 0.8, RiskLevel.CRITICAL: 1.0}
            
            return RiskAssessment(
                risk_level=risk_level,
                risk_score=scores.get(risk_level, 0.5),
                impact_summary=explanation,
                affected_operations=["Supply Chain", "Procurement"],
                recommended_actions=actions,
                reasoning=f"Deterministic Rule: {explanation}",
                urgency_hours=24 if risk_level != RiskLevel.HIGH else 4,
                financial_impact_estimate=None # Hard to guess
            )
        
        return None
    
    def _parse_result(self, result: dict) -> RiskAssessment:
        """Parse LLM JSON result into RiskAssessment model."""
        
        # Parse risk level
        try:
            risk_level = RiskLevel(result.get("risk_level", "medium"))
        except ValueError:
            risk_level = RiskLevel.MEDIUM
        
        return RiskAssessment(
            risk_level=risk_level,
            risk_score=result.get("risk_score", 0.5),
            impact_summary=result.get("impact_summary", "Unable to determine impact"),
            affected_operations=result.get("affected_operations", []),
            recommended_actions=result.get("recommended_actions", []),
            urgency_hours=result.get("urgency_hours"),
            financial_impact_estimate=result.get("financial_impact_estimate"),
            reasoning=result.get("reasoning", "")
        )
    
    def _rule_based_assessment(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder] = None,
        context: Optional[HistoricalContext] = None
    ) -> RiskAssessment:
        """
        Fallback rule-based risk assessment when LLM unavailable.
        
        This fallback uses simple heuristics only when Ollama fails.
        Logs clearly that this is a fallback, not the primary reasoning.
        """
        logger.warning("Ollama unavailable - using rule-based fallback assessment")
        
        # Build minimal fallback prompt for simple decision
        fallback_prompt = f"""Quick risk assessment (fallback only).

Change: {change.change_type.value if change.change_type else 'unknown'} ({change.delay_days or 0} days)
Priority: {po.priority if po else 'normal'}
Reliability: {context.supplier_reliability_score if context else 0.5}

Rate risk (LOW|MEDIUM|HIGH|CRITICAL) and score (0-1.0):
{{
  "risk_level": "MEDIUM",
  "risk_score": 0.5,
  "reasoning": "Fallback assessment"
}}
"""
        
        try:
            # Try Ollama one more time with simplified prompt
            response = self.ollama.generate(fallback_prompt)
            result = json.loads(response)
            return self._parse_result(result)
        except Exception as e:
            logger.error(f"Fallback Ollama call also failed: {e}. Using conservative defaults.")
            # Only use hardcoded logic if Ollama completely unavailable
            return self._conservative_defaults(change, po, context)
    
    def _conservative_defaults(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder] = None,
        context: Optional[HistoricalContext] = None
    ) -> RiskAssessment:
        """
        Ultra-conservative defaults when both Ollama attempts fail.
        
        Errs on the side of alerting (better to over-alert than miss risk).
        Only uses simple threshold checks for safety.
        """
        logger.warning("All Ollama attempts failed - using conservative safety defaults")
        
        # Conservative: Assume medium-high risk by default
        risk_score = 0.55  # Default medium risk
        
        # Only apply very basic heuristics for immediate danger signals
        if change.delay_days and abs(change.delay_days) > 21:
            # Extreme delay only
            risk_score = 0.8
        
        if change.change_type and change.change_type.value == "cancellation":
            # Cancellations always significant
            risk_score = max(risk_score, 0.7)
        
        if po and po.priority == "critical":
            # Critical orders get higher score
            risk_score = min(risk_score + 0.15, 1.0)
        
        # Determine level conservatively
        if risk_score >= 0.75:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 0.55:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.MEDIUM
        
        # Generate recommendations using simple logic
        recommendations = ["Manual review required - LLM unavailable", "Contact supplier immediately"]
        
        return RiskAssessment(
            risk_level=risk_level,
            risk_score=risk_score,
            impact_summary="[FALLBACK] Unable to assess with Ollama. Conservative estimate: significant risk.",
            affected_operations=["Supply Chain", "Operations Management"],
            recommended_actions=recommendations,
            urgency_hours=4 if risk_level == RiskLevel.CRITICAL else 12,
            financial_impact_estimate=None,
            reasoning=f"[FALLBACK - Ollama unavailable] Conservative estimate (score {risk_score:.2f}) pending LLM assessment."
        )
    
    def _generate_recommendations(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder],
        risk_level: RiskLevel
    ) -> list[str]:
        """Generate actionable recommendations based on risk level."""
        recommendations = []
        
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("Immediately contact supplier for expedite options")
            recommendations.append("Identify alternative suppliers for affected items")
            recommendations.append("Notify production planning of potential disruption")
        
        if risk_level == RiskLevel.CRITICAL:
            recommendations.append("Escalate to supply chain leadership")
            recommendations.append("Prepare customer communication if needed")
        
        if change.change_type and change.change_type.value == "partial_shipment":
            recommendations.append("Confirm partial delivery acceptance")
            recommendations.append("Request firm date for remaining items")
        
        if risk_level == RiskLevel.MEDIUM:
            recommendations.append("Monitor situation closely")
            recommendations.append("Document supplier communication")
        
        if risk_level == RiskLevel.LOW:
            recommendations.append("Acknowledge and track the change")
        
        return recommendations[:5]
    
    def _generate_impact_summary(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder],
        risk_level: RiskLevel
    ) -> str:
        """Generate a brief impact summary."""
        if risk_level == RiskLevel.CRITICAL:
            return f"Critical disruption expected. {change.delay_days or 'Multiple'} day delay on priority order may halt production."
        elif risk_level == RiskLevel.HIGH:
            return f"Significant operational impact. {change.change_type.value if change.change_type else 'Delivery change'} requires immediate attention."
        elif risk_level == RiskLevel.MEDIUM:
            return f"Moderate impact. Delivery {change.change_type.value if change.change_type else 'change'} may affect planning."
        else:
            return "Minor impact expected. Standard monitoring recommended."
    
    def _determine_affected_ops(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder]
    ) -> list[str]:
        """Determine which operations may be affected."""
        ops = ["Supply Chain"]
        
        if change.delay_days and abs(change.delay_days) > 3:
            ops.append("Production Planning")
        
        if po and po.priority in ["critical", "high"]:
            ops.append("Operations Management")
        
        if change.change_type and change.change_type.value in ["cancellation", "partial_shipment"]:
            ops.append("Procurement")
        
        return ops
    
    def _calculate_urgency(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder]
    ) -> Optional[int]:
        """Calculate hours until action is needed."""
        if not po:
            return 48  # Default 2 days
        
        if po.priority == "critical":
            return 4
        elif po.priority == "high":
            return 12
        else:
            return 24
