# 🤖 Hugo — AI Procurement & Operations Copilot for Voltway

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)
![Status](https://img.shields.io/badge/Status-Prototype-green)

**Hugo** is an AI-powered operational copilot built to help fast-growing manufacturing companies detect supply risks, resolve inventory conflicts, and make data-driven procurement decisions in real time.

Built for the **Dryft – Running Industrial Operations on AI** challenge.

---

## 📌 Problem Context

Modern industrial procurement is no longer just warehouse management. It is a high-stakes orchestration problem involving:

- Volatile supplier lead times  
- Complex multi-part Bills of Materials (BOMs)  
- Conflicting demand from e-commerce and fleet contracts  
- Aging and excess inventory tying up capital  
- Fragmented data across ERP systems, emails, and contracts  

Human-driven workflows struggle to reason across these constraints fast enough.

---

## 🚀 What is Hugo?

Hugo is an AI-powered **procurement and operations copilot** that:

- 🎧 Listens to supplier emails in real time  
- ⚠️ Detects delivery delays, quantity changes, and supply risks  
- ⚔️ Resolves demand vs stock priority conflicts  
- 🧱 Identifies hoarding and excess inventory risks  
- 📊 Produces clear, actionable insights for operations teams  

### Hybrid by Design

Hugo uses:
- **LLMs** only where semantic understanding is required  
- **Deterministic logic** for all critical business decisions  

LLMs never make final operational decisions.  
This ensures explainability, reliability, and production realism.

---

## 🎯 Core Capabilities

### 🔔 Reactive Intelligence
- Parses supplier emails via Gmail API  
- Detects delivery delays, ETA changes, and quantity updates  
- Flags high-risk supplier communications automatically  

### ⚔️ Priority Wars (Demand vs Stock Conflicts)
- Identifies parts where total demand exceeds available stock  
- Resolves conflicts across:
  - Fleet framework contracts  
  - Fleet spot orders  
  - Webshop demand  
- Allocates stock by business priority  
- Transparently lists deferred (“loser”) orders  

### 📦 Inventory Balancer
- Analyzes stock vs historical demand  
- Classifies actions:
  - `KEEP_STOCK`  
  - `REDUCE_STOCK`  
  - `INVESTIGATE`  
- Provides confidence scores with reasoning  

### 🧱 Hoarding Risk Detection
- Detects aging or unused inventory  
- Quantifies excess units  
- Estimates potential working capital recovery  

### 🧠 RAG-Augmented Risk Reasoning
- Retrieves historical context for similar past issues  
- Enhances risk assessment using memory, not hallucination  

---

## 🧩 System Architecture

### High-Level Flow

1. Supplier emails and ERP-like datasets are ingested  
2. LLMs extract semantic signals only where required  
3. Deterministic engines compute:
   - Risk scores  
   - Priority resolutions  
   - Inventory actions  
4. Streamlit dashboard presents actionable outcomes  

*LLMs assist. Logic decides.*


::contentReference[oaicite:0]{index=0}


---

## 🏗️ Tech Stack

| Layer | Technology |
|-----|-----------|
| Language | Python 3.10+ |
| Frontend | Streamlit |
| Email Ingestion | Gmail API |
| LLM (Optional) | Hugging Face / OpenAI compatible |
| Vector Store | Lightweight in-memory RAG |
| Data | CSV-based ERP simulation |
| Visualization | Streamlit Components |
| Architecture | Modular, Agent-based |

---

## 🖥️ Frontend Experience

### User Workflow

1. Open **Hugo Dashboard**  
2. Click **Run Hugo Analysis**  
3. Hugo:
   - Fetches latest supplier emails  
   - Processes all datasets  
   - Runs risk, inventory, and priority analysis  
4. User receives:
   - Supply risk alerts  
   - Inventory recommendations  
   - Priority conflict summaries  
   - Hoarding risk insights  

No manual data stitching required.

---

## 🧪 Sample Outputs

### Delivery Delay Alert
- Supplier email flagged  
- Risk score computed  
- Recommended actions generated  

### Priority Conflict Resolution
- Part: `P300`  
- Demand: `962`  
- Stock: `158`  
- Orders fulfilled by priority  
- Deferred orders clearly listed  

### Hoarding Risk
- Total excess units detected  
- Estimated capital unlocked  

---

## 🧠 Why This Fits the Dryft Challenge

- Integrates structured and unstructured data  
- Solves real operational problems  
- Demonstrates reasoning under constraints  
- Focuses on depth over feature sprawl  
- Aligns with agentic AI principles  

**Hugo doesn’t chat. Hugo thinks operationally.**

---

## 🔮 Future Extensions

- Slack and email alert automation  
- What-if simulations (e.g. +20% webshop demand)  
- Supplier reliability scoring  
- Auto-tuned reorder points  
- PDF BOM ingestion  

---

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.10+  
- Google Cloud Console credentials (Gmail API)  
- Hugging Face API token  

---

1️⃣ Environment Variables

#### API Keys & Tokens

To use Hugo, you must configure your own API credentials.

Hugo does not ship with hard-coded API keys.

Required:
- Google Gmail API credentials (OAuth)
- Hugging Face API token (for optional LLM features)

These credentials are loaded via environment variables using a `.env` file.

Create a `.env` file in the root directory:

```env
# Google Gmail API Configuration
GMAIL_CLIENT_ID=your_google_oauth_client_id
GMAIL_CLIENT_SECRET=your_google_oauth_client_secret
GMAIL_REFRESH_TOKEN=your_refresh_token
GMAIL_USER_EMAIL=your_email@gmail.com

# Hugging Face Configuration
HF_API_TOKEN=your_huggingface_api_key
HF_MODEL_NAME=google/flan-t5-large

```

2️⃣ Installation Steps
```
Clone the Repository
git clone https://github.com/AdnanMohsin21/hugo.git
cd hugo

Create Virtual Environment
# macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate

Install Dependencies
pip install -r requirements.txt
```

3️⃣ Run the Application

Run frontend and backend separately.
```
# Terminal A (Frontend)
streamlit run Frontend/app.py

# Terminal B (Backend)
python Backend/main.py
```

## 📂 Project Structure

hugo/
├── Frontend/
│   ├── app.py
│   └── streamlit/
│       └── config.toml
│
├── Backend/
│   ├── agents/
│   │   ├── signal_extractor.py
│   │   ├── delivery_detector.py
│   │   ├── risk_engine.py
│   │   ├── priority_arbiter.py
│   │   ├── inventory_balancer.py
│   │   └── hoarding_detector.py
│   │
│   ├── services/
│   ├── utils/
│   ├── models/
│   ├── analytics/
│   ├── config/
│   ├── data/
│   │   ├── sales_orders.csv
│   │   ├── stock_levels.csv
│   │   ├── stock_movements.csv
│   │   ├── suppliers.csv
│   │   ├── bom.csv
│   │   └── material_master.csv
│   │
│   └── main.py
│
└── README.md


## Authors- (TEAM)

Adnan Mohsin — Backend, Architecture, Intelligence Systems
Al Amin — Frontend & Backend Integration



