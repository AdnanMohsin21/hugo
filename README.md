# 🐕 Hugo - Inbox Watchdog Agent

A hackathon MVP backend that monitors supplier emails for delivery changes, matches them with purchase orders, and assesses operational risk using AI.

## Architecture

```
hugo/
├── main.py                    # Pipeline orchestrator & demo
├── config/
│   └── settings.py            # Environment configuration
├── services/
│   ├── email_ingestion.py     # Gmail API integration
│   ├── delivery_detector.py   # Gemini Pro LLM extraction
│   ├── erp_matcher.py         # PO matching logic
│   ├── vector_store.py        # ChromaDB for RAG
│   └── risk_engine.py         # Risk reasoning
├── models/
│   └── schemas.py             # Pydantic data models
├── utils/
│   └── helpers.py             # Utilities
└── data/                      # Auto-generated data directory
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your GCP project settings
```

### 3. Run Demo (with mock data)

```bash
python main.py
```

The demo works without GCP credentials using mock emails and rule-based risk assessment.

## Full Setup (Production)

### Gmail API Setup

1. Create a GCP project and enable Gmail API
2. Create OAuth 2.0 credentials (Desktop app)
3. Download as `credentials.json`
4. First run will prompt for Gmail authorization

### Vertex AI Setup

1. Enable Vertex AI API in your GCP project
2. Authenticate with `gcloud auth application-default login`
3. Update `GCP_PROJECT_ID` in `.env`

## Usage with Streamlit

```python
from main import HugoAgent

# Initialize agent
agent = HugoAgent()

# Process emails (async for Streamlit)
alerts = await agent.process_emails_async(max_emails=10)

# Or process text directly
alert = agent.process_single_email_from_text(
    sender="supplier@example.com",
    subject="Delivery Delay Notice",
    body="Your order PO-123 will be delayed by 5 days..."
)
```

## Pipeline Flow

1. **Email Ingestion** → Fetch from Gmail or process text input
2. **Change Detection** → Gemini Pro extracts delivery changes
3. **PO Matching** → Match to ERP purchase orders
4. **Context Retrieval** → RAG with historical incidents
5. **Risk Assessment** → LLM reasoning on operational impact
6. **Alert Generation** → Structured output with recommendations

## Tech Stack

- **Python 3.10+**
- **Vertex AI** - Gemini Pro for LLM operations
- **ChromaDB** - Local vector database for RAG
- **Gmail API** - Email ingestion
- **Pydantic** - Data validation

## License

MIT - Built for 48-hour hackathon
