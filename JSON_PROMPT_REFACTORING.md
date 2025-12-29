# Ollama JSON Prompt Refactoring - Complete Implementation

## Overview

All Ollama prompts across the Hugo procurement agent have been refactored to **strictly enforce valid JSON output**. This improves reliability and consistency for local LLM inference with gemma:2b.

## Changes Summary

### Files Modified

1. **services/ollama_risk_assessor.py**
   - `_build_assessment_prompt()` - Risk assessment prompt
2. **services/alert_decision.py**
   - `_build_alert_evaluation_prompt()` - Alert decision prompt
3. **services/inventory_optimizer.py**
   - `OPTIMIZATION_PROMPT` constant - Inventory optimization prompt
4. **services/operations_qa.py**
   - `_build_operational_prompt()` - Operations Q&A prompt
   - `_parse_operational_response()` - Updated to parse JSON instead of plain text
5. **services/delivery_detector.py**
   - `EXTRACTION_PROMPT` constant - Delivery detection prompt
   - `RETRY_PROMPT` constant - Fallback prompt for retries
6. **services/risk_engine.py**
   - `RISK_PROMPT` constant - Risk assessment prompt
7. **services/rag_reasoner.py**
   - `REASONING_PROMPT` constant - RAG reasoning prompt

## Refactoring Rules Applied Uniformly

### Rule 1: Explicit JSON Schema

Every prompt now includes an explicit JSON schema at the beginning:

```
=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{
    "field_name": type | null,
    "array_field": ["string"],
    ...
}
```

**Example:**

```python
prompt = f"""...
=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "risk_level": "low" | "medium" | "high" | "critical",
    "risk_score": number (0.0-1.0),
    "drivers": ["string"],
    "recommended_actions": ["string"]
}}
...
"""
```

### Rule 2: Explicit Output Instructions

Every prompt ends with standardized output rules:

```
=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null or empty array [].
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else.
```

### Rule 3: Schema BEFORE Task Description

The JSON schema always appears **before** the task description:

**✅ CORRECT ORDER:**

```
1. JSON Schema definition
2. Input data
3. Task description
4. Output rules
```

**❌ AVOID:**

```
1. Task description
2. Input data
3. JSON schema (too late, model already thinking about format)
```

### Rule 4: Clear Field Types

Every field in the schema includes type information:

```
"field": string
"count": number
"is_active": true | false
"items": ["string"]
"metadata": {...} | null
```

**Not:**

```
"field": any
"count": <number>
```

## Prompts Refactored

### 1. Risk Assessment (ollama_risk_assessor.py)

**Location:** `_build_assessment_prompt()`

**Schema:**

```json
{
    "risk_level": "low" | "medium" | "high" | "critical",
    "risk_score": 0.0-1.0,
    "drivers": ["string"],
    "recommended_actions": ["string"]
}
```

**Key Changes:**

- ✅ Added explicit JSON schema before task
- ✅ Removed "or" syntax (use pipes |)
- ✅ Added clear output rules
- ✅ Removed markdown block indicators

---

### 2. Alert Decision (alert_decision.py)

**Location:** `_build_alert_evaluation_prompt()`

**Schema:**

```json
{
    "trigger_alert": true | false,
    "urgency": "low" | "medium" | "high" | "critical",
    "reason": "string (1-2 sentences)",
    "should_escalate": true | false,
    "recommended_actions": ["string"] | null
}
```

**Key Changes:**

- ✅ JSON schema moved to top
- ✅ Boolean values explicitly typed (true | false)
- ✅ String length hints added (1-2 sentences)
- ✅ Clear guidelines for decision logic

---

### 3. Inventory Optimization (inventory_optimizer.py)

**Location:** `OPTIMIZATION_PROMPT` constant

**Schema:**

```json
{
    "reorder_point": number,
    "reorder_point_change": number,
    "safety_stock": number,
    "safety_stock_change": number,
    "lot_size": number,
    "lot_size_change_percent": number,
    "carrying_cost_change": number,
    "ordering_cost_change": number,
    "expected_fill_rate": 0.0-1.0,
    "expected_stockouts_per_year": number,
    "rationale": "string",
    "trade_offs": "string",
    "key_factors": ["string"],
    "implementation_notes": "string"
}
```

**Key Changes:**

- ✅ Detailed schema with all 14 fields
- ✅ Type ranges specified (0.0-1.0)
- ✅ Array fields clearly marked
- ✅ Added comprehensive guidelines section
- ✅ Clear trade-off explanation requirement

---

### 4. Operations Q&A (operations_qa.py)

**Location:** `_build_operational_prompt()` and `_parse_operational_response()`

**Schema:**

```json
{
    "answer": "string (clear, direct answer)",
    "reasoning_steps": ["string"],
    "constraints": ["string"],
    "bottlenecks": ["string"],
    "confidence": "high" | "medium" | "low"
}
```

**Key Changes:**

- ✅ Changed from plain text format to JSON
- ✅ Added explicit schema before task
- ✅ Updated parser to handle JSON instead of text sections
- ✅ Maintains backward compatibility with text fallback
- ⚠️ **Important:** `_parse_operational_response()` updated to:
  - Try JSON parsing first
  - Fall back to text parsing if JSON fails
  - Validate confidence values
  - Handle missing fields gracefully

---

### 5. Delivery Detection (delivery_detector.py)

**Location:** `EXTRACTION_PROMPT` and `RETRY_PROMPT` constants

**Schema:**

```json
{
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
    "confidence": 0.0-1.0
}
```

**Key Changes:**

- ✅ Both prompts now have explicit JSON schemas
- ✅ Date format standardized (YYYY-MM-DD)
- ✅ Enum values for change_type clearly listed
- ✅ Confidence scoring rules clarified
- ✅ Retry prompt includes same schema for consistency

---

### 6. Risk Engine (risk_engine.py)

**Location:** `RISK_PROMPT` constant

**Schema:**

```json
{
    "risk_level": "low" | "medium" | "high" | "critical",
    "risk_score": 0.0-1.0,
    "impact_summary": "string (1-2 sentences)",
    "affected_operations": ["string"],
    "recommended_actions": ["string"],
    "urgency_hours": number | null,
    "financial_impact_estimate": number | null,
    "reasoning": "string (2-3 sentences)"
}
```

**Key Changes:**

- ✅ Schema explicitly defined at top
- ✅ Risk level guidelines clearly separated
- ✅ Financial impact as optional number (null allowed)
- ✅ Clear urgency expectations

---

### 7. RAG Reasoner (rag_reasoner.py)

**Location:** `REASONING_PROMPT` constant

**Schema:**

```json
{
    "risk_level": "HIGH" | "MEDIUM" | "LOW",
    "explanation": "string (2-3 sentences grounded in provided context)",
    "suggested_action": "string (specific action based on provided information)"
}
```

**Key Changes:**

- ✅ Added explicit JSON schema at top
- ✅ Maintained grounding instructions (critical for RAG)
- ✅ Emphasized context-only reasoning in schema
- ✅ Clear output format (no markdown)
- ✅ Preserved all grounding constraints from earlier refactoring

---

## Implementation Details

### JSON Schema Format Standards

All schemas follow this format:

```python
prompt = f"""[Description]

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "field1": type | null,
    "field2": type,
    "field3": ["type"] | [],
    "field4": type (details/range)
}}

=== INPUT SECTION ===
[Context data]

=== TASK SECTION ===
[What to do]

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null or empty array [].
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else."""
```

### Type Notation Standards

| Type          | Example                                 |
| ------------- | --------------------------------------- |
| String        | `"field": "string"`                     |
| Number        | `"count": number`                       |
| Boolean       | `"active": true \| false`               |
| Enum          | `"status": "high" \| "medium" \| "low"` |
| Array         | `"items": ["string"]`                   |
| Optional      | `"field": string \| null`               |
| Numeric range | `"score": 0.0-1.0`                      |

### Error Handling

All parser functions maintain robust error handling:

```python
try:
    # Try JSON parsing first
    result = json.loads(text)
    return parse_json_fields(result)
except json.JSONDecodeError:
    # Fallback to text parsing if available
    logger.warning("JSON parsing failed, trying text fallback")
    return parse_text_format(response)
except Exception as e:
    # Final fallback with safe defaults
    return safe_default_values()
```

## Backward Compatibility

✅ **All changes are backward compatible:**

- Public function signatures unchanged
- Return types unchanged
- Error handling preserved
- Existing callers work without modification

### Updated Parsing Functions

The only functions with significant changes are the response parsers:

- ✅ `operations_qa.py:_parse_operational_response()` - Now tries JSON first, text fallback
- ✅ `alert_decision.py:_parse_alert_decision()` - Still works (uses existing JSON parser)
- ✅ `inventory_optimizer.py:_parse_optimization_response()` - Still works (uses existing JSON parser)

**Note:** No changes to JSON parsing logic in callsites - just the prompt templates.

## Testing & Validation

### To validate the refactored prompts:

```bash
# 1. Test risk assessment
python test_ollama_risk_assessor.py

# 2. Test alert decision
python test_alert_decision.py

# 3. Test inventory optimization
python test_inventory_optimizer.py

# 4. Test operations Q&A (will need to update test expectations for JSON)
python test_operations_qa.py

# 5. Test delivery detection
python test_delivery_detector.py
```

### Expected Behavior

All Ollama calls should now:

1. Receive strictly formatted JSON schema in prompt
2. Return valid JSON (no markdown, no explanations)
3. Parse cleanly without whitespace/formatting issues
4. Handle null values appropriately
5. Maintain consistent field naming across responses

## Configuration

No configuration changes needed:

- ✅ Model: `gemma:2b` (unchanged)
- ✅ Endpoint: `http://localhost:11434/api/generate` (unchanged)
- ✅ Temperature: `0.2-0.3` (unchanged, deterministic)
- ✅ Timeout: `60-120s` (unchanged)
- ✅ Stream: `False` (unchanged)

## Benefits

### For Local LLMs (gemma:2b)

1. **Higher Success Rate:** Explicit schema reduces ambiguity
2. **Consistent Parsing:** JSON structure predictable
3. **Better Quality:** Model concentrates on reasoning, not formatting
4. **Faster Processing:** Smaller, more focused prompts
5. **Easier Debugging:** Clear input/output structure

### For Hugo System

1. **Reliability:** No more parsing errors due to markdown/formatting
2. **Maintainability:** Uniform prompt structure across all services
3. **Scalability:** Easy to add new fields without changing parsers
4. **Monitoring:** Can track JSON parse success rates
5. **Documentation:** Schema serves as API contract

## Summary

| Service             | Prompt                              | Status        |
| ------------------- | ----------------------------------- | ------------- |
| Risk Assessor       | `_build_assessment_prompt()`        | ✅ Refactored |
| Alert Decision      | `_build_alert_evaluation_prompt()`  | ✅ Refactored |
| Inventory Optimizer | `OPTIMIZATION_PROMPT`               | ✅ Refactored |
| Operations Q&A      | `_build_operational_prompt()`       | ✅ Refactored |
| Delivery Detector   | `EXTRACTION_PROMPT`, `RETRY_PROMPT` | ✅ Refactored |
| Risk Engine         | `RISK_PROMPT`                       | ✅ Refactored |
| RAG Reasoner        | `REASONING_PROMPT`                  | ✅ Refactored |

**All 7 services with Ollama calls now use strict JSON prompts.**

## Notes

- No business logic changed (thresholds, weights, heuristics unchanged)
- No cloud dependencies introduced
- No new Python packages required
- All error handling preserved
- Fallback behavior unchanged (conservative defaults still available)
- Model remains gemma:2b
- Endpoint remains localhost:11434
