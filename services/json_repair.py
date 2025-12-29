"""
Hugo - JSON Repair Service

Automatically repairs malformed JSON responses from LLM.
If JSON parsing fails, asks LLM to fix it and retries once.

Design:
- Non-intrusive: only called when parsing fails
- Single retry: asks LLM to fix, then accepts result or falls back
- Logged: all failures clearly logged
- No hardcoded logic: uses LLM to repair, not regex hacks
"""

import json
import logging
import re
from typing import Optional, Dict, Any
from huggingface_hub import InferenceClient

logger = logging.getLogger("hugo.json_repair")

# Repair prompt for Ollama
# Updated Repair Prompt
REPAIR_PROMPT = """Fix the following JSON to match this schema exactly. Output JSON only.

INVALID RESPONSE:
{invalid_response}

ERROR:
{error_message}

Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null.
Output a single valid JSON object and nothing else."""


def normalize_json_output(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize JSON output to handle null values before Pydantic validation.
    
    Rules:
    - null -> [] for list fields (based on key suffix or known keys)
    - null -> 0 for numeric fields (if likely optional number)
    - null -> "" for known string fields
    """
    if not isinstance(data, dict):
        return data

    normalized = data.copy()
    
    # Known list keys across all schemas
    list_keys = {
        "sku", "affected_items", "labels", "items", "similar_incidents", 
        "resolution_patterns", "affected_operations", "recommended_actions"
    }
    
    # Known numeric keys
    numeric_keys = {
        "delay_days", "quantity_change", "financial_impact_estimate", 
        "risk_score", "confidence", "total_past_issues", "avg_delay_days", "supplier_reliability_score"
    }
    
    # Known string keys (optional)
    string_keys = {
        "reason", "supplier_reason", "po_reference", "impact_summary", "reasoning", "order_id"
    }

    for key, value in normalized.items():
        # Rule 1: Lists
        if key in list_keys and value is None:
            logger.info(f"Normalizing {key}: null -> []")
            normalized[key] = []
            
        # Rule 2: Numeric (Optional -> 0)
        elif key in numeric_keys and value is None:
            logger.info(f"Normalizing {key}: null -> 0")
            normalized[key] = 0
            
        # Rule 3: Strings (Optional -> "")
        elif key in string_keys and value is None:
            logger.info(f"Normalizing {key}: null -> \"\"")
            normalized[key] = ""
            
        # Recursive cleaning for nested dicts (though most schemas are flat-ish)
        elif isinstance(value, dict):
            normalized[key] = normalize_json_output(value)
            
        # Handle list of dicts (e.g. items)
        elif isinstance(value, list):
            new_list = []
            for item in value:
                if isinstance(item, dict):
                    new_list.append(normalize_json_output(item))
                else:
                    new_list.append(item)
            normalized[key] = new_list
            
    return normalized


def attempt_json_repair(
    raw_response: str,
    parse_error: Exception,
    ollama_url: str = "",  # Deprecated, kept for compatibility
    model: str = "google/flan-t5-large",
    timeout: int = 30
) -> Optional[dict[str, Any]]:
    """
    Attempt to repair malformed JSON by asking LLM to fix it.
    
    Uses Hugging Face Inference API for repair.
    
    Args:
        raw_response: Original malformed response
        parse_error: JSON parsing error
        ollama_url: Deprecated, kept for compatibility
        model: HF model identifier
        timeout: Request timeout
        
    Returns:
        Repaired JSON dict or empty dict on failure
    """
    
    logger.warning(f"JSON parsing failed: {str(parse_error)[:100]}")
    logger.info("Starting self-healing JSON repair (max 2 attempts)...")
    
    current_response = raw_response
    current_error = parse_error
    
    for attempt in range(2):
        try:
            # Build repair prompt
            repair_prompt = REPAIR_PROMPT.format(
                invalid_response=current_response[:1000], 
                error_message=str(current_error)[:500]
            )
            
            logger.info(f"Repair validation attempt {attempt + 1}/2")
            
            # Call Hugging Face API
            fixed_response = _call_hf_for_repair(repair_prompt, model, timeout)
            
            # Clean and parse
            cleaned_fixed = clean_json_text(fixed_response)
            result = json.loads(cleaned_fixed)
            
            # Normalize immediately after parse
            normalized_result = normalize_json_output(result)
            
            logger.info(f"✅ JSON repair successful on attempt {attempt + 1}")
            return normalized_result
        
        except json.JSONDecodeError as e:
            logger.warning(f"Repair attempt {attempt + 1} failed: {e}")
            current_error = e
            # Loop again with the new error if we have attempts left
            
        except Exception as e:
            logger.error(f"Unexpected error during repair: {e}")
            break
            
    logger.error("❌ All JSON repair attempts failed. Returning safe empty object.")
    return {}  # Return safe empty object instead of None


def _call_hf_for_repair(
    prompt: str,
    model: str,
    timeout: int
) -> str:
    """
    Call Hugging Face Inference API to repair malformed JSON.
    Uses text_generation API.
    """
    import os
    
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError("HF_TOKEN environment variable is required for JSON repair")
    
    client = InferenceClient(model=model, token=token)
    
    try:
        # Use text generation API for flan-t5 models
        response = client.text_generation(
            prompt,
            max_new_tokens=1000,
            temperature=0.1,
            seed=42
        )
        
        return response.strip()
    except Exception as e:
        logger.error(f"HF repair call failed: {e}")
        raise


def clean_json_text(text: str) -> str:
    """
    Clean common JSON formatting issues before parsing.
    
    Handles:
    - Markdown code blocks (```json ... ```)
    - Leading/trailing whitespace
    - Common escape issues
    
    Args:
        text: Raw response text
    
    Returns:
        Cleaned text ready for json.loads()
    """
    
    text = text.strip()
    
    # Remove markdown code blocks if present
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
    
    return text


# Export public API
__all__ = [
    "attempt_json_repair",
    "clean_json_text",
    "normalize_json_output",
]
