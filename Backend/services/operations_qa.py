"""
Hugo - Operational Question Answering Service

Uses Ollama (gemma:2b) to answer analytical questions about procurement,
production, and inventory operations.

Acts as a procurement operations copilot for strategic decision-making.
"""

import logging
import requests
import json
from typing import Optional, Dict, Any, List

from services.json_repair import attempt_json_repair, clean_json_text

logger = logging.getLogger("hugo.operations_qa")


class OperationalAnswer:
    """Structured operational question answer."""
    
    def __init__(
        self,
        question: str,
        answer: str,
        reasoning_steps: List[str],
        constraints: List[str],
        bottlenecks: List[str],
        confidence: str = "high",
        raw_response: str = "",
        error: Optional[str] = None
    ):
        """
        Initialize operational answer.
        
        Args:
            question: Original question asked
            answer: Clear, plain-text final answer
            reasoning_steps: Step-by-step reasoning used
            constraints: Operational constraints identified
            bottlenecks: Supply chain bottlenecks identified
            confidence: "high", "medium", or "low"
            raw_response: Raw Ollama response
            error: Error message if any
        """
        self.question = question
        self.answer = answer
        self.reasoning_steps = reasoning_steps
        self.constraints = constraints
        self.bottlenecks = bottlenecks
        self.confidence = confidence
        self.raw_response = raw_response
        self.error = error
        self.is_error = error is not None
    
    def __str__(self) -> str:
        """Return formatted answer for display."""
        lines = []
        lines.append(f"Question: {self.question}")
        lines.append("")
        lines.append(f"Answer: {self.answer}")
        
        if self.constraints:
            lines.append("")
            lines.append("Constraints:")
            for constraint in self.constraints:
                lines.append(f"  - {constraint}")
        
        if self.bottlenecks:
            lines.append("")
            lines.append("Bottlenecks:")
            for bottleneck in self.bottlenecks:
                lines.append(f"  - {bottleneck}")
        
        if self.error:
            lines.append("")
            lines.append(f"Error: {self.error}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "question": self.question,
            "answer": self.answer,
            "reasoning_steps": self.reasoning_steps,
            "constraints": self.constraints,
            "bottlenecks": self.bottlenecks,
            "confidence": self.confidence,
            "is_error": self.is_error,
            "error": self.error
        }


def answer_operational_question(
    question: str,
    erp_data: Optional[Dict[str, Any]] = None,
    orders: Optional[List[Dict[str, Any]]] = None,
    inventory: Optional[Dict[str, Any]] = None,
    bom_data: Optional[Dict[str, Any]] = None,
    ollama_url: str = "http://localhost:11434",
    model: str = "gemma:2b"
) -> OperationalAnswer:
    """
    Answer operational questions about procurement, production, and inventory.
    
    Acts as a procurement operations copilot using step-by-step reasoning.
    
    Args:
        question: Analytical question about operations
            Examples:
            - "How many scooters of model X can be built next week?"
            - "Which parts are current bottlenecks?"
            - "What happens if demand increases by 20%?"
            - "Which suppliers are at risk of delays?"
            - "What is our inventory turnover rate?"
        
        erp_data: ERP system data (dict with operational context)
            Keys might include: production_capacity, lead_times, etc.
        
        orders: List of active/upcoming orders (list of dicts)
            Keys might include: order_id, quantity, due_date, status, etc.
        
        inventory: Current inventory levels (dict)
            Keys might include: sku, quantity_on_hand, min_level, etc.
        
        bom_data: Bill of materials data (dict)
            Keys might include: product_id, components, quantities, etc.
        
        ollama_url: Ollama API endpoint
        model: Model name (gemma:2b)
    
    Returns:
        OperationalAnswer with clear answer, reasoning, constraints, bottlenecks
    
    Example:
        >>> result = answer_operational_question(
        ...     question="How many scooters can we build next week?",
        ...     orders=[{"order_id": "O-123", "quantity": 50, ...}],
        ...     inventory={"MOTOR-A": 200, "FRAME-X": 150, ...},
        ...     bom_data={"MODEL-X": {"MOTOR-A": 1, "FRAME-X": 1, ...}}
        ... )
        >>> print(result.answer)
        We can build 150 scooters next week...
        >>> print(result.constraints)
        ["Frame inventory is limiting factor at 150 units"]
    """
    
    # Build the operational analysis prompt
    prompt = _build_operational_prompt(question, erp_data, orders, inventory, bom_data)
    
    try:
        # Call Ollama
        response = _call_ollama(prompt, ollama_url, model)
        
        # Parse structured response
        answer_data = _parse_operational_response(response, ollama_url, model)
        
        logger.info(f"Operational question answered: {question[:50]}...")
        
        return OperationalAnswer(
            question=question,
            answer=answer_data.get("answer", response),
            reasoning_steps=answer_data.get("reasoning_steps", []),
            constraints=answer_data.get("constraints", []),
            bottlenecks=answer_data.get("bottlenecks", []),
            confidence=answer_data.get("confidence", "medium"),
            raw_response=response
        )
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot reach Ollama at {ollama_url}: {e}")
        return _safe_error_answer(
            question=question,
            error=f"Cannot reach Ollama at {ollama_url}"
        )
    
    except requests.exceptions.Timeout as e:
        logger.error(f"Ollama request timeout: {e}")
        return _safe_error_answer(
            question=question,
            error="Ollama request timed out"
        )
    
    except Exception as e:
        logger.error(f"Error answering operational question: {e}")
        return _safe_error_answer(
            question=question,
            error=str(e)
        )


def _build_operational_prompt(
    question: str,
    erp_data: Optional[Dict[str, Any]],
    orders: Optional[List[Dict[str, Any]]],
    inventory: Optional[Dict[str, Any]],
    bom_data: Optional[Dict[str, Any]]
) -> str:
    """Build the operational analysis prompt for Ollama."""
    
    # Format ERP data
    erp_str = "No ERP data available"
    if erp_data:
        erp_items = []
        for key, value in list(erp_data.items())[:10]:  # Limit to 10 items
            erp_items.append(f"  {key}: {value}")
        erp_str = "\n".join(erp_items) if erp_items else "ERP data: (empty)"
    
    # Format orders
    orders_str = "No active orders"
    if orders:
        orders_items = []
        for order in orders[:5]:  # Limit to 5 orders for brevity
            order_id = order.get("order_id", "Unknown")
            qty = order.get("quantity", "?")
            due = order.get("due_date", "?")
            status = order.get("status", "?")
            orders_items.append(f"  {order_id}: {qty} units, due {due}, status {status}")
        orders_str = "\n".join(orders_items) if orders_items else "No orders found"
    
    # Format inventory
    inventory_str = "No inventory data"
    if inventory:
        inv_items = []
        for sku, qty in list(inventory.items())[:10]:  # Limit to 10 items
            inv_items.append(f"  {sku}: {qty} units")
        inventory_str = "\n".join(inv_items) if inv_items else "Inventory: (empty)"
    
    # Format BOM data
    bom_str = "No BOM data"
    if bom_data:
        bom_items = []
        for product, components in list(bom_data.items())[:3]:  # Limit to 3 products
            if isinstance(components, dict):
                comp_str = ", ".join([f"{k}:{v}" for k, v in list(components.items())[:5]])
                bom_items.append(f"  {product}: {comp_str}")
            else:
                bom_items.append(f"  {product}: {components}")
        bom_str = "\n".join(bom_items) if bom_items else "BOM: (empty)"
    
    prompt = f"""You are a procurement operations copilot for a manufacturing company.

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "answer": "string (clear, direct answer)",
    "reasoning_steps": ["string"],
    "constraints": ["string"],
    "bottlenecks": ["string"],
    "confidence": "high" | "medium" | "low"
}}

=== QUESTION ===
{question}

=== OPERATIONAL DATA ===

ERP System Data:
{erp_str}

Active Orders:
{orders_str}

Current Inventory Levels:
{inventory_str}

Bill of Materials:
{bom_str}

=== TASK ===
Answer the question step by step. Think through:
1. What data is relevant to this question?
2. What are the current constraints?
3. What bottlenecks exist?
4. What is the final answer?

Provide:
- answer: A clear, direct answer to the question
- reasoning_steps: Step-by-step reasoning (array of strings)
- constraints: Operational constraints identified (array of strings)
- bottlenecks: Supply chain bottlenecks (array of strings)
- confidence: Your confidence level (high/medium/low)

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null or empty array [].
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else.

Be concise. Focus on facts and numbers."""
    
    return prompt


def _call_ollama(
    prompt: str,
    ollama_url: str,
    model: str
) -> str:
    """
    Call Ollama API with operational question.
    
    Args:
        prompt: The operational analysis prompt
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
        "temperature": 0.3  # Slightly higher than risk assessment for reasoning
    }
    
    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()
    
    result = response.json()
    return result.get("response", "").strip()


def _parse_operational_response(response: str, ollama_url: str, model: str) -> Dict[str, Any]:
    """
    Parse JSON response from Ollama.
    
    Args:
        response: Raw response text from Ollama (should be JSON)
        ollama_url: Ollama API base URL
        model: Model name
    
    Returns:
        Dict with parsed components (answer, reasoning_steps, constraints, bottlenecks, confidence)
    """
    
    parsed = {
        "answer": "",
        "reasoning_steps": [],
        "constraints": [],
        "bottlenecks": [],
        "confidence": "medium"
    }
    
    text = clean_json_text(response)
    
    try:
        # Parse JSON
        result = json.loads(text)
        
        # Extract fields with defaults
        parsed["answer"] = result.get("answer", "")
        parsed["reasoning_steps"] = result.get("reasoning_steps", [])
        parsed["constraints"] = result.get("constraints", [])
        parsed["bottlenecks"] = result.get("bottlenecks", [])
        parsed["confidence"] = result.get("confidence", "medium").lower()
        
        # Validate confidence value
        if parsed["confidence"] not in ["high", "medium", "low"]:
            parsed["confidence"] = "medium"
        
        return parsed
    
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parsing failed: {str(e)[:100]}")
        
        # Attempt to repair JSON with Ollama
        repaired = attempt_json_repair(response, e, ollama_url, model)
        if repaired is not None:
            # Extract fields with defaults
            parsed["answer"] = repaired.get("answer", "")
            parsed["reasoning_steps"] = repaired.get("reasoning_steps", [])
            parsed["constraints"] = repaired.get("constraints", [])
            parsed["bottlenecks"] = repaired.get("bottlenecks", [])
            parsed["confidence"] = repaired.get("confidence", "medium").lower()
            
            # Validate confidence value
            if parsed["confidence"] not in ["high", "medium", "low"]:
                parsed["confidence"] = "medium"
            
            return parsed
        
        # If repair failed, try text fallback
        logger.warning(f"JSON repair failed, falling back to text parsing")
        
        # Try to extract from text sections (old format fallback)
        sections = response.split("\n\n")
        for section in sections:
            section = section.strip()
            
            if section.startswith("ANSWER:"):
                parsed["answer"] = section.replace("ANSWER:", "").strip()
            elif section.startswith("REASONING:"):
                reasoning_text = section.replace("REASONING:", "").strip()
                parsed["reasoning_steps"] = [
                    line.strip() for line in reasoning_text.split("\n")
                    if line.strip() and line.strip().startswith("-")
                ]
            elif section.startswith("CONSTRAINTS:"):
                constraints_text = section.replace("CONSTRAINTS:", "").strip()
                parsed["constraints"] = [
                    line.strip() for line in constraints_text.split("\n")
                    if line.strip() and line.strip().startswith("-")
                ]
            elif section.startswith("BOTTLENECKS:"):
                bottlenecks_text = section.replace("BOTTLENECKS:", "").strip()
                parsed["bottlenecks"] = [
                    line.strip() for line in bottlenecks_text.split("\n")
                    if line.strip() and line.strip().startswith("-")
                ]
            elif section.startswith("CONFIDENCE:"):
                conf_text = section.replace("CONFIDENCE:", "").strip().lower()
                if any(word in conf_text for word in ["high", "confident"]):
                    parsed["confidence"] = "high"
                elif any(word in conf_text for word in ["low", "uncertain"]):
                    parsed["confidence"] = "low"
                else:
                    parsed["confidence"] = "medium"
        
        # Fallback: use entire response as answer if no sections found
        if not parsed["answer"] and not parsed["reasoning_steps"]:
            parsed["answer"] = response
        
        return parsed


def _safe_error_answer(
    question: str,
    error: str
) -> OperationalAnswer:
    """
    Return a safe error answer when Ollama fails.
    
    Args:
        question: Original question
        error: Error message
    
    Returns:
        OperationalAnswer indicating error
    """
    
    logger.warning(f"Cannot answer question due to error: {error}")
    
    return OperationalAnswer(
        question=question,
        answer="Unable to process question - Ollama service is unavailable.",
        reasoning_steps=["Error occurred while contacting Ollama API"],
        constraints=["Ollama service connectivity"],
        bottlenecks=[],
        confidence="low",
        error=error
    )


# Export public API
__all__ = [
    "OperationalAnswer",
    "answer_operational_question",
]
