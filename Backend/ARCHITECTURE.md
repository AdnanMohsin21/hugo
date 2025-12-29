# Hugo Ollama Architecture

## System Overview

Hugo is an AI procurement agent that monitors supplier emails for delivery changes and assesses operational risk. The refactored system uses **Ollama (gemma:2b)** as the sole LLM engine, eliminating all cloud dependencies.

```
┌─────────────────────────────────────────────────────────────┐
│                    Hugo Agent                                │
│                 (Main Orchestrator)                          │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┬────────────┬──────────────┐
        │                 │            │              │
        ▼                 ▼            ▼              ▼
   ┌─────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐
   │  Email  │  │  Delivery    │  │   ERP    │  │ Vector   │
   │  Service│  │  Detector    │  │  Matcher │  │  Store   │
   └─────────┘  └──────┬───────┘  └──────────┘  └──────────┘
                       │
                       │ (Ollama)
                       ▼
              ┌────────────────────┐
              │  RiskEngine        │
              │  RiskAssessor      │
              └────┬───────────────┘
                   │
                   ▼ (Ollama HTTP POST)
          ┌────────────────────┐
          │   OLLAMA (LOCAL)   │
          │   gemma:2b         │
          │ :11434             │
          └────────────────────┘
                   │
                   │ (JSON Response)
                   ▼
           ┌──────────────────┐
           │ RiskAssessment   │
           │ Result           │
           └──────────────────┘
```

## Core Components

### 1. DeliveryDetector (`services/delivery_detector.py`)

**Purpose:** Extract delivery changes from supplier emails

**LLM Engine:** Ollama (gemma:2b)

**Process:**

1. Takes Email object
2. Builds extraction prompt with date context
3. Calls Ollama API: POST `/api/generate`
4. Parses JSON response
5. Returns DeliveryChange object

**Key Features:**

- Handles vague date phrases ("next Friday", "end of month")
- Retry logic for JSON parsing (3 attempts)
- Confidence scoring (0.0-1.0)
- Structured extraction: order_id, sku, dates, reason

**Prompt Size:** ~350 tokens (optimized for gemma:2b)

### 2. RiskEngine (`services/risk_engine.py`)

**Purpose:** Assess operational risk for delivery changes

**LLM Engine:** Ollama (gemma:2b)

**Process:**

1. Takes DeliveryChange, PurchaseOrder, HistoricalContext
2. Formats context into prompt
3. Calls Ollama API: POST `/api/generate`
4. Parses JSON response
5. Returns RiskAssessment object

**Key Features:**

- Considers: delay severity, supplier reliability, PO priority
- Context-aware: historical data, similar incidents
- Returns: risk_level, risk_score, impact_summary, actions

**Prompt Size:** ~400 tokens (optimized for gemma:2b)

### 3. RiskAssessor (NEW) (`services/ollama_risk_assessor.py`)

**Purpose:** Pure Ollama-powered risk assessment (NO heuristics)

**API:** `assess_risk_with_ollama(email_text, purchase_order, historical_context)`

**Key Difference:**

- **Risk level and risk_score are determined 100% by Ollama**
- No Python-side heuristics or weighted rules
- All reasoning comes from the LLM

**Process:**

1. Builds assessment prompt with all context
2. Calls Ollama API: POST `/api/generate` (non-streaming)
3. Validates JSON response structure
4. Returns RiskAssessmentResult

**Error Handling:**

- JSON parsing errors → retry or safe default
- Connection errors → safe default (MEDIUM risk)
- Invalid responses → safe default with error logged
- All errors logged for debugging

**Safe Default Behavior:**

- risk_level: "medium"
- risk_score: 0.5
- drivers: ["Unable to assess - Ollama unavailable"]
- actions: ["Manual review required", "Contact supplier"]

**Prompt Size:** ~500 tokens (comprehensive assessment)

### 4. RAGReasoner (`services/rag_reasoner.py`)

**Purpose:** Risk reasoning with retrieved context

**LLM Engine:** Ollama (gemma:2b)

**Process:**

1. Builds prompt with email + ERP + retrieved context
2. Calls Ollama API: POST `/api/generate`
3. Parses JSON response
4. Returns RiskAssessment object

**Key Features:**

- Combines: email analysis, ERP data, historical context
- Retrieves similar incidents from vector DB
- Generates reasoning and actions

**Prompt Size:** ~300 tokens (minimal context injection)

## API Calls to Ollama

### Request Format

```http
POST http://localhost:11434/api/generate HTTP/1.1
Content-Type: application/json

{
  "model": "gemma:2b",
  "prompt": "...",
  "stream": false,
  "temperature": 0.2
}
```

### Response Format

```json
{
  "model": "gemma:2b",
  "created_at": "2025-01-15T10:30:45Z",
  "response": "{\"risk_level\": \"high\", \"risk_score\": 0.72, ...}",
  "done": true,
  "context": [...],
  "total_duration": 5000000000,
  "load_duration": 1000000000,
  "prompt_eval_count": 42,
  "prompt_eval_duration": 2000000000,
  "eval_count": 28,
  "eval_duration": 2000000000
}
```

### Configuration

```python
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma:2b"
TEMPERATURE = 0.2  # Low for consistent reasoning
TIMEOUT = 120  # seconds
STREAM = False  # Non-streaming for simplicity
```

## Prompt Engineering for gemma:2b

### Principles

1. **Concise** - Fewer tokens, clearer reasoning
2. **Structured** - Clear sections and format
3. **Explicit** - Direct JSON schema inline
4. **Task-focused** - What to do, not how to think

### Example Structure

```
[Task description]

=== CONTEXT SECTION 1 ===
[Formatted data]

=== CONTEXT SECTION 2 ===
[Formatted data]

---

OUTPUT JSON ONLY:
{
  "field1": "value",
  "field2": value,
  ...
}
```

### JSON Parsing Strategy

````python
1. Strip markdown code blocks (```json ... ```)
2. Parse with json.loads()
3. Validate required fields
4. Validate field types and ranges
5. Return parsed result or error
````

## Offline Capability

✓ **No Cloud Dependencies**

- All processing local
- No network calls except to localhost:11434
- Works completely offline

✓ **Local Model**

- gemma:2b runs on local machine
- Can run on CPU (slower) or GPU (faster)
- ~2GB model size

✓ **Deterministic**

- Low temperature (0.2)
- Same input → same output
- Good for testing and debugging

## Error Handling Strategy

```
┌─────────────────────────────┐
│  Call Ollama API            │
└────────────┬────────────────┘
             │
      ┌──────┴─────────────┐
      │                    │
      ▼                    ▼
  Success            Connection Error
     │                    │
     │              (Timeout, Network, DNS)
     │                    │
     ▼                    ▼
  Parse JSON         Safe Default
     │                    │
  ┌──┴──────┐            │
  │          │            │
  ▼          ▼            │
Valid     Invalid      Mid-Request
  │          │            │
  ▼          ▼            ▼
Result   Retry/Default  Safe Default
```

**Safe Default:**

- risk_level = "medium"
- risk_score = 0.5
- drivers = ["Unable to assess"]
- actions = ["Manual review required"]
- is_fallback = True
- error = "Error message"

## Configuration Files

### `.env` (required for Ollama)

```env
OLLAMA_MODEL=gemma:2b
OLLAMA_BASE_URL=http://localhost:11434
```

### `.env` (optional for embeddings/other features)

```env
GCP_PROJECT_ID=...
EMBEDDING_MODEL=text-embedding-004
```

## Testing & Validation

### Unit Tests

```python
# Run: python test_ollama_risk_assessor.py
- Tests basic risk assessment
- Validates JSON parsing
- Checks fallback behavior
- Verifies response structure
```

### Integration Tests

```python
# Run: python integration_example.py
- Tests full pipeline
- Shows real-world usage
- Demonstrates fallback behavior
```

### Manual Testing

```bash
# 1. Start Ollama
ollama run gemma:2b

# 2. Check connectivity
curl http://localhost:11434/api/tags

# 3. Run test
python test_ollama_risk_assessor.py
```

## Performance Characteristics

### Model: gemma:2b

- **Parameters:** 2 Billion
- **Size:** ~1.6 GB (quantized)
- **Speed:** Fast (typical 100-500ms per inference)
- **Memory:** ~2-4 GB loaded
- **Hardware:** CPU or GPU capable

### Typical Response Times

| Operation           | Time  | Notes               |
| ------------------- | ----- | ------------------- |
| Model Load          | 2-5s  | First call only     |
| Delivery Extraction | 1-3s  | ~350 token prompt   |
| Risk Assessment     | 2-5s  | ~500 token prompt   |
| Full Pipeline       | 5-15s | Multiple operations |

## Scalability Notes

- **Single Instance:** Adequate for <1000 emails/day
- **Concurrent Requests:** Ollama serializes by default
- **Optimization:** Use batch processing for multiple emails
- **Production:** Consider Ollama clustering or queue

## Advantages Over Cloud LLM

1. **Cost:** Free, no API billing
2. **Speed:** Local network, no roundtrips
3. **Privacy:** Data stays local, no cloud transmission
4. **Compliance:** No data leaves your machine
5. **Offline:** Works without internet
6. **Control:** Model runs on your hardware

## Limitations Compared to Gemini Pro

1. **Quality:** Smaller model (2B vs 70B+)
2. **Features:** No multimodal, no function calling
3. **Context:** Shorter context window
4. **Speed:** Slower on CPU-only systems

## Migration Path

### Phase 1: Parallel Deployment ✓

- Keep existing Vertex AI code
- Deploy new Ollama code alongside
- Test in non-critical path

### Phase 2: Rollover

- Route new requests to Ollama
- Keep fallback to rule-based assessment
- Monitor results

### Phase 3: Full Migration

- Deprecate Vertex AI LLM calls
- Keep vertex_ai.py for embeddings if needed
- Full Ollama-based reasoning

---

**Status:** All refactoring complete. Ready for hackathon deployment.
