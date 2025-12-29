# Hugo Ollama Modules - Quick Reference

**Status:** ✅ PRODUCTION READY

---

## One-Line Summaries

| Module               | Purpose                              | Input                     | Output              |
| -------------------- | ------------------------------------ | ------------------------- | ------------------- |
| **DeliveryDetector** | Extract supplier changes from emails | Email text                | `DeliveryChange[]`  |
| **AlertDecision** ⭐ | Decide if change warrants alert      | `ChangeEvent` + `Context` | `AlertDecision`     |
| **RiskEngine**       | Assess operational risk              | `DeliveryChange`          | `RiskAssessment`    |
| **OperationsQA**     | Answer operational questions         | Question + context        | `OperationalAnswer` |
| **OllamaLLM**        | Low-level Ollama interface           | Prompt                    | Response text       |

---

## Quickstart: Alert Decision

```python
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

# Create change event
change = ChangeEvent(
    change_type="delay",
    delay_days=5,
    affected_items=["CRITICAL-PART"],
    supplier_name="Supplier ABC",
    po_priority="critical",
    order_value=50000
)

# Gather context
context = OperationalContext(
    inventory_level=2.0,
    supplier_reliability_score=0.70,
    days_until_deadline=7
)

# Get decision
decision = should_trigger_alert(change, context)

# Use decision
if decision.trigger_alert:
    print(f"🚨 {decision.urgency}: {decision.reason}")
    if decision.should_escalate:
        escalate_to_management(decision.recommended_actions)
```

---

## Quickstart: Risk Assessment

```python
from services.risk_engine import RiskEngine

engine = RiskEngine()
risk = engine.assess_risk(delivery_change)

print(f"Risk Level: {risk.risk_level}")  # LOW, MEDIUM, HIGH, CRITICAL
print(f"Score: {risk.risk_score}")  # 0-1
print(f"Drivers: {risk.drivers}")  # List of reasons
```

---

## Quickstart: Operations Q&A

```python
from services.operations_qa import answer_operational_question

answer = answer_operational_question(
    question="What's blocking our production?",
    erp_data=erp_data,
    orders=active_orders,
    inventory=inventory
)

print(answer.answer)  # Plain text answer
print(answer.bottlenecks)  # List of constraints
print(answer.confidence)  # 0-1 confidence score
```

---

## Integration: Full Pipeline

```python
from services.delivery_detector import DeliveryDetector
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

# Detect changes
detector = DeliveryDetector()
changes = detector.detect_changes(email_text)

# For each change
for change in changes:
    # Convert to alert format
    event = ChangeEvent(
        change_type=change.change_type.value,
        delay_days=change.delay_days,
        affected_items=change.affected_items,
        supplier_name=change.supplier_name
    )

    # Get context
    context = OperationalContext(
        inventory_level=get_inventory(),
        supplier_reliability_score=get_supplier_score(change.supplier_name)
    )

    # Decide
    decision = should_trigger_alert(event, context)

    # Act
    if decision.trigger_alert:
        notify(decision)
```

---

## Environment Setup

```bash
# 1. Create .env file
OLLAMA_MODEL=gemma:2b
OLLAMA_BASE_URL=http://localhost:11434

# 2. Start Ollama
ollama run gemma:2b

# 3. Verify
python -c "from services.ollama_llm import OllamaLLM; print(OllamaLLM().check_availability())"
```

---

## Data Classes

### ChangeEvent

```python
ChangeEvent(
    change_type: str,              # delay, early, cancellation, partial_shipment, quality_issue
    delay_days: Optional[int],     # negative for early
    affected_items: List[str],     # which parts
    supplier_name: str,
    po_number: Optional[str],
    po_priority: Optional[str],    # normal, high, critical
    order_value: Optional[float],
    detected_at: Optional[str],    # ISO timestamp
    confidence: Optional[float],   # 0-1
    supplier_reason: Optional[str] # why supplier gave reason
)
```

### OperationalContext

```python
OperationalContext(
    production_capacity: Optional[float],
    current_production_rate: Optional[float],
    active_orders_count: Optional[int],
    orders_at_risk: Optional[int],
    inventory_level: Optional[float],      # days of supply
    min_inventory_level: Optional[float],
    supplier_reliability_score: Optional[float],  # 0-1
    supplier_past_issues: Optional[int],
    alternate_suppliers_available: Optional[bool],
    days_until_delivery: Optional[int],
    days_until_deadline: Optional[int]
)
```

### AlertDecision

```python
AlertDecision(
    trigger_alert: bool,
    urgency: str,                  # low, medium, high, critical
    reason: str,                   # explanation
    should_escalate: bool,
    recommended_actions: List[str],
    raw_response: Optional[str],   # full Ollama response
    error: Optional[str],          # if error occurred
    is_fallback: bool              # if used safe defaults
)
```

---

## Error Handling

**All modules handle:**

- ✅ Connection errors → Safe defaults + log error
- ✅ Timeout errors → Fallback decision + log
- ✅ JSON parse errors → Safe defaults + log
- ✅ Invalid responses → Fallback decision + log

**Safe Defaults:**

- AlertDecision: Alert on critical/low-inventory orders
- RiskEngine: MEDIUM risk
- OperationsQA: "Unable to analyze" + error message

---

## Testing

```bash
# Test alert decision
python test_alert_decision.py

# Test operations QA
python test_operations_qa.py

# Test risk assessment
python test_ollama_risk_assessor.py

# Test with specific Ollama
OLLAMA_MODEL=mistral python test_alert_decision.py
```

---

## Common Tasks

### Check Ollama Status

```python
from services.ollama_llm import OllamaLLM
llm = OllamaLLM()
available = llm.check_availability()
print(f"Ollama available: {available}")
```

### Set Confidence Threshold

```python
# In your code
if change.confidence < 0.8:
    log.warning(f"Low confidence detection: {change.confidence}")
    return  # Skip low-confidence changes
```

### Custom Alert Criteria

Edit `ALERT_EVALUATION_PROMPT_TEMPLATE` in `services/alert_decision.py`

### Change Temperature

- Edit ALERT_DECISION_TEMPERATURE in `services/alert_decision.py`
- Default: 0.2 (deterministic)
- Range: 0-1 (higher = more creative)

### Increase Timeout

- Edit `OLLAMA_TIMEOUT_SECONDS` in module
- Default: 120 seconds
- Good for slow systems or complex prompts

---

## Files

| File                               | Purpose              | Lines |
| ---------------------------------- | -------------------- | ----- |
| `services/alert_decision.py`       | Alert intelligence   | 500+  |
| `services/operations_qa.py`        | Question answering   | 450+  |
| `services/ollama_risk_assessor.py` | Risk assessment      | 400+  |
| `services/delivery_detector.py`    | Change detection     | 250+  |
| `services/risk_engine.py`          | Risk evaluation      | 200+  |
| `test_alert_decision.py`           | Alert tests          | 200+  |
| `test_operations_qa.py`            | QA tests             | 200+  |
| `INTEGRATION_GUIDE.md`             | Full guide           | -     |
| `ALERT_DECISION_VALIDATION.md`     | Validation checklist | -     |

---

## Decision Logic

### Alert Decision Flow

```
Change detected
    ├─ Convert to ChangeEvent
    ├─ Gather OperationalContext
    ├─ Call should_trigger_alert()
    │   └─ Ollama evaluates:
    │      ├─ Production impact?
    │      ├─ Inventory buffer?
    │      ├─ Order priority?
    │      ├─ Supplier reliability?
    │      ├─ Timeline urgency?
    │      └─ Alternatives available?
    └─ Return AlertDecision
        ├─ trigger_alert: bool
        ├─ urgency: enum
        ├─ reason: text
        └─ recommended_actions: list
```

---

## Prompt Engineering

All prompts optimized for **gemma:2b**:

- ✅ Concise (300-600 tokens)
- ✅ Structured (numbered lists, clear sections)
- ✅ JSON output (explicit schema)
- ✅ Temperature 0.2 (deterministic)
- ✅ ~60-120s timeout

**To customize:** Edit `*_PROMPT_TEMPLATE` constants in each module

---

## Performance

| Operation        | Latency | Timeout |
| ---------------- | ------- | ------- |
| Alert Decision   | 2-5s    | 60s     |
| Risk Assessment  | 2-5s    | 120s    |
| Operations QA    | 3-8s    | 120s    |
| Change Detection | 2-4s    | 120s    |

---

## Troubleshooting

| Problem              | Cause                   | Fix                      |
| -------------------- | ----------------------- | ------------------------ |
| "Connection refused" | Ollama not running      | `ollama run gemma:2b`    |
| Timeout errors       | Ollama slow             | Increase timeout in code |
| Invalid JSON         | Ollama format change    | Check \_parse functions  |
| Always alerting      | Safe defaults triggered | Check Ollama connection  |
| Blank responses      | Model issue             | Try different model      |

---

## Next Steps

1. **Verify Ollama:** `ollama run gemma:2b`
2. **Run Tests:** `python test_alert_decision.py`
3. **Integrate:** Import into main.py
4. **Monitor:** Track alert quality
5. **Iterate:** Refine prompts based on feedback

---

**Documentation:** See `INTEGRATION_GUIDE.md` for complete guide

**Status:** ✅ Production Ready | Last Updated: 2025-01-01
