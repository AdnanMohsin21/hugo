# Hugo System - Deployment Verification Checklist

Use this checklist to verify that the Hugo procurement agent is properly set up and working.

---

## ✅ Pre-Flight Checks

### Environment Setup

- [ ] `.env` file exists in project root
- [ ] `.env` contains `OLLAMA_MODEL=gemma:2b`
- [ ] `.env` contains `OLLAMA_BASE_URL=http://localhost:11434`
- [ ] Python 3.8+ installed (`python --version`)
- [ ] Virtual environment activated (`.venv/`)
- [ ] `requirements.txt` installed (`pip install -r requirements.txt`)

### Directory Structure

- [ ] `services/` directory exists with all modules:
  - [ ] `alert_decision.py` (500+ lines)
  - [ ] `operations_qa.py` (450+ lines)
  - [ ] `ollama_risk_assessor.py` (400+ lines)
  - [ ] `delivery_detector.py` (refactored)
  - [ ] `risk_engine.py` (refactored)
  - [ ] `rag_reasoner.py` (refactored)
  - [ ] `ollama_llm.py` (shared foundation)
- [ ] `tests/` directory exists
- [ ] `data/` directory exists with mock data

---

## 🔌 Ollama Verification

### Ollama Installation

- [ ] Ollama installed on system
- [ ] `ollama` command available in terminal
- [ ] Ollama service can be started

### Ollama Model

- [ ] gemma:2b model downloaded (`ollama pull gemma:2b`)
- [ ] Model size ~5GB on disk
- [ ] Model loads in <2 minutes

### Ollama Connectivity

- [ ] Start Ollama: `ollama run gemma:2b`
- [ ] Ollama listens on http://localhost:11434
- [ ] API endpoint responds: `curl http://localhost:11434/api/tags`
- [ ] Response includes gemma:2b in models list

### Connection Test

```bash
# Run this Python command
python -c "
from services.ollama_llm import OllamaLLM
llm = OllamaLLM()
status = llm.check_availability()
print(f'Ollama available: {status}')
"
# Expected: "Ollama available: True"
```

---

## 📦 Python Imports Verification

### Core Imports

```bash
python -c "
# Test core imports
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext, AlertDecision
from services.operations_qa import answer_operational_question, OperationalAnswer
from services.ollama_risk_assessor import assess_risk_with_ollama, RiskAssessmentResult
from services.delivery_detector import DeliveryDetector
from services.risk_engine import RiskEngine
from services.ollama_llm import OllamaLLM
print('✅ All imports successful')
"
# Expected: "✅ All imports successful"
```

---

## 🧪 Unit Tests

### Run Alert Decision Tests

```bash
python test_alert_decision.py
```

- [ ] Test starts
- [ ] Scenario 1: Minor delay with good inventory → Pass
- [ ] Scenario 2: Critical delay with low inventory → Pass
- [ ] Scenario 3: Early delivery → Pass
- [ ] Scenario 4: Partial shipment → Pass
- [ ] Scenario 5: Cancellation → Pass
- [ ] Integration example shows
- [ ] All tests complete

### Run Operations QA Tests

```bash
python test_operations_qa.py
```

- [ ] Test starts
- [ ] Scenario 1: Capacity question → Pass
- [ ] Scenario 2: Bottleneck question → Pass
- [ ] Scenario 3: Demand scenario → Pass
- [ ] Scenario 4: Supplier scenario → Pass
- [ ] All tests complete

### Run Risk Assessment Tests

```bash
python test_ollama_risk_assessor.py
```

- [ ] Test starts
- [ ] Test 1: High risk scenario → Pass
- [ ] Test 2: Medium risk scenario → Pass
- [ ] Test 3: Low risk scenario → Pass
- [ ] All tests complete

---

## 🎯 Functional Tests

### Test Alert Decision Function

```python
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

change = ChangeEvent(
    change_type="delay",
    delay_days=5,
    affected_items=["TEST-PART"],
    supplier_name="Test Supplier",
    po_priority="critical",
    order_value=50000
)

context = OperationalContext(
    inventory_level=2.0,
    supplier_reliability_score=0.70,
    days_until_deadline=7
)

decision = should_trigger_alert(change, context)

assert decision.trigger_alert == True, "Should trigger alert for critical order"
assert decision.urgency in ["low", "medium", "high", "critical"], "Invalid urgency"
assert isinstance(decision.reason, str), "Reason should be string"
assert isinstance(decision.recommended_actions, list), "Actions should be list"

print("✅ Alert Decision Test Passed")
```

- [ ] Test script runs
- [ ] No assertion errors
- [ ] Output shows "✅ Alert Decision Test Passed"

### Test Operations QA Function

```python
from services.operations_qa import answer_operational_question

answer = answer_operational_question(
    question="What is our current inventory level?",
    erp_data={"total_inventory": 1000},
    orders=[],
    inventory={}
)

assert answer.answer is not None, "Answer should not be None"
assert isinstance(answer.answer, str), "Answer should be string"
assert answer.answer != "", "Answer should not be empty"
assert answer.confidence >= 0 and answer.confidence <= 1, "Confidence should be 0-1"

print("✅ Operations QA Test Passed")
```

- [ ] Test script runs
- [ ] No assertion errors
- [ ] Output shows "✅ Operations QA Test Passed"

### Test Risk Assessment Function

```python
from services.ollama_risk_assessor import assess_risk_with_ollama

result = assess_risk_with_ollama(
    email_text="Supplier ABC has delayed shipment by 10 days",
    purchase_order={"po_number": "PO-001", "deadline": "2025-01-15"},
    historical_context="First delay from this supplier"
)

assert result.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"], "Invalid risk level"
assert 0 <= result.risk_score <= 1, "Risk score should be 0-1"
assert isinstance(result.drivers, list), "Drivers should be list"

print("✅ Risk Assessment Test Passed")
```

- [ ] Test script runs
- [ ] No assertion errors
- [ ] Output shows "✅ Risk Assessment Test Passed"

---

## 📊 Performance Checks

### Latency Test

```bash
python -c "
import time
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

start = time.time()
change = ChangeEvent(change_type='delay', delay_days=5, affected_items=['TEST'])
context = OperationalContext(inventory_level=5.0)
decision = should_trigger_alert(change, context)
elapsed = time.time() - start

print(f'Alert decision latency: {elapsed:.2f}s')
assert elapsed < 30, 'Alert decision too slow (should be <30s)'
print('✅ Latency acceptable')
"
```

- [ ] Latency: 2-10 seconds
- [ ] Confirms "✅ Latency acceptable"

### Error Handling Test

```python
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

# Test with minimal context (should still work with safe defaults)
change = ChangeEvent(change_type="delay", delay_days=5, affected_items=["TEST"])
context = OperationalContext()  # Empty context

decision = should_trigger_alert(change, context)

assert decision is not None, "Should return decision even with empty context"
assert isinstance(decision.trigger_alert, bool), "trigger_alert should be bool"
assert isinstance(decision.reason, str), "reason should be string"

print("✅ Error Handling Test Passed")
```

- [ ] Test runs without crashing
- [ ] Output shows "✅ Error Handling Test Passed"

---

## 📝 Documentation Verification

### Documentation Files Exist

- [ ] `INTEGRATION_GUIDE.md` exists (complete guide)
- [ ] `ALERT_DECISION_VALIDATION.md` exists (validation checklist)
- [ ] `QUICK_REFERENCE_OLLAMA.md` exists (developer reference)
- [ ] `OLLAMA_REFACTORING.md` exists (refactoring summary)
- [ ] `ARCHITECTURE.md` exists (system architecture)
- [ ] `PROJECT_COMPLETION.md` exists (completion summary)

### Documentation Quality

- [ ] Each file has clear sections
- [ ] Code examples are present
- [ ] Error handling described
- [ ] Integration points documented
- [ ] Troubleshooting guide included

---

## 🚀 Integration Readiness

### Code Integration Points

- [ ] Can import `should_trigger_alert` in main.py
- [ ] Can import `answer_operational_question` in main.py
- [ ] Can import `assess_risk_with_ollama` in main.py
- [ ] Can import data classes (ChangeEvent, etc.)
- [ ] No import errors

### Pipeline Integration

```python
# In main.py or your pipeline
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

def process_supplier_email(email_text):
    # 1. Detect changes
    # 2. Create ChangeEvent
    # 3. Gather OperationalContext
    # 4. Call should_trigger_alert()
    # 5. Act on AlertDecision
    pass
```

- [ ] Can add above code to main.py
- [ ] Code syntax is valid
- [ ] Imports work

---

## 🔒 Safety & Reliability

### Error Scenarios

- [ ] Ollama down → System continues with safe defaults
- [ ] Network timeout → System uses fallback decision
- [ ] Invalid response → System validates and falls back
- [ ] Missing context → System handles optional fields
- [ ] All errors logged with context

### Fallback Verification

```python
from services.alert_decision import should_trigger_alert, ChangeEvent, OperationalContext

# Simulate Ollama being unavailable by using invalid URL
import os
original_url = os.environ.get('OLLAMA_BASE_URL')
os.environ['OLLAMA_BASE_URL'] = 'http://invalid-url:11434'

change = ChangeEvent(change_type="delay", delay_days=5, affected_items=["TEST"], po_priority="critical")
context = OperationalContext(inventory_level=1.0)
decision = should_trigger_alert(change, context)

# Should use safe defaults, not crash
assert decision.trigger_alert == True, "Should alert on critical order even if Ollama down"
assert decision.is_fallback == True, "Should indicate fallback was used"

# Restore original URL
if original_url:
    os.environ['OLLAMA_BASE_URL'] = original_url

print("✅ Fallback Mechanism Works")
```

- [ ] Test runs without crashing
- [ ] Output shows "✅ Fallback Mechanism Works"

---

## 📋 Final Checklist

### Before Production Deployment

- [ ] All environment variables configured
- [ ] Ollama running and responsive
- [ ] All unit tests pass
- [ ] All functional tests pass
- [ ] Performance acceptable (<30s latency)
- [ ] Error handling tested
- [ ] Fallbacks verified
- [ ] Documentation reviewed
- [ ] Code integrated into main pipeline
- [ ] Team trained on module usage

### Production Deployment

- [ ] Ollama running on dedicated machine (not developer laptop)
- [ ] .env configured for production
- [ ] Error logging configured
- [ ] Monitoring/alerting set up
- [ ] Audit logging enabled
- [ ] Backup plan for Ollama failures
- [ ] Runbook created
- [ ] On-call procedure documented

---

## 🆘 Troubleshooting

### If Ollama connection fails:

```bash
# Check Ollama is running
ollama run gemma:2b

# Check port is accessible
curl http://localhost:11434/api/tags

# Check network
ping localhost
```

### If tests fail:

1. Verify Ollama running with `ollama run gemma:2b`
2. Check `.env` file has correct settings
3. Verify Python environment (`python --version`)
4. Check network connectivity
5. Look at error messages for specific issues

### If performance is slow:

- Verify Ollama has enough CPU/memory
- Check network latency
- Monitor Ollama logs
- Consider dedicated Ollama machine

---

## ✅ Sign-Off

**Date Completed:** ****\_\_\_\_****

**Verified By:** ****\_\_\_\_****

**Issues Found:**

```
None / See attached notes
```

**Ready for Production:** [ ] Yes [ ] No

**Notes:**

```
_____________________________________________________
_____________________________________________________
_____________________________________________________
```

---

## Support

**Questions?** See:

- QUICK_REFERENCE_OLLAMA.md (Quick reference)
- INTEGRATION_GUIDE.md (Complete guide)
- ALERT_DECISION_VALIDATION.md (Validation details)

**Ready to deploy!** 🚀
