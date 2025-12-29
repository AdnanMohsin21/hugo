# Hugo System Integration Guide

Complete guide to integrating all Ollama-powered modules into the Hugo procurement agent.

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        INPUT: Emails                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │   DeliveryDetector (Ollama) │
        │   Extract: delays, changes  │
        └──────────┬──────────────────┘
                   │
                   ▼
        ┌─────────────────────────────┐
        │   ChangeEvent Created       │
        └──────────┬──────────────────┘
                   │
       ┌───────────┴───────────┐
       │                       │
       ▼                       ▼
    ANALYSIS              DECISION
    (Optional)            (Required)
       │                       │
       ├─ RiskEngine          ├─ AlertDecision
       │  (Risk Level)         │  (Trigger Alert?)
       │                       │
       ├─ RAGReasoner         ├─ OperationsQA
       │  (Impact Analysis)    │  (Answer Questions)
       │                       │
       └─ OperationsQA ──────┘
          (Questions)
                   │
                   ▼
        ┌─────────────────────────────┐
        │    Alert / Notification     │
        │    + Recommended Actions    │
        └─────────────────────────────┘
```

---

## Module Descriptions

### 1. DeliveryDetector (Core Pipeline)

**File:** `services/delivery_detector.py`
**Purpose:** Extract supplier changes from emails using Ollama
**Input:** Email text
**Output:** `DeliveryChange` objects (change_type, delay_days, affected_items, etc.)

```python
from services.delivery_detector import DeliveryDetector

detector = DeliveryDetector()
changes = detector.detect_changes(email_text)
# Returns: List[DeliveryChange]
```

### 2. AlertDecision (Reactive Intelligence) ⭐ NEW

**File:** `services/alert_decision.py`
**Purpose:** Decide if supplier change warrants an alert using Ollama
**Input:** `ChangeEvent` + `OperationalContext`
**Output:** `AlertDecision` (trigger_alert, urgency, reason, actions)

```python
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

change = ChangeEvent(change_type="delay", delay_days=5, ...)
context = OperationalContext(inventory_level=2.0, ...)
decision = should_trigger_alert(change, context)
# Returns: AlertDecision with trigger_alert, urgency, reason
```

### 3. RiskEngine (Analysis - Optional)

**File:** `services/risk_engine.py`
**Purpose:** Assess operational risk using Ollama
**Input:** `DeliveryChange` object
**Output:** `RiskAssessment` (risk_level, risk_score, drivers)

```python
from services.risk_engine import RiskEngine

engine = RiskEngine()
risk = engine.assess_risk(change)
# Returns: RiskAssessment with risk_level (LOW/MEDIUM/HIGH/CRITICAL)
```

### 4. OperationsQA (Analytical Questions)

**File:** `services/operations_qa.py`
**Purpose:** Answer operational questions using Ollama
**Input:** Question + context (ERP, orders, inventory)
**Output:** `OperationalAnswer` (answer, reasoning, constraints, bottlenecks)

```python
from services.operations_qa import answer_operational_question

answer = answer_operational_question(
    question="What's our production bottleneck?",
    erp_data=erp_data,
    orders=orders,
    inventory=inventory
)
# Returns: OperationalAnswer with plain text answer + reasoning
```

### 5. OllamaLLM (Shared Foundation)

**File:** `services/ollama_llm.py`
**Purpose:** Low-level Ollama HTTP interface
**Used by:** DeliveryDetector, RiskEngine, RAGReasoner, AlertDecision, OperationsQA

---

## Complete Integration Example

### Scenario: Email arrives from supplier about delivery delay

```python
from services.delivery_detector import DeliveryDetector
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext
from services.risk_engine import RiskEngine
from services.operations_qa import answer_operational_question

# Step 1: Detect the change
detector = DeliveryDetector()
changes = detector.detect_changes(email_text)
# Output: [DeliveryChange(change_type="delay", delay_days=5, ...)]

if not changes:
    print("No changes detected")
    return

for change in changes:
    # Step 2: Prepare change event for alert decision
    change_event = ChangeEvent(
        change_type=change.change_type.value,
        delay_days=change.delay_days,
        affected_items=change.affected_items,
        supplier_name=change.supplier_name,
        confidence=change.confidence
    )

    # Step 3: Gather operational context
    context = OperationalContext(
        inventory_level=get_inventory_level(),
        supplier_reliability_score=get_supplier_score(change.supplier_name),
        days_until_deadline=calculate_deadline(),
        # ... other context fields
    )

    # Step 4: Decide if alert is needed (Ollama evaluates impact)
    alert_decision = should_trigger_alert(change_event, context)

    if alert_decision.trigger_alert:
        # High-urgency path: escalate
        if alert_decision.urgency == "critical":
            escalate_to_management(alert_decision)

            # Optionally: get analytical insights
            question = "How does this supplier change affect our production schedule?"
            analysis = answer_operational_question(question, erp, orders, inventory)
            include_in_escalation(analysis)
        else:
            # Medium urgency: notify operations
            notify_operations(alert_decision)

    else:
        # No alert needed: monitor
        log_monitoring_event(change_event, alert_decision)

    # Optional: Get risk assessment
    engine = RiskEngine()
    risk = engine.assess_risk(change)
    log_risk_assessment(risk)
```

---

## Data Flow Diagrams

### Flow 1: Alert Decision Path (Primary)

```
Email
  │
  ├─→ DeliveryDetector (Ollama)
  │   └─→ DeliveryChange object
  │
  ├─→ Convert to ChangeEvent
  │
  ├─→ Gather OperationalContext
  │   ├─ Inventory systems
  │   ├─ ERP/production data
  │   ├─ Supplier history DB
  │   └─ Timeline calculations
  │
  ├─→ should_trigger_alert(change, context)
  │   └─→ Ollama evaluates impact
  │       ├─ Production impact?
  │       ├─ Inventory buffer?
  │       ├─ Order priority?
  │       ├─ Supplier reliability?
  │       └─ Timeline urgency?
  │
  └─→ AlertDecision
      ├─ trigger_alert: true/false
      ├─ urgency: low/medium/high/critical
      ├─ reason: explanation
      ├─ should_escalate: true/false
      └─ recommended_actions: [...]
```

### Flow 2: Analysis Path (Optional)

```
Detected Change
  │
  ├─→ RiskEngine (Ollama)
  │   └─→ RiskAssessment (risk_level, drivers)
  │
  ├─→ RAGReasoner (Ollama)
  │   └─→ Reasoning output
  │
  └─→ OperationsQA (Ollama)
      └─→ OperationalAnswer (answer + bottlenecks)
```

---

## Configuration Setup

### 1. Environment Variables

Create `.env` file:

```bash
OLLAMA_MODEL=gemma:2b
OLLAMA_BASE_URL=http://localhost:11434
```

### 2. Start Ollama

```bash
ollama run gemma:2b
```

### 3. Verify Connectivity

```bash
python -c "
from services.ollama_llm import OllamaLLM
llm = OllamaLLM()
status = llm.check_availability()
print(f'Ollama available: {status}')
"
```

---

## Integration Points with Hugo Pipeline

### In main.py

```python
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

async def process_email(email_text: str):
    """Process email and make alert decision."""

    # 1. Detect changes
    changes = detector.detect_changes(email_text)

    # 2. For each change: decide on alert
    for change in changes:
        change_event = ChangeEvent(
            change_type=change.change_type.value,
            delay_days=change.delay_days,
            # ... other fields
        )

        context = gather_operational_context()

        # 3. Alert decision (Ollama evaluates)
        decision = should_trigger_alert(change_event, context)

        # 4. Act on decision
        if decision.trigger_alert:
            await send_alert(decision)
```

### In notification system

```python
async def send_alert(decision: AlertDecision):
    """Send alert with Ollama's recommended actions."""

    notification = {
        "title": f"{decision.urgency.upper()}: {decision.reason}",
        "body": decision.reason,
        "actions": decision.recommended_actions,
        "escalate": decision.should_escalate,
        "timestamp": datetime.now()
    }

    if decision.should_escalate:
        # Route to management
        await notify_management(notification)
    else:
        # Route to operations
        await notify_operations(notification)

    # Log for audit
    await log_alert_decision(decision)
```

---

## Error Handling Strategy

### Per-Module Resilience

| Module           | Failure     | Fallback              | Result                     |
| ---------------- | ----------- | --------------------- | -------------------------- |
| DeliveryDetector | Ollama down | Return empty changes  | No detection, continue     |
| AlertDecision    | Ollama down | Conservative defaults | Alert on critical orders   |
| RiskEngine       | Ollama down | MEDIUM risk           | Alert sent, may escalate   |
| OperationsQA     | Ollama down | Error message         | Return "Unable to analyze" |

### Safe Defaults

**AlertDecision safe defaults:**

- Always alert if order_priority == "critical"
- Always alert if inventory < min_inventory
- Always alert if supplier_reliability < 0.5
- Log error with full context
- Set is_fallback=True

---

## Testing Strategy

### Unit Tests

```bash
# Test alert decision
python test_alert_decision.py

# Test operations QA
python test_operations_qa.py

# Test risk assessment
python test_ollama_risk_assessor.py
```

### Integration Tests

```python
# Full pipeline test
from integration_example import test_full_pipeline

test_full_pipeline(
    email="Dear Hugo, we have a 5-day delay...",
    expected_alert=True,
    expected_urgency="high"
)
```

### Load Testing

```bash
# Test alert decision with 100 changes
python -m pytest test_alert_decision.py -v --count=100
```

---

## Operational Monitoring

### Metrics to Track

1. **Alert Decision Quality**

   - True alert rate (% of alerts that had real impact)
   - False positive rate (% of alerts that didn't matter)
   - Escalation rate (% flagged for management)

2. **Ollama Performance**

   - Response latency (target: <5s)
   - Error rate (target: <1%)
   - Timeout rate (target: <0.1%)

3. **Decision Accuracy**
   - Alert recall (% of real issues caught)
   - Alert precision (% of alerts were necessary)
   - User feedback on alert quality

### Logging

```python
# Log all alert decisions for audit
log_entry = {
    "timestamp": datetime.now(),
    "change_type": change_event.change_type,
    "supplier": change_event.supplier_name,
    "decision": decision.trigger_alert,
    "urgency": decision.urgency,
    "reason": decision.reason,
    "is_fallback": decision.is_fallback,
    "latency_ms": elapsed_time
}

await audit_log.write(log_entry)
```

---

## Next Steps

1. **Verify Ollama Running**

   ```bash
   ollama run gemma:2b
   ```

2. **Run Tests**

   ```bash
   python test_alert_decision.py
   python test_operations_qa.py
   python test_ollama_risk_assessor.py
   ```

3. **Integrate into main.py**

   - Import alert_decision module
   - Add alert decision to email processing
   - Route decisions to notification system

4. **Monitor Quality**

   - Track alert accuracy
   - Measure Ollama latency
   - Gather user feedback
   - Refine prompts based on feedback

5. **Scale & Optimize**
   - Add caching for repeated evaluations
   - Batch alert decisions if volume high
   - Consider async/parallel Ollama calls
   - Monitor and tune temperature/timeouts

---

## FAQ

**Q: What if Ollama is not running?**
A: All modules degrade gracefully with safe defaults. AlertDecision will alert on critical orders. System continues to function.

**Q: How long does alert decision take?**
A: Typically 2-5 seconds with gemma:2b. Timeout is 60 seconds.

**Q: Can I use a different LLM?**
A: Yes. Edit OLLAMA_MODEL in .env. Tested with gemma:2b, may work with others (test first).

**Q: How do I customize alert criteria?**
A: Edit the ALERT_EVALUATION_PROMPT_TEMPLATE in alert_decision.py to change evaluation criteria.

**Q: Should I always escalate critical orders?**
A: The safe default is yes, but you can customize \_safe_default_decision() to match your business rules.

**Q: Can I integrate with Slack/Teams?**
A: Yes. In your notification system, call the Slack/Teams API with decision.recommended_actions.

**Q: How do I improve alert quality?**
A: Collect feedback, refine prompts, adjust safe defaults, monitor true/false positive rates.

---

## Architecture Decisions

### Why Ollama for Every Decision?

- **Transparency:** Every decision is traceable to an LLM response
- **Consistency:** Same model evaluates all changes
- **Learning:** Can improve prompts over time
- **Flexibility:** Easy to customize criteria

### Why Conservative Defaults?

- **Safety First:** Better to alert unnecessarily than miss a real issue
- **Human-in-Loop:** Operations team reviews alerts, filters false positives
- **Audit Trail:** Every decision logged with reasoning

### Why Three Separate Functions?

- **Single Responsibility:** Each function does one thing well
- **Reusability:** Can call AlertDecision without RiskEngine
- **Testing:** Easier to test individual functions
- **Flexibility:** Use only the modules you need

---

## Production Checklist

- ✅ Ollama running on dedicated machine (not user laptop)
- ✅ Environment variables configured correctly
- ✅ Error logging configured and monitored
- ✅ Alert decision metrics tracked
- ✅ User feedback mechanism in place
- ✅ Escalation routing configured (email/Slack/etc)
- ✅ Audit logging enabled
- ✅ Fallback procedures tested
- ✅ Load testing completed
- ✅ Documentation reviewed by ops team

---

**Status:** ✅ All modules ready for production integration

**Last Updated:** 2025-01-01
