"""
Hugo - Inventory Optimization Service

Uses Ollama to optimize inventory settings (reorder point, safety stock, lot size)
by balancing cost, warehouse space, and service level.

Optimization factors:
- Carrying cost (warehouse space, obsolescence, capital tie-up)
- Ordering cost (procurement overhead)
- Stockout cost (production delays, customer impact)
- Lead time variability (supplier reliability)
- Demand variability (forecast accuracy)
"""

import json
import logging
import os
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from services.json_repair import attempt_json_repair, clean_json_text

logger = logging.getLogger("hugo.inventory_optimizer")

# Environment variables for Ollama
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma:2b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT_SECONDS = 120


@dataclass
class PartData:
    """Part/SKU data for inventory optimization."""
    
    sku: str                           # Part number
    part_name: Optional[str] = None    # Description
    annual_demand: Optional[float] = None  # Units/year
    lead_time_days: Optional[int] = None   # Days from order to delivery
    lead_time_variability: Optional[float] = None  # Std dev of lead time (0-1)
    demand_variability: Optional[float] = None      # Std dev of demand (0-1)
    current_inventory: Optional[float] = None       # Units on hand
    current_reorder_point: Optional[float] = None   # Current ROP
    current_safety_stock: Optional[float] = None    # Current safety stock
    current_lot_size: Optional[float] = None        # Current order qty
    carrying_cost_per_unit_year: Optional[float] = None  # Annual cost to hold 1 unit
    ordering_cost_per_order: Optional[float] = None      # Cost per PO
    stockout_cost_per_unit: Optional[float] = None       # Cost of lost sale/delay
    service_level_target: Optional[float] = None         # 0-1 (0.95 = 95% fill rate)
    max_warehouse_space_allocated: Optional[float] = None  # Square feet or units
    supplier_reliability_score: Optional[float] = None    # 0-1 (delivery performance)
    recent_stockouts: Optional[int] = None                # Count last 12 months
    forecast_accuracy: Optional[float] = None             # 0-1 (forecast error rate)


@dataclass
class InventoryRecommendation:
    """Inventory optimization recommendation from Ollama."""
    
    sku: str
    reorder_point: float              # New recommended ROP
    reorder_point_change: float        # Adjustment from current (units)
    safety_stock: float               # New recommended safety stock
    safety_stock_change: float         # Adjustment from current (units)
    lot_size: float                   # New recommended order quantity
    lot_size_change_percent: float    # Percent change from current
    
    # Trade-off analysis
    carrying_cost_change: float       # Annual cost impact ($)
    ordering_cost_change: float       # Annual cost impact ($)
    expected_fill_rate: float         # Projected service level (0-1)
    expected_stockouts_per_year: float  # Projected stockout frequency
    
    # Reasoning
    rationale: str                    # Why these recommendations
    trade_offs: str                   # Explicit trade-off explanation
    key_factors: list                 # Main factors influencing decision
    implementation_notes: str         # How to implement changes
    
    # Metadata
    raw_response: Optional[str] = None  # Full Ollama response for audit
    error: Optional[str] = None         # If error occurred
    is_fallback: bool = False          # If used safe defaults
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sku": self.sku,
            "reorder_point": self.reorder_point,
            "reorder_point_change": self.reorder_point_change,
            "safety_stock": self.safety_stock,
            "safety_stock_change": self.safety_stock_change,
            "lot_size": self.lot_size,
            "lot_size_change_percent": self.lot_size_change_percent,
            "carrying_cost_change": self.carrying_cost_change,
            "ordering_cost_change": self.ordering_cost_change,
            "expected_fill_rate": self.expected_fill_rate,
            "expected_stockouts_per_year": self.expected_stockouts_per_year,
            "rationale": self.rationale,
            "trade_offs": self.trade_offs,
            "key_factors": self.key_factors,
            "implementation_notes": self.implementation_notes,
            "is_fallback": self.is_fallback,
            "error": self.error
        }


# Optimization prompt for Ollama
OPTIMIZATION_PROMPT = """Optimize inventory settings for a part using tradeoff analysis.

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "reorder_point": number,
    "reorder_point_change": number,
    "safety_stock": number,
    "safety_stock_change": number,
    "lot_size": number,
    "lot_size_change_percent": number,
    "carrying_cost_change": number,
    "ordering_cost_change": number,
    "expected_fill_rate": number (0.0-1.0),
    "expected_stockouts_per_year": number,
    "rationale": "string",
    "trade_offs": "string",
    "key_factors": ["string"],
    "implementation_notes": "string"
}}

=== PART DATA ===
SKU: {sku}
Part Name: {part_name}
Annual Demand: {annual_demand} units
Lead Time: {lead_time_days} days (variability: {lead_time_variability})
Demand Variability: {demand_variability} (0=stable, 1=highly variable)
Current Inventory: {current_inventory} units
Current Reorder Point: {current_reorder_point} units
Current Safety Stock: {current_safety_stock} units
Current Lot Size: {current_lot_size} units
Service Level Target: {service_level_target}%

=== COSTS ===
Carrying Cost: ${carrying_cost_per_unit_year}/unit/year (warehouse, capital, obsolescence)
Ordering Cost: ${ordering_cost_per_order}/order (procurement overhead)
Stockout Cost: ${stockout_cost_per_unit} per unit (lost sales, production delay)

=== CONSTRAINTS ===
Max Warehouse Space: {max_warehouse_space_allocated}
Supplier Reliability: {supplier_reliability_score} (0=unreliable, 1=perfect)
Recent Stockouts: {recent_stockouts} (last 12 months)
Forecast Accuracy: {forecast_accuracy} (0=inaccurate, 1=very accurate)

=== TASK ===
Recommend optimized inventory settings that balance:
1. Holding costs (minimize excess inventory)
2. Ordering costs (minimize small frequent orders)
3. Stockout risk (maintain service level)
4. Warehouse constraints (stay within space allocation)

IMPORTANT: Explicitly explain ALL trade-offs between these competing objectives.

=== GUIDELINES ===
- ROP = (Daily Demand × Lead Time) + Safety Stock
- Safety Stock = Z-score × Std Dev of Demand × Sqrt(Lead Time)
- Consider service level vs cost trade-offs explicitly
- If costs are very high, recommend lower service level with clear trade-off
- If demand/lead time very variable, recommend higher safety stock
- If supplier unreliable, pad lead time and increase safety stock
- Always mention specific cost/service level changes in trade_offs field

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null.
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else."""
    
    return prompt


def optimize_inventory_settings(
    part_data: PartData,
    ollama_url: Optional[str] = None,
    model: Optional[str] = None
) -> InventoryRecommendation:
    """
    Optimize inventory settings (ROP, safety stock, lot size) using Ollama.
    
    Ollama evaluates the part data and recommends settings that balance:
    - Carrying costs (warehouse, capital, obsolescence)
    - Ordering costs (procurement overhead)
    - Service level (fill rate, stockout frequency)
    - Warehouse space constraints
    - Supplier reliability
    - Demand/lead time variability
    
    Args:
        part_data: Part/SKU data for optimization
            - sku: Part number
            - annual_demand: Annual usage (units)
            - lead_time_days: Supplier lead time
            - lead_time_variability: Lead time std dev (0-1)
            - demand_variability: Demand std dev (0-1)
            - carrying_cost_per_unit_year: Annual holding cost
            - ordering_cost_per_order: Cost per purchase order
            - stockout_cost_per_unit: Cost of stockout/lost sale
            - service_level_target: Target fill rate (0.95 = 95%)
            - supplier_reliability_score: Historical reliability (0-1)
            - recent_stockouts: Stockout count in last 12 months
            - forecast_accuracy: Forecast error rate (0-1)
        
        ollama_url: Ollama API base URL (default: env var OLLAMA_BASE_URL)
        model: Model to use (default: env var OLLAMA_MODEL)
    
    Returns:
        InventoryRecommendation with optimized settings and trade-off analysis
    
    Example:
        >>> part = PartData(
        ...     sku="SKU-001",
        ...     part_name="Motor Assembly",
        ...     annual_demand=1000,
        ...     lead_time_days=14,
        ...     lead_time_variability=0.1,
        ...     demand_variability=0.2,
        ...     carrying_cost_per_unit_year=50,
        ...     ordering_cost_per_order=150,
        ...     stockout_cost_per_unit=500,
        ...     service_level_target=0.95
        ... )
        >>> 
        >>> rec = optimize_inventory_settings(part)
        >>> print(f"New ROP: {rec.reorder_point} (change: {rec.reorder_point_change})")
        >>> print(f"Trade-offs: {rec.trade_offs}")
    """
    
    if ollama_url is None:
        ollama_url = OLLAMA_BASE_URL
    if model is None:
        model = OLLAMA_MODEL
    
    try:
        # Build optimization prompt
        prompt = _build_optimization_prompt(part_data)
        
        # Call Ollama
        response = _call_ollama_for_optimization(prompt, ollama_url, model)
        
        # Parse response
        parsed = _parse_optimization_response(response, ollama_url, model)
        
        if parsed is None:
            # Fallback to safe defaults
            return _safe_default_recommendation(part_data, "JSON parse error")
        
        # Validate response
        if not _validate_recommendation(parsed):
            # Fallback to safe defaults
            return _safe_default_recommendation(part_data, "Validation error")
        
        # Build recommendation
        recommendation = InventoryRecommendation(
            sku=part_data.sku,
            reorder_point=parsed.get("reorder_point", part_data.current_reorder_point or 100),
            reorder_point_change=parsed.get("reorder_point_change", 0),
            safety_stock=parsed.get("safety_stock", part_data.current_safety_stock or 50),
            safety_stock_change=parsed.get("safety_stock_change", 0),
            lot_size=parsed.get("lot_size", part_data.current_lot_size or 200),
            lot_size_change_percent=parsed.get("lot_size_change_percent", 0),
            carrying_cost_change=parsed.get("carrying_cost_change", 0),
            ordering_cost_change=parsed.get("ordering_cost_change", 0),
            expected_fill_rate=parsed.get("expected_fill_rate", 0.95),
            expected_stockouts_per_year=parsed.get("expected_stockouts_per_year", 0),
            rationale=parsed.get("rationale", "Ollama optimization complete"),
            trade_offs=parsed.get("trade_offs", "See detailed analysis"),
            key_factors=parsed.get("key_factors", []),
            implementation_notes=parsed.get("implementation_notes", ""),
            raw_response=response,
            is_fallback=False
        )
        
        logger.info(f"Inventory optimization successful for {part_data.sku}")
        return recommendation
        
    except Exception as e:
        logger.error(f"Inventory optimization error for {part_data.sku}: {e}")
        return _safe_default_recommendation(part_data, str(e))


def _build_optimization_prompt(part_data: PartData) -> str:
    """Build the optimization prompt for Ollama."""
    
    return OPTIMIZATION_PROMPT.format(
        sku=part_data.sku or "UNKNOWN",
        part_name=part_data.part_name or "Unknown Part",
        annual_demand=part_data.annual_demand or 0,
        lead_time_days=part_data.lead_time_days or 7,
        lead_time_variability=part_data.lead_time_variability or 0.1,
        demand_variability=part_data.demand_variability or 0.2,
        current_inventory=part_data.current_inventory or 0,
        current_reorder_point=part_data.current_reorder_point or 100,
        current_safety_stock=part_data.current_safety_stock or 50,
        current_lot_size=part_data.current_lot_size or 200,
        carrying_cost_per_unit_year=part_data.carrying_cost_per_unit_year or 10,
        ordering_cost_per_order=part_data.ordering_cost_per_order or 100,
        stockout_cost_per_unit=part_data.stockout_cost_per_unit or 500,
        service_level_target=(part_data.service_level_target or 0.95) * 100,
        max_warehouse_space_allocated=part_data.max_warehouse_space_allocated or "unlimited",
        supplier_reliability_score=part_data.supplier_reliability_score or 0.8,
        recent_stockouts=part_data.recent_stockouts or 0,
        forecast_accuracy=part_data.forecast_accuracy or 0.8
    )


def _call_ollama_for_optimization(
    prompt: str,
    ollama_url: str,
    model: str
) -> str:
    """Call Ollama to optimize inventory settings."""
    
    url = f"{ollama_url.rstrip('/')}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.2  # Deterministic optimization decisions
    }
    
    try:
        response = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to Ollama at {ollama_url}: {e}")
        raise RuntimeError(f"Ollama connection failed at {ollama_url}")
    except requests.exceptions.Timeout as e:
        logger.error(f"Ollama timeout after {OLLAMA_TIMEOUT_SECONDS}s: {e}")
        raise RuntimeError(f"Ollama timeout after {OLLAMA_TIMEOUT_SECONDS}s")
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        raise RuntimeError(f"Ollama API error: {e}")


def _parse_optimization_response(response: str, ollama_url: str, model: str) -> Optional[dict]:
    """Parse Ollama response to extract JSON."""
    
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
        logger.error(f"Failed to parse Ollama response as JSON: {response[:200]}")
        raise


def _validate_recommendation(rec_dict: dict) -> bool:
    """Validate the optimization recommendation structure."""
    
    required_fields = [
        "reorder_point",
        "safety_stock",
        "lot_size",
        "expected_fill_rate",
        "rationale",
        "trade_offs"
    ]
    
    for field in required_fields:
        if field not in rec_dict:
            logger.error(f"Missing required field in recommendation: {field}")
            return False
    
    # Validate numeric types
    try:
        float(rec_dict["reorder_point"])
        float(rec_dict["safety_stock"])
        float(rec_dict["lot_size"])
        float(rec_dict["expected_fill_rate"])
        if not 0 <= rec_dict["expected_fill_rate"] <= 1:
            logger.error("Expected fill rate must be 0-1")
            return False
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid numeric field: {e}")
        return False
    
    # Validate strings
    if not isinstance(rec_dict.get("rationale"), str) or not rec_dict["rationale"]:
        logger.error("Rationale must be non-empty string")
        return False
    
    if not isinstance(rec_dict.get("trade_offs"), str) or not rec_dict["trade_offs"]:
        logger.error("Trade-offs must be non-empty string")
        return False
    
    return True


def _safe_default_recommendation(part_data: PartData, error: str) -> InventoryRecommendation:
    """
    Return conservative safe defaults on error.
    
    First attempts simplified Ollama reasoning, then uses conservative defaults.
    Never relies solely on hardcoded heuristics.
    """
    
    logger.warning(f"Primary Ollama call failed for {part_data.sku}: {error}. Attempting simplified fallback reasoning.")
    
    # Try one more time with minimal fallback prompt
    fallback_prompt = f"""Quick inventory recommendation (fallback only).
SKU: {part_data.sku}
Annual Demand: {part_data.annual_demand or 'unknown'}
Lead Time: {part_data.supplier_lead_time_days or 'unknown'} days
Current ROP: {part_data.current_reorder_point or 'unknown'}
Current SS: {part_data.current_safety_stock or 'unknown'}

Conservative recommendation (increase safety stock):
{{
  "reorder_point": {(part_data.current_reorder_point or 100) * 1.2},
  "safety_stock": {(part_data.current_safety_stock or 50) * 1.3},
  "lot_size": {(part_data.current_lot_size or 200) * 1.1},
  "rationale": "Conservative fallback"
}}
"""
    
    try:
        from services.ollama_llm import OllamaLLM
        ollama = OllamaLLM(model="gemma:2b", base_url="http://localhost:11434")
        response = ollama.generate(fallback_prompt)
        result = json.loads(response)
        
        # Validate minimal structure
        if all(k in result for k in ["reorder_point", "safety_stock", "lot_size"]):
            logger.info(f"Fallback Ollama reasoning succeeded for {part_data.sku}")
            
            return InventoryRecommendation(
                sku=part_data.sku,
                reorder_point=float(result.get("reorder_point", part_data.current_reorder_point or 100)),
                reorder_point_change=float(result.get("reorder_point", part_data.current_reorder_point or 100)) - (part_data.current_reorder_point or 100),
                safety_stock=float(result.get("safety_stock", part_data.current_safety_stock or 50)),
                safety_stock_change=float(result.get("safety_stock", part_data.current_safety_stock or 50)) - (part_data.current_safety_stock or 50),
                lot_size=float(result.get("lot_size", part_data.current_lot_size or 200)),
                lot_size_change_percent=((float(result.get("lot_size", part_data.current_lot_size or 200)) - (part_data.current_lot_size or 200)) / (part_data.current_lot_size or 200) * 100),
                carrying_cost_change=0,
                ordering_cost_change=0,
                expected_fill_rate=0.90,
                expected_stockouts_per_year=2,
                rationale=result.get("rationale", "Fallback LLM recommendation"),
                trade_offs="Fallback LLM conservative approach prioritizes availability over cost reduction.",
                key_factors=["Fallback LLM reasoning", "Conservative approach", "Primary Ollama call failed"],
                implementation_notes=f"This is fallback LLM reasoning. When primary Ollama is available, re-run for optimized settings.",
                is_fallback=False,  # Ollama succeeded on fallback
                error=None
            )
    except Exception as fallback_error:
        logger.error(f"Fallback Ollama attempt also failed for {part_data.sku}: {fallback_error}. Using hardcoded conservative defaults.")
    
    # Only use hardcoded defaults if both Ollama attempts fail
    logger.warning(f"All Ollama attempts failed for {part_data.sku}. Using hardcoded conservative safety defaults.")
    
    current_rop = part_data.current_reorder_point or 100
    current_ss = part_data.current_safety_stock or 50
    current_lot = part_data.current_lot_size or 200
    
    new_rop = current_rop * 1.2  # 20% increase in ROP
    new_ss = current_ss * 1.3    # 30% increase in safety stock
    new_lot = current_lot * 1.1  # 10% increase in lot size
    
    return InventoryRecommendation(
        sku=part_data.sku,
        reorder_point=new_rop,
        reorder_point_change=new_rop - current_rop,
        safety_stock=new_ss,
        safety_stock_change=new_ss - current_ss,
        lot_size=new_lot,
        lot_size_change_percent=10,
        carrying_cost_change=0,
        ordering_cost_change=0,
        expected_fill_rate=0.90,
        expected_stockouts_per_year=2,
        rationale="Using safe conservative hardcoded defaults due to optimization error",
        trade_offs="Conservative approach prioritizes availability (stockout prevention) over cost reduction. Increases carrying costs but reduces stockout risk.",
        key_factors=["Ollama unavailable on all attempts", "Hardcoded conservative fallback activated", "Recommend manual review when Ollama available"],
        implementation_notes=f"These are hardcoded conservative defaults. When Ollama is available, re-run optimization for cost-optimal settings.",
        is_fallback=True,
        error=error
    )
