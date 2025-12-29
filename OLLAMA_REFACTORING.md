"""
OLLAMA-POWERED RISK ASSESSMENT REFACTORING
============================================

## Summary of Changes

This refactoring replaces all mock/heuristic reasoning with pure Ollama-powered
LLM reasoning across the Hugo procurement agent. The system is now 100% Ollama-only
with no Vertex AI or cloud dependencies.

# FILES MODIFIED

1. services/delivery_detector.py

   - Replaced Vertex AI imports with OllamaLLM
   - Direct Ollama API calls for email extraction
   - Removed mock detection fallback (\_mock_detect method)
   - Optimized prompts for gemma:2b (more concise)
   - JSON parsing with retry logic maintained

2. services/risk_engine.py

   - Replaced vertexai.GenerativeModel with OllamaLLM
   - Direct Ollama API calls for risk assessment
   - Simplified prompt for gemma:2b efficiency
   - Maintains RiskAssessment schema compatibility

3. services/rag_reasoner.py

   - Removed USE_VERTEX_AI conditional logic
   - Forces Ollama-only reasoning
   - Updated prompt template for optimal gemma:2b performance
   - Fallback assessment still uses basic heuristics (safe default only)

4. services/ollama_risk_assessor.py (NEW)

   - Dedicated risk assessment module
   - Pure LLM reasoning - NO heuristics for risk determination
   - Direct HTTP POST to http://localhost:11434/api/generate
   - Robust JSON parsing with graceful error handling
   - RiskAssessmentResult dataclass for structured output

5. main.py
   - check_llm_provider_status() now forces Ollama only
   - Removed USE_VERTEX_AI branching logic
   - Single LLM provider configuration

# DESIGN PRINCIPLES

1. NO HEURISTICS FOR RISK DETERMINATION

   - Risk level and risk_score come ONLY from Ollama reasoning
   - No if-else logic for risk calculation
   - No weights or multipliers in Python code

2. OLLAMA AS SOLE LLM ENGINE

   - All prompts optimized for gemma:2b
   - HTTP POST to /api/generate endpoint
   - Non-streaming responses for simplicity
   - Temperature: 0.2 (low) for consistent reasoning

3. ROBUST ERROR HANDLING

   - JSON parsing with validation
   - Graceful degradation on Ollama failure
   - Safe default assessment (MEDIUM risk) when LLM unavailable
   - All errors logged for debugging

4. HACKATHON-READY & OFFLINE-CAPABLE
   - No cloud dependencies
   - Works fully offline with local Ollama
   - Deterministic behavior (low temperature)
   - Fast response times (gemma:2b is lightweight)

# NEW FUNCTION: assess_risk_with_ollama()

Located in: services/ollama_risk_assessor.py

Signature:
assess_risk_with_ollama(
email_text: str,
purchase_order: Optional[Dict[str, Any]] = None,
historical_context: Optional[Dict[str, Any]] = None,
ollama_url: str = "http://localhost:11434",
model: str = "gemma:2b"
) -> RiskAssessmentResult

Returns: RiskAssessmentResult object with:

- risk_level: "low" | "medium" | "high" | "critical"
- risk_score: 0.0 to 1.0 (determined by Ollama)
- drivers: list of risk factors identified by Ollama
- recommended_actions: list of actionable items from Ollama
- is_fallback: bool indicating if safe default was used
- error: str with error message if fallback used

# PROMPT OPTIMIZATION FOR GEMMA:2B

Prompts have been simplified and optimized:

DELIVERY EXTRACTION PROMPT

- Removed verbose explanations
- Clear JSON structure definition
- Concise rules for vague dates
- ~350 tokens (previously ~800)

RISK ASSESSMENT PROMPT

- Structured sections (EMAIL, PO, HISTORY)
- Clear risk level definitions
- JSON output format inline
- ~400 tokens (previously ~900)

RAG REASONING PROMPT

- Minimal context injection
- Direct JSON schema
- ~300 tokens (previously ~700)

# TESTING

To test the new risk assessor:

1. Start Ollama with gemma:2b model
   $ ollama run gemma:2b

2. Run the test script
   $ python test_ollama_risk_assessor.py

Expected output:

- Risk Level: (low|medium|high|critical)
- Risk Score: (0.0-1.0)
- Drivers: (list of risk factors)
- Actions: (list of recommendations)

# MIGRATION NOTES

1. DeliveryDetector

   - No API changes - drop-in replacement
   - Will fail gracefully if Ollama unavailable

2. RiskEngine

   - Existing code paths still work
   - Uses assess_risk() method
   - Returns RiskAssessment objects

3. New Code
   - Use assess_risk_with_ollama() for pure LLM reasoning
   - Direct return of RiskAssessmentResult
   - No heuristics, pure LLM logic

# DEPENDENCIES

Required:

- requests (for HTTP calls)
- Ollama running on localhost:11434
- gemma:2b model installed in Ollama

No new Python packages needed beyond existing requirements.

# CONFIGURATION

In .env:
OLLAMA_MODEL=gemma:2b (or any installed model)
OLLAMA_BASE_URL=http://localhost:11434

Remove from .env:

- USE_VERTEX_AI (no longer used)
- GCP_PROJECT_ID (no longer used)
- GCP_LOCATION (no longer used)
- GEMINI_MODEL (no longer used)

# OFFLINE CAPABILITY

✓ Works completely offline
✓ No external API calls
✓ No internet required
✓ All reasoning local to machine
✓ Deterministic (low temperature)
✓ Hackathon-ready: just run Ollama locally

# NEXT STEPS

1. Verify Ollama is running with gemma:2b
2. Test risk assessment with test_ollama_risk_assessor.py
3. Integrate assess_risk_with_ollama() into main pipeline
4. Remove all Vertex AI references from codebase
5. Clean up unused imports and settings
   """
