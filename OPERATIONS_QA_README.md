# Hugo Operations QA Module

## Overview

The Operations QA module allows Hugo to answer analytical operational questions about production, inventory, and supply chain using Ollama (gemma:2b) as the reasoning engine.

**Key Concept:** A procurement operations copilot that thinks step-by-step about production capacity, bottlenecks, constraints, and what-if scenarios.

## Features

- **Step-by-step reasoning** - Ollama analyzes data methodically
- **Structured output** - Clear answer + constraints + bottlenecks
- **Plain text responses** - No markdown, no JSON, no emojis
- **Confidence levels** - Indicates reasoning certainty
- **Error handling** - Graceful degradation on Ollama failure
- **Offline capable** - Works entirely locally

## Example Questions

```
Production Capacity:
  "How many X-Series scooters can we build next week?"
  "What's our maximum production rate with current staffing?"

Bottleneck Analysis:
  "Which parts are current bottlenecks?"
  "Where are the constraints in our supply chain?"

Scenario Planning:
  "What happens if demand increases by 20%?"
  "Can we meet the deadline if motor delivery is delayed 5 days?"

Supplier Management:
  "Which suppliers should we prioritize for expedited orders?"
  "What's the risk exposure from our top 3 suppliers?"

Inventory Analysis:
  "How long can we sustain current production if supply stops?"
  "Which inventory items have the highest turnover rate?"
```

## API

### Function Signature

```python
answer_operational_question(
    question: str,
    erp_data: Optional[Dict[str, Any]] = None,
    orders: Optional[List[Dict[str, Any]]] = None,
    inventory: Optional[Dict[str, Any]] = None,
    bom_data: Optional[Dict[str, Any]] = None,
    ollama_url: str = "http://localhost:11434",
    model: str = "gemma:2b"
) -> OperationalAnswer
```

### Parameters

| Parameter    | Type | Description                          | Example                                  |
| ------------ | ---- | ------------------------------------ | ---------------------------------------- |
| `question`   | str  | Analytical question about operations | "How many units next week?"              |
| `erp_data`   | dict | ERP system data (optional)           | `{"capacity": 500, "lead_time": 2}`      |
| `orders`     | list | Active/upcoming orders               | `[{"order_id": "O-1", "qty": 100, ...}]` |
| `inventory`  | dict | Current inventory levels             | `{"MOTOR-A": 450, "FRAME-X": 250, ...}`  |
| `bom_data`   | dict | Bill of materials                    | `{"Product-X": {"MOTOR-A": 1, ...}}`     |
| `ollama_url` | str  | Ollama API endpoint                  | "http://localhost:11434"                 |
| `model`      | str  | Model name                           | "gemma:2b"                               |

### Return Value: OperationalAnswer

```python
class OperationalAnswer:
    question: str              # Original question
    answer: str                # Clear final answer (plain text)
    reasoning_steps: list[str] # Step-by-step reasoning
    constraints: list[str]     # Operational constraints
    bottlenecks: list[str]     # Supply chain bottlenecks
    confidence: str            # "high", "medium", or "low"
    is_error: bool             # True if error occurred
    error: Optional[str]       # Error message if any
```

### Methods

```python
result = answer_operational_question(...)

# Display formatted
print(result)

# Get as dictionary
data = result.to_dict()

# Access components
answer = result.answer
for constraint in result.constraints:
    print(f"- {constraint}")
```

## Usage Examples

### Basic Question

```python
from services.operations_qa import answer_operational_question

result = answer_operational_question(
    question="How many scooters can we build next week?",
    inventory={"MOTOR": 200, "FRAME": 150, "BATTERY": 180},
    bom_data={"Scooter": {"MOTOR": 1, "FRAME": 1, "BATTERY": 1}}
)

print(result.answer)
# Output: "We can build 150 scooters limited by frame inventory..."

print(result.bottlenecks)
# Output: ["Frame inventory at 150 units"]
```

### With ERP and Orders

```python
result = answer_operational_question(
    question="Can we meet the deadline for order O-2025-001?",
    orders=[{"order_id": "O-2025-001", "due_date": "2025-01-31", "qty": 200}],
    inventory={"PART-A": 300, "PART-B": 150},
    erp_data={"production_rate": 100, "lead_time_weeks": 2}
)

print(result.answer)
print(f"Confidence: {result.confidence}")
```

### Scenario Analysis

```python
# What-if scenario
result = answer_operational_question(
    question="What if demand increases by 30%?",
    orders=[{"qty": 100}, {"qty": 80}],  # Current demand
    inventory={"CRITICAL": 50, "NORMAL": 500},
    erp_data={"capacity": 400}
)

if "bottleneck" in str(result.bottlenecks).lower():
    print("WARNING: Demand increase would create bottlenecks")
```

### Integration with Hugo Agent

```python
class HugoAgent:
    def process_strategic_question(self, question: str):
        """Answer operational questions."""
        from services.operations_qa import answer_operational_question

        result = answer_operational_question(
            question=question,
            erp_data=self._get_erp_data(),
            orders=self._get_active_orders(),
            inventory=self._get_inventory(),
            bom_data=self._get_bom_data()
        )

        return result
```

## Response Format

The module returns **plain text**, never markdown or JSON:

```
Question: How many X-Series can we build next week?

Answer: We can build 150 X-Series scooters next week, limited by FRAME-X inventory at 150 units.

Constraints:
  - Supply lead time for frames is 2 weeks
  - Current factory operates 5 days per week
  - Motor supply is adequate with 450 units

Bottlenecks:
  - FRAME-X inventory at 150 units (needed for 150 scooters)
  - Supply replenishment lead time: 2 weeks
```

## Prompt Design

The module uses optimized prompts for gemma:2b:

1. **Step-by-step reasoning** - Ollama thinks through problem methodically
2. **Data context** - All operational data provided as formatted text
3. **Clear instructions** - Structured sections for answer, reasoning, constraints
4. **Plain language** - No markdown, JSON, or special formatting

Temperature: 0.3 (moderate for balanced reasoning and consistency)

## Error Handling

On Ollama failure:

- Returns OperationalAnswer with `is_error=True`
- Includes error message in `error` field
- Sets confidence to "low"
- Suggests manual review

```python
result = answer_operational_question(question)

if result.is_error:
    print(f"Error: {result.error}")
    print("Fallback: Manual analysis required")
```

## Testing

Run the test suite:

```bash
# Start Ollama first
ollama run gemma:2b

# Run tests
python test_operations_qa.py
```

Test file includes:

- Production capacity analysis
- Bottleneck identification
- Demand scenario planning
- Supplier risk analysis

## Integration Patterns

### Pattern 1: Batch Analysis

```python
questions = [
    "What's our production capacity?",
    "Which parts bottleneck us?",
    "What if demand increases 20%?"
]

for q in questions:
    result = answer_operational_question(q, ...)
    analysis_results.append(result)
```

### Pattern 2: Real-time Alerts

```python
if detected_supply_delay:
    result = answer_operational_question(
        f"How does the {part} delay impact production?",
        ...
    )
    if result.bottlenecks:
        alert_operations_manager(result)
```

### Pattern 3: What-If Scenarios

```python
for demand_increase in [10, 20, 30, 40]:
    result = answer_operational_question(
        f"Can we handle {demand_increase}% more demand?",
        ...
    )
    scenario_analysis[demand_increase] = result
```

### Pattern 4: Web API

```python
@app.route("/api/operations/ask", methods=["POST"])
def ask_question():
    q = request.json["question"]
    result = answer_operational_question(q, ...)
    return result.to_dict()
```

## Performance

| Metric                | Value                    |
| --------------------- | ------------------------ |
| Model                 | gemma:2b (2B parameters) |
| Typical response time | 3-8 seconds              |
| Temperature           | 0.3 (moderate reasoning) |
| Timeout               | 120 seconds              |
| Hardware              | CPU or GPU capable       |

## Constraints & Limitations

- **Data quality depends on input** - Garbage in, garbage out
- **Reasoning matches model capability** - gemma:2b vs Gemini Pro
- **No real-time data integration** - Data passed at question time
- **No learning/memory** - Each question independent
- **Generic reasoning** - No domain-specific rules

## Best Practices

1. **Provide complete context** - Include all relevant data
2. **Be specific in questions** - "How many units?" not "Status?"
3. **Validate constraints** - Cross-check identified bottlenecks
4. **Use for analysis** - Not a replacement for domain expertise
5. **Check confidence** - Low confidence answers need verification
6. **Monitor Ollama** - Ensure model stays responsive

## Files

- `services/operations_qa.py` - Core module
- `test_operations_qa.py` - Test suite
- `operations_qa_integration.py` - Integration examples

## Requirements

- Ollama running on localhost:11434
- gemma:2b model installed
- requests library (already in requirements)
- No additional dependencies

## Future Enhancements

- [ ] Multi-turn conversations (remember context)
- [ ] Real-time data feeds (auto-refresh data)
- [ ] Custom reasoning templates
- [ ] Integration with BI dashboards
- [ ] Confidence scoring improvements
- [ ] Batch question processing
- [ ] Export analysis to reports

## Troubleshooting

**Q: "Cannot reach Ollama" error**

- A: Start Ollama: `ollama run gemma:2b`

**Q: Response is too generic**

- A: Provide more specific data and context

**Q: Confidence is always "low"**

- A: Check data quality and completeness

**Q: Takes too long to respond**

- A: Reduce context size or use GPU acceleration

---

**Module Status:** Production-ready for hackathon deployment
