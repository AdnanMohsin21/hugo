# JSON Prompt Refactoring - Quick Reference Card

## 📋 What Was Done

All **7 Ollama prompts** in Hugo refactored to enforce **strict valid JSON output**.

| Service               | Prompt                    | Status  |
| --------------------- | ------------------------- | ------- |
| 🔴 Risk Assessment    | `ollama_risk_assessor.py` | ✅ Done |
| 🟠 Alert Decision     | `alert_decision.py`       | ✅ Done |
| 🟡 Inventory Optim.   | `inventory_optimizer.py`  | ✅ Done |
| 🟢 Operations Q&A     | `operations_qa.py`        | ✅ Done |
| 🔵 Delivery Detection | `delivery_detector.py`    | ✅ Done |
| 🟣 Risk Engine        | `risk_engine.py`          | ✅ Done |
| ⚫ RAG Reasoner       | `rag_reasoner.py`         | ✅ Done |

---

## 🎯 5 Core Rules Applied

### 1️⃣ Schema First

```
=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{
    "field": type,
    ...
}
```

### 2️⃣ Clear Types

```
"status": "high" | "medium" | "low"       (enum)
"count": number                            (number)
"active": true | false                     (boolean)
"items": ["string"]                        (array)
"value": number | null                     (optional)
```

### 3️⃣ Strict Output

```
=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null or empty array [].
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else.
```

### 4️⃣ Schema BEFORE Task

```
✅ Schema → Input → Task → Rules
❌ Task → ... Schema ... → Rules
```

### 5️⃣ No Markdown

````
❌ ```json { ... } ```
✅ { ... }
````

---

## 📝 Prompt Structure Template

Every prompt now follows this pattern:

```python
prompt = f"""[Brief description]

=== JSON SCHEMA (RESPOND WITH THIS STRUCTURE ONLY) ===
{{
    "field1": type,
    "field2": ["type"],
    "field3": type | null
}}

=== INPUT SECTION(S) ===
[Context data here]

=== TASK ===
[What to do]

=== [SPECIFIC SECTION NAME] ===
[Context-specific rules/guidelines]

=== OUTPUT RULES ===
Respond with VALID JSON ONLY.
Do NOT include explanations, markdown, comments, or extra text.
If a value cannot be determined, use null or empty array [].
Do NOT include code blocks or backticks.
Output a single valid JSON object and nothing else."""
```

---

## 🔍 Side-by-Side: Before vs After

### Type Notation

| Before              | After               |
| ------------------- | ------------------- |
| `"low" or "medium"` | `"low" \| "medium"` |
| `true or false`     | `true \| false`     |
| `value or null`     | `value \| null`     |
| `<number>`          | `number`            |
| `0.0-1.0 decimal`   | `number (0.0-1.0)`  |

### Schema Location

| Before             | After                 |
| ------------------ | --------------------- |
| Mixed in task text | **Top section**       |
| At the end         | **Before input data** |
| Incomplete         | **All fields listed** |
| Vague types        | **Clear type info**   |

### Output Instructions

| Before        | After                 |
| ------------- | --------------------- |
| Scattered     | **Unified section**   |
| Implicit      | **Explicit rules**    |
| Vague         | **5-point checklist** |
| "No markdown" | **"No code blocks"**  |

---

## 📊 All 7 JSON Schemas

### 1. Risk Assessment

```json
{
    "risk_level": "low" | "medium" | "high" | "critical",
    "risk_score": 0.0-1.0,
    "drivers": ["string"],
    "recommended_actions": ["string"]
}
```

### 2. Alert Decision

```json
{
    "trigger_alert": true | false,
    "urgency": "low" | "medium" | "high" | "critical",
    "reason": "string (1-2 sentences)",
    "should_escalate": true | false,
    "recommended_actions": ["string"] | null
}
```

### 3. Inventory Optimization

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
    "expected_fill_rate": number (0.0-1.0),
    "expected_stockouts_per_year": number,
    "rationale": "string",
    "trade_offs": "string",
    "key_factors": ["string"],
    "implementation_notes": "string"
}
```

### 4. Operations Q&A

```json
{
    "answer": "string",
    "reasoning_steps": ["string"],
    "constraints": ["string"],
    "bottlenecks": ["string"],
    "confidence": "high" | "medium" | "low"
}
```

### 5. Delivery Detection

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

### 6. Risk Engine

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

### 7. RAG Reasoner

```json
{
    "risk_level": "HIGH" | "MEDIUM" | "LOW",
    "explanation": "string (2-3 sentences)",
    "suggested_action": "string"
}
```

---

## ✅ Validation Checklist

Before deploying, verify:

- [ ] All 7 services compile without syntax errors
- [ ] Existing tests still pass
- [ ] JSON responses parse cleanly
- [ ] No markdown in Ollama responses
- [ ] All null values handled correctly
- [ ] Enum values match schema
- [ ] Arrays have correct structure
- [ ] No business logic changed
- [ ] Fallback behavior unchanged

---

## 🚀 Quick Test

### Test Risk Assessment

```bash
python -c "
from services.ollama_risk_assessor import assess_risk_with_ollama
result = assess_risk_with_ollama('Email: Order delayed 5 days')
print(f'Risk: {result.risk_level} ({result.risk_score})')
"
```

### Test Alert Decision

```bash
python -c "
from services.alert_decision import should_trigger_alert, ChangeEvent
event = ChangeEvent(change_type='delay', delay_days=10)
decision = should_trigger_alert(event)
print(f'Alert: {decision.trigger_alert} (urgency: {decision.urgency})')
"
```

---

## 📚 Documentation Files

| File                                  | Purpose                        |
| ------------------------------------- | ------------------------------ |
| `JSON_PROMPT_REFACTORING.md`          | Complete implementation guide  |
| `JSON_PROMPT_BEFORE_AFTER.md`         | Concrete before/after examples |
| `OLLAMA_JSON_REFACTORING_COMPLETE.md` | Executive summary              |
| **This file**                         | Quick reference card           |

---

## 🔧 Configuration

**No changes needed:**

- ✅ Model: `gemma:2b`
- ✅ Endpoint: `http://localhost:11434/api/generate`
- ✅ Temperature: `0.2-0.3`
- ✅ Stream: `False`

---

## 🎁 Benefits

| Who                | Benefit                           |
| ------------------ | --------------------------------- |
| **LLM (gemma:2b)** | Explicit schema reduces ambiguity |
| **Hugo System**    | Reliable JSON parsing             |
| **Developers**     | Uniform prompt format             |
| **Maintainers**    | Self-documenting code             |
| **Scaling**        | Easy to add new services          |

---

## ⚡ Key Takeaway

**All Ollama prompts now have:**

1. Explicit JSON schema at the top
2. Clear type information for every field
3. Standardized output rules at the bottom
4. No markdown in responses
5. Consistent format across all services

**Result:** More reliable, consistent, and maintainable local LLM integration.

---

## 📞 Need Help?

- **Questions about what changed?** → See `JSON_PROMPT_BEFORE_AFTER.md`
- **Implementation details?** → See `JSON_PROMPT_REFACTORING.md`
- **Executive summary?** → See `OLLAMA_JSON_REFACTORING_COMPLETE.md`
- **This quick reference?** → You're reading it! 📍

---

**Status:** ✅ Complete and Ready for Deployment

🚀 All 7 services ready to go!
