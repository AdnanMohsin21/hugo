"""
Hugo - Inbox Watchdog Agent
RAG Reasoning Service

Uses Ollama (gemma:2b) with retrieved context for risk assessment.
Combines supplier email, ERP data, and vector database context
to determine risk level and suggest actions.
"""

import json
import os
import re
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from services.ollama_llm import OllamaLLM
from utils.helpers import setup_logging

logger = setup_logging()

# Maximum retries for JSON parsing
MAX_RETRIES = 3


@dataclass
class RiskAssessment:
    """Structured risk assessment output."""
    risk_level: str  # HIGH, MEDIUM, LOW
    explanation: str
    suggested_action: str
    raw_response: str = ""


# Prompt template - optimized for gemma:2b
# ENHANCED WITH EXPLICIT GROUNDING CONSTRAINTS AND JSON OUTPUT
REASONING_PROMPT = """Assess supply chain risk. Respond with JSON only.

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "risk_level": "HIGH" | "MEDIUM" | "LOW",
    "explanation": "string (2-3 sentences grounded in provided context)",
    "suggested_action": "string (specific action based on provided information)"
}}

=== GROUNDING INSTRUCTIONS (CRITICAL) ===
GROUND ALL REASONING ONLY ON PROVIDED CONTEXT BELOW.
DO NOT assume facts not present in the context.
If information is unavailable in the provided context, explicitly state "Not provided in context".
Do NOT rely on general training data - use ONLY the email, ERP data, and historical context given below.

=== EMAIL ===
Order: {order_id} / SKU: {sku} / Supplier: {supplier_id}
Subject: {subject}
Content: {email_content}
New Delivery Date Stated: {supplier_date}

=== ERP RECORD ===
{erp_data}

=== DELAY CALCULATION ===
Days Delayed: {delay_days} days
Change Type: {change_type}

=== HISTORICAL CONTEXT FROM SIMILAR CASES ===
{rag_context}

=== REASONING RULES ===
1. Base risk assessment on: email change, ERP mismatch, delay days, historical patterns in context
2. HIGH risk: Production impact likely / delay > 7 days / critical component / poor supplier history in context
3. MEDIUM risk: Some production impact / 3-7 day delay / moderate supplier reliability in context
4. LOW risk: Minor impact / < 3 days / good supplier history in context / early delivery
5. If context is sparse or contradicts email, flag this in explanation

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null.
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else."""


# =========================================================================
# CONTEXT SUMMARIZATION FOR GROUNDING
# =========================================================================

def build_llm_context(historical_incidents: list[dict]) -> str:
    """
    Summarize retrieved historical incidents into context for LLM grounding.
    
    Transforms raw vector DB results into concise, structured context
    that helps Ollama ground reasoning without hallucinating.
    
    Args:
        historical_incidents: list[dict] from vector DB, each with:
            - text: The incident or historical context
            - metadata: dict with source_type, supplier_id, date, outcome, etc.
            - similarity/relevance: float score (0-1)
    
    Returns:
        Formatted string suitable for LLM consumption. Prioritizes:
        1. Most relevant incidents (by similarity score)
        2. Specific facts and outcomes (not assumptions)
        3. Supplier reliability metrics if available
        4. Recent incidents (dates if available)
        5. Clear labeling of data source
    
    Example:
        >>> incidents = [
        ...     {
        ...         "text": "Supplier SUP-01: 2 late deliveries in Q3, avg 5 days late",
        ...         "metadata": {"source_type": "history", "supplier_id": "SUP-01"},
        ...         "similarity": 0.89
        ...     },
        ...     {
        ...         "text": "Part CTRL-1001: high demand volatility",
        ...         "metadata": {"source_type": "sku_analysis"},
        ...         "similarity": 0.76
        ...     }
        ... ]
        >>> context = build_llm_context(incidents)
        >>> print(context)
        "SIMILAR CASES FROM HISTORY (ranked by relevance):
        1. [HISTORY - SUP-01] (rel: 0.89): 2 late deliveries in Q3, avg 5 days late
        2. [SKU_ANALYSIS] (rel: 0.76): Part CTRL-1001: high demand volatility"
    """
    if not historical_incidents:
        return "No historical context available. Assess based on email and ERP data only."
    
    # Sort by relevance/similarity (descending)
    sorted_incidents = sorted(
        historical_incidents,
        key=lambda x: x.get("relevance", x.get("similarity", 0)),
        reverse=True
    )
    
    # Build formatted context, limiting to top 5 most relevant
    context_parts = ["SIMILAR CASES FROM HISTORY (ranked by relevance):"]
    
    for i, incident in enumerate(sorted_incidents[:5], 1):
        # Extract fields
        text = incident.get("text", incident.get("document", ""))
        metadata = incident.get("metadata", {})
        relevance = incident.get("relevance", incident.get("similarity", 0))
        
        # Build source label
        source_type = metadata.get("source_type", "unknown").upper()
        supplier_id = metadata.get("supplier_id", "")
        source_label = f"[{source_type}" + (f" - {supplier_id}]" if supplier_id else "]")
        
        # Truncate text to 250 chars for readability
        text_snippet = text[:250] + ("..." if len(text) > 250 else "")
        
        # Format: "N. [SOURCE - SUPPLIER] (rel: 0.XX): text"
        context_parts.append(
            f"{i}. {source_label} (rel: {relevance:.2f}): {text_snippet}"
        )
    
    result = "\n".join(context_parts)
    
    # Add note if we had to truncate
    if len(historical_incidents) > 5:
        result += f"\n\n(Showing 5 of {len(historical_incidents)} available historical items)"
    
    return result


class RAGReasoner:
    """
    RAG-based reasoning using Ollama (gemma:2b).
    
    Combines:
    - Parsed supplier email
    - ERP purchase order data
    - Retrieved vector database context
    
    To produce structured risk assessments.
    """
    
    def __init__(self):
        """Initialize reasoner with Ollama."""
        self.ollama = OllamaLLM(model="gemma:2b", base_url="http://localhost:11434")
        logger.info("RAGReasoner initialized with Ollama (gemma:2b)")
    
    def assess_risk(
        self,
        email_data: dict,
        erp_data: Optional[dict],
        rag_context: list[dict],
        delay_days: int = 0,
        change_type: str = "NO_CHANGE"
    ) -> RiskAssessment:
        """
        Assess risk using RAG-enhanced LLM reasoning.
        
        Args:
            email_data: Parsed supplier email JSON with keys:
                - order_id, sku, supplier_id, subject, body, new_delivery_date
            erp_data: ERP purchase order record (dict or None)
            rag_context: List of retrieved context documents from vector DB
            delay_days: Calculated delay in days
            change_type: DELAY, EARLY, or NO_CHANGE
        
        Returns:
            RiskAssessment with risk_level, explanation, suggested_action
        """
        try:
            # Format the prompt
            prompt = self._build_prompt(email_data, erp_data, rag_context, delay_days, change_type)
            
            # Try generation with retries
            last_error = None
            for attempt in range(MAX_RETRIES):
                try:
                    # Use Ollama for generation
                    response = self.ollama.generate(prompt)
                    result = self._parse_response(response)
                    logger.info(f"Risk assessment: {result.risk_level}")
                    return result
                    
                except json.JSONDecodeError as e:
                    last_error = str(e)
                    logger.warning(f"JSON parse failed (attempt {attempt + 1}): {e}")
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"Reasoning failed (attempt {attempt + 1}): {e}")
            
            # All retries failed, use fallback
            logger.error(f"All attempts failed: {last_error}")
            return self._fallback_assessment(email_data, erp_data, delay_days, change_type)
        
        except Exception as e:
            logger.error(f"Risk assessment error: {e}")
            return self._fallback_assessment(email_data, erp_data, delay_days, change_type)
    
    def _build_prompt(
        self,
        email_data: dict,
        erp_data: Optional[dict],
        rag_context: list[dict],
        delay_days: int,
        change_type: str
    ) -> str:
        """Build the reasoning prompt with all context."""
        
        # Format ERP data
        if erp_data:
            erp_str = "\n".join([f"  {k}: {v}" for k, v in erp_data.items()])
        else:
            erp_str = "  No matching ERP record found"
        
        # Use new context summarization helper for better grounding
        rag_str = build_llm_context(rag_context)
        
        # Get ERP date
        erp_date = erp_data.get("delivery_date", "Unknown") if erp_data else "Unknown"
        
        return REASONING_PROMPT.format(
            order_id=email_data.get("order_id", "Unknown"),
            sku=email_data.get("sku", "Unknown"),
            supplier_id=email_data.get("supplier_id", "Unknown"),
            subject=email_data.get("subject", ""),
            email_content=email_data.get("body", email_data.get("content", ""))[:1000],
            supplier_date=email_data.get("new_delivery_date", "Not specified"),
            erp_data=erp_str,
            erp_date=erp_date,
            delay_days=delay_days,
            change_type=change_type,
            rag_context=rag_str
        )
    
    def _parse_response(self, response: str) -> RiskAssessment:
        """Parse LLM response into RiskAssessment."""
        text = response.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```"):
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1)
        
        result = json.loads(text)
        
        # Validate and normalize risk_level
        risk_level = str(result.get("risk_level", "MEDIUM")).upper()
        if risk_level not in ["HIGH", "MEDIUM", "LOW"]:
            risk_level = "MEDIUM"
        
        return RiskAssessment(
            risk_level=risk_level,
            explanation=result.get("explanation", "Unable to determine risk explanation."),
            suggested_action=result.get("suggested_action", "Review manually."),
            raw_response=response
        )
    
    def _fallback_assessment(
        self,
        email_data: dict,
        erp_data: Optional[dict],
        delay_days: int,
        change_type: str
    ) -> RiskAssessment:
        """
        Rule-based fallback when LLM is unavailable.
        """
        # Determine risk level based on delay
        if change_type == "EARLY":
            risk_level = "LOW"
            explanation = f"Delivery arriving {abs(delay_days)} days early. May need to arrange storage capacity."
            action = "Confirm warehouse can receive early shipment."
        elif delay_days > 7:
            risk_level = "HIGH"
            explanation = f"Significant delay of {delay_days} days detected. Production schedule likely impacted."
            action = "Escalate to supply chain manager. Contact supplier for expedite options."
        elif delay_days > 3:
            risk_level = "MEDIUM"
            explanation = f"Moderate delay of {delay_days} days. May affect downstream production."
            action = "Monitor closely and prepare contingency plan."
        elif delay_days > 0:
            risk_level = "LOW"
            explanation = f"Minor delay of {delay_days} days. Within acceptable tolerance."
            action = "Acknowledge and update delivery schedule."
        else:
            risk_level = "LOW"
            explanation = "No significant delivery change detected."
            action = "No action required."
        
        return RiskAssessment(
            risk_level=risk_level,
            explanation=explanation,
            suggested_action=action,
            raw_response="[Fallback rule-based assessment]"
        )


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

_reasoner: Optional[RAGReasoner] = None


def assess_risk(
    email_data: dict,
    erp_data: Optional[dict] = None,
    rag_context: Optional[list[dict]] = None,
    delay_days: int = 0,
    change_type: str = "NO_CHANGE"
) -> RiskAssessment:
    """
    Assess risk using RAG-enhanced reasoning.
    
    Args:
        email_data: Parsed supplier email with order_id, sku, etc.
        erp_data: ERP purchase order record
        rag_context: Retrieved context from vector DB
        delay_days: Delay in days from ERP comparison
        change_type: DELAY, EARLY, or NO_CHANGE
    
    Returns:
        RiskAssessment with risk_level, explanation, suggested_action
    
    Example:
        >>> result = assess_risk(
        ...     email_data={"order_id": "MO-1042", "sku": "CTRL-1001", ...},
        ...     erp_data={"delivery_date": "2025-08-15", ...},
        ...     rag_context=[{"text": "Supplier SUP-01 reliability 0.72", ...}],
        ...     delay_days=7,
        ...     change_type="DELAY"
        ... )
        >>> print(result.risk_level)
        "HIGH"
    """
    global _reasoner
    if _reasoner is None:
        _reasoner = RAGReasoner()
    
    return _reasoner.assess_risk(
        email_data=email_data,
        erp_data=erp_data,
        rag_context=rag_context or [],
        delay_days=delay_days,
        change_type=change_type
    )


def assess_risk_json(
    email_data: dict,
    erp_data: Optional[dict] = None,
    rag_context: Optional[list[dict]] = None,
    delay_days: int = 0,
    change_type: str = "NO_CHANGE"
) -> dict:
    """
    Assess risk and return as JSON-serializable dict.
    
    Returns:
        {
            "risk_level": "HIGH" | "MEDIUM" | "LOW",
            "explanation": "...",
            "suggested_action": "..."
        }
    """
    result = assess_risk(email_data, erp_data, rag_context, delay_days, change_type)
    return {
        "risk_level": result.risk_level,
        "explanation": result.explanation,
        "suggested_action": result.suggested_action
    }
