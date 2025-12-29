# JSON Prompt Refactoring - Before & After Examples

## Overview

This document shows concrete examples of how each Ollama prompt was refactored to enforce strict JSON output.

---

## 1. Risk Assessment (ollama_risk_assessor.py)

### BEFORE

```python
prompt = f"""You are an operations risk analyst for a manufacturing company.

Analyze this supplier email notification for delivery changes and assess operational risk.

=== SUPPLIER EMAIL ===
{email_text}

=== PURCHASE ORDER CONTEXT ===
{po_info}

=== HISTORICAL SUPPLIER DATA ===
{history_info}

=== YOUR TASK ===
Determine the operational risk level and provide structured reasoning.

Consider:
1. Severity of the delivery change (delay, cancellation, etc.)
2. Impact on production (priority of items, criticality)
3. Supplier reliability and historical performance
4. Business impact (timeline, cost, alternatives)

Output STRICT JSON only (no markdown, no explanation):
{{
    "risk_level": "low" or "medium" or "high" or "critical",
    "risk_score": <number from 0.0 to 1.0>,
    "drivers": [
        "Risk factor 1",
        "Risk factor 2",
        "Risk factor 3"
    ],
    "recommended_actions": [
        "Specific action 1",
        "Specific action 2",
        "Specific action 3"
    ]
}}

Risk Level Definitions:
- LOW (0.0-0.3): Minor impact, non-critical items, adequate buffers, early delivery
- MEDIUM (0.3-0.6): Moderate impact, <7 day delay, some operational adjustment needed
- HIGH (0.6-0.85): Significant disruption, 7-14 day delay, critical timeline impact
- CRITICAL (0.85-1.0): Production stoppage risk, >14 day delay, critical components, unreliable supplier

RESPOND WITH ONLY THE JSON OBJECT. NO MARKDOWN BLOCKS."""
```

### AFTER

```python
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
```

### Key Changes

| Aspect          | Before              | After                    |
| --------------- | ------------------- | ------------------------ |
| Schema location | Bottom              | **Top**                  |
| Schema clarity  | Vague               | **Explicit with types**  |
| Syntax          | `"low" or "medium"` | **`"low" \| "medium"`**  |
| Output rules    | Scattered           | **Unified section**      |
| Markdown blocks | Mentioned           | **Explicitly forbidden** |
| Format clarity  | Implicit            | **Explicit enumeration** |

---

## 2. Alert Decision (alert_decision.py)

### BEFORE

```python
prompt = f"""You are an operations alert intelligence system. Evaluate whether this supplier change event warrants an operational alert.

SUPPLIER CHANGE EVENT
{change_info}

OPERATIONAL CONTEXT
{context_info}

EVALUATION CRITERIA
Consider:
1. Impact on production (can we still build products?)
2. Inventory buffer (do we have enough stock?)
3. Order priority (is this for a critical order?)
4. Supplier reliability (is this expected behavior?)
5. Timeline (how urgent is this?)
6. Alternatives (can we switch suppliers?)

DECISION CATEGORIES
- IGNORE: Minor event, no action needed
- MONITOR: Watch situation, no immediate action
- ALERT: Notify operations, action may be needed
- CRITICAL: Escalate to management, immediate action required

Respond with ONLY this JSON (no markdown, no extra text):
{{
    "trigger_alert": true or false,
    "urgency": "low" or "medium" or "high" or "critical",
    "reason": "Clear explanation (1-2 sentences) of why this decision",
    "should_escalate": true or false,
    "recommended_actions": ["action 1", "action 2"] or null
}}

Answer based on operational impact, not just delay duration. A 2-day early delivery with adequate inventory may not warrant alert. A critical order with unknown delay may warrant high urgency alert."""
```

### AFTER

```python
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
```

### Key Changes

| Aspect          | Before          | After                         |
| --------------- | --------------- | ----------------------------- |
| Schema position | Mixed in        | **Explicit top section**      |
| Boolean syntax  | `true or false` | **`true \| false`**           |
| String hints    | Embedded        | **In schema (1-2 sentences)** |
| Null handling   | `or null`       | **`\| null`**                 |
| Guidelines      | At bottom       | **Clear, separate section**   |

---

## 3. Inventory Optimization (inventory_optimizer.py)

### BEFORE

```python
OPTIMIZATION_PROMPT = """Optimize inventory settings for a part using tradeoff analysis.

PART DATA:
SKU: {sku}
...
Service Level Target: {service_level_target}%

COSTS:
Carrying Cost: ${carrying_cost_per_unit_year}/unit/year (warehouse, capital, obsolescence)
Ordering Cost: ${ordering_cost_per_order}/order (procurement overhead)
Stockout Cost: ${stockout_cost_per_unit} per unit (lost sales, production delay)

CONSTRAINTS:
Max Warehouse Space: {max_warehouse_space_allocated}
Supplier Reliability: {supplier_reliability_score} (0=unreliable, 1=perfect)
Recent Stockouts: {recent_stockouts} (last 12 months)
Forecast Accuracy: {forecast_accuracy} (0=inaccurate, 1=very accurate)

TASK: Recommend optimized inventory settings that balance:
1. Holding costs (minimize excess inventory)
2. Ordering costs (minimize small frequent orders)
3. Stockout risk (maintain service level)
4. Warehouse constraints (stay within space allocation)

IMPORTANT: Explicitly explain ALL trade-offs between these competing objectives.

Return ONLY valid JSON (no markdown):
{{
    "reorder_point": <number>,
    "reorder_point_change": <number from current>,
    "safety_stock": <number>,
    ...
    "trade_offs": "Explicit explanation of trade-offs. Example: 'Increasing safety stock from X to Y costs $Z more annually in carrying costs but reduces stockouts from A to B per year, improving service level from X% to Y%'",
    ...
}}

Guidelines:
- ROP = (Daily Demand × Lead Time) + Safety Stock
- Safety Stock = Z-score × Std Dev of Demand × Sqrt(Lead Time)
..."""
```

### AFTER

```python
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
...
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
```

### Key Changes

| Aspect        | Before            | After                                     |
| ------------- | ----------------- | ----------------------------------------- |
| Schema        | Scattered in text | **Explicit top section**                  |
| Schema detail | Partial           | **All 14 fields listed**                  |
| Number syntax | `<number>`        | **`number` with ranges where applicable** |
| Type ranges   | Not shown         | **`0.0-1.0` for scores**                  |
| Guidelines    | At end            | **Dedicated section**                     |
| Output rules  | Vague             | **Explicit 5-point section**              |

---

## 4. Operations Q&A (operations_qa.py)

### BEFORE

```python
prompt = f"""You are a procurement operations copilot for a manufacturing company.

QUESTION: {question}

=== OPERATIONAL DATA ===

ERP System Data:
{erp_str}

Active Orders:
{orders_str}

Current Inventory Levels:
{inventory_str}

Bill of Materials:
{bom_str}

=== YOUR TASK ===

Answer the question step by step. Think through:
1. What data is relevant to this question?
2. What are the current constraints?
3. What bottlenecks exist?
4. What is the final answer?

Provide:
- A clear, direct answer to the question (no markdown, no JSON)
- Identify operational constraints
- Identify supply chain bottlenecks
- Your confidence level (high/medium/low)

Format your response as plain text with these sections:

ANSWER:
[Your clear, direct answer]

REASONING:
[Step-by-step reasoning, one step per line starting with "-"]

CONSTRAINTS:
[Operational constraints, one per line starting with "-"]

BOTTLENECKS:
[Supply chain bottlenecks, one per line starting with "-"]

CONFIDENCE:
[high/medium/low]

Be concise. Focus on facts and numbers. No markdown, no emojis, no JSON."""
```

### AFTER

```python
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
```

### Key Changes

| Aspect     | Before                  | After                            |
| ---------- | ----------------------- | -------------------------------- |
| Format     | Plain text sections     | **Structured JSON**              |
| Schema     | No schema               | **Explicit schema with types**   |
| Parser     | Text section extraction | **JSON parsing + text fallback** |
| Arrays     | Bullet-point lists      | **Proper JSON arrays**           |
| Confidence | Plain text              | **Enum: high \| medium \| low**  |

**Parser Update:**

```python
# OLD: Extract from text sections (ANSWER:, REASONING:, etc.)
# NEW: Parse JSON first, fall back to text if needed
try:
    result = json.loads(text)
except json.JSONDecodeError:
    # Fall back to text parsing for backward compatibility
    result = parse_text_sections(text)
```

---

## 5. Delivery Detection (delivery_detector.py)

### BEFORE

```python
EXTRACTION_PROMPT = """Extract delivery change information from this email. TODAY: {today} ({day_of_week})

From: {sender}
Subject: {subject}
Body: {body}

OUTPUT STRICT JSON ONLY (no markdown):
{{
    "detected": true/false,
    "order_id": "PO-123 or null",
    "sku": ["SKU-001"] or [],
    "original_delivery_date": "YYYY-MM-DD or null",
    "new_delivery_date": "YYYY-MM-DD or null",
    "change_type": "delay|early|quantity_change|cancellation|partial_shipment|rescheduled|other|null",
    "delay_days": integer or null,
    "reason": "Brief reason or null",
    "affected_items": ["Item description"],
    "quantity_change": integer or null,
    "confidence": 0.0 to 1.0
}}

Rules:
- If no delivery change: set detected=false
- Confidence: 0.9+ (explicit), 0.7-0.9 (clear), 0.5-0.7 (vague), 0.3-0.5 (uncertain)
- For vague dates: "next Friday"=next Friday, "end of month"=month end, "in 2 weeks"=today+14 days"""
```

### AFTER

```python
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
```

### Key Changes

| Aspect          | Before         | After                   |
| --------------- | -------------- | ----------------------- |
| Schema location | Bottom         | **Top**                 |
| Boolean syntax  | `true/false`   | **`true \| false`**     |
| Enum syntax     | Pipe-separated | **Clear `\|` notation** |
| Number type     | `integer`      | **`number`**            |
| Null handling   | `or null`      | **`\| null`**           |
| Field hints     | Sparse         | **Type + range info**   |
| Rules section   | Short          | **Detailed, numbered**  |

---

## 6. Risk Engine (risk_engine.py)

### BEFORE

```python
RISK_PROMPT = """Assess operational risk for this delivery change.

DELIVERY CHANGE
Type: {change_type}
Delay: {delay_days} days
Items: {affected_items}
Reason: {supplier_reason}

PURCHASE ORDER
PO: {po_number}
Supplier: {supplier_name}
Value: {order_value}
Priority: {priority}
Expected: {expected_delivery}
Items: {po_items}

HISTORY
Supplier Reliability: {reliability_score}/1.0
Past Issues: {past_issues}
Avg Delay: {avg_delay} days
Similar Incidents:
{similar_incidents}

---

OUTPUT STRICT JSON:
{{
    "risk_level": "low|medium|high|critical",
    "risk_score": 0.0-1.0,
    "impact_summary": "1-2 sentence impact",
    "affected_operations": ["operations"],
    "recommended_actions": ["action 1", "action 2"],
    "urgency_hours": number or null,
    "financial_impact_estimate": number or null,
    "reasoning": "2-3 sentence explanation"
}}

Guidelines:
- LOW: <3 day delay, minor impact
- MEDIUM: 3-7 day delay, some disruption, <$10k
- HIGH: 7-14 day delay, significant disruption, $10k-$50k
- CRITICAL: >14 day delay or production stoppage or critical priority

ONLY JSON, NO MARKDOWN."""
```

### AFTER

```python
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
```

### Key Changes

| Aspect          | Before              | After                              |
| --------------- | ------------------- | ---------------------------------- |
| Schema position | Bottom              | **Top**                            |
| Enum syntax     | Pipe without spaces | **`\| clear pipes` with types**    |
| String hints    | Embedded            | **In schema**                      |
| Guidelines      | Unstructured        | **Dedicated section with details** |

---

## 7. RAG Reasoner (rag_reasoner.py)

### BEFORE

```python
REASONING_PROMPT = """Assess supply chain risk. Respond with JSON only.

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

=== OUTPUT JSON ===
{{
  "risk_level": "HIGH"|"MEDIUM"|"LOW",
  "explanation": "2-3 sentences. Ground explanation ONLY on provided email, ERP, and historical context. State any assumptions.",
  "suggested_action": "Specific action based on provided information"
}}

JSON ONLY. NO MARKDOWN."""
```

### AFTER

```python
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
```

### Key Changes

| Aspect          | Before              | After                                 |
| --------------- | ------------------- | ------------------------------------- |
| Schema position | Bottom              | **Top**                               |
| Schema section  | "OUTPUT JSON"       | **"JSON SCHEMA"**                     |
| Enum syntax     | Pipe without spaces | **`\| clear pipes`**                  |
| String hints    | Embedded            | **In schema with emphasis**           |
| Output emphasis | At bottom           | **Grounding + output rules combined** |
| Consistency     | Inconsistent quotes | **Uniform type annotations**          |

---

## Summary of Changes

### Universal Improvements

All 7 prompts now follow this consistent pattern:

```
1. Brief description
2. === JSON SCHEMA === (explicit types)
3. === INPUT SECTIONS === (data sections)
4. === TASK === (what to do)
5. === GUIDELINES/RULES === (context-specific)
6. === OUTPUT RULES === (strict JSON requirements)
```

### Consistency Improvements

| Aspect       | Old               | New                         |
| ------------ | ----------------- | --------------------------- |
| Enum syntax  | `"a" or "b"`      | **`"a" \| "b"`**            |
| Optional     | `value or null`   | **`value \| null`**         |
| Type hints   | Sparse            | **Complete and consistent** |
| Array format | Context-dependent | **`["type"]` or `[]`**      |
| Ranges       | Missing           | **Explicit (0.0-1.0)**      |
| Guidelines   | Mixed             | **Dedicated sections**      |
| Output rules | Vague             | **5-point checklist**       |

### Quality Improvements

✅ **Better for LLMs:** Explicit schema reduces ambiguity
✅ **Easier to parse:** Consistent JSON structure
✅ **Fewer errors:** Clear type information  
✅ **More maintainable:** Uniform format across all services
✅ **Better documentation:** Schema serves as API contract
