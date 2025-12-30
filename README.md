🤖 Hugo — AI Procurement & Operations Copilot for Voltway

Hugo is an operational AI agent designed to help fast-growing manufacturing companies detect supply risks, resolve inventory conflicts, and make data-driven procurement decisions in real time. Built for the Dryft – Running Industrial Operations on AI challenge.

📌 Problem Context

Modern industrial procurement is not just warehouse management — it is a high-stakes orchestration problem involving:

Volatile supplier lead times

Complex multi-part Bills of Materials (BOMs)

Conflicting demand from e-commerce and fleet contracts

Aging and excess inventory tying up capital

Fragmented data across ERP systems, emails, and contracts

Human-driven workflows struggle to reason across these constraints fast enough.

🚀 What is Hugo?

Hugo is an AI-powered operational copilot that:

Listens to supplier emails in real time

Detects delivery delays, quantity changes, and risks

Resolves priority conflicts when demand exceeds stock

Identifies hoarding and excess inventory risks

Produces clear, actionable insights for operations teams

Hugo is hybrid by design:

Uses LLMs only where semantic understanding is required

Uses deterministic logic for all critical business decisions

This ensures explainability, reliability, and production realism.

🎯 Core Capabilities 🔔 Reactive Intelligence

Parses supplier emails (Gmail API)

Detects:

Delivery delays

Quantity changes

ETA updates

Flags high-risk supplier communications

⚔️ Priority Wars (Demand vs Stock Conflicts)

Identifies parts where total demand exceeds available stock

Resolves conflicts across:

Fleet framework contracts

Fleet spot orders

Webshop demand

Allocates stock by business priority

Transparently lists deferred (“loser”) orders

📦 Inventory Balancer

Analyzes stock vs historical demand

Classifies actions:

KEEP_STOCK

REDUCE_STOCK

INVESTIGATE

Provides confidence scores and rationale

🧱 Hoarding Risk Detection

Detects aging or unused inventory

Quantifies excess units

Estimates potential working capital recovery

🧠 RAG-Augmented Risk Reasoning

Retrieves historical context for similar past issues

Enhances risk assessment with memory (not hallucination)

🧩 System Architecture High-Level Flow

Supplier emails + ERP-like datasets ingested

LLM extracts semantic signals (only where needed)

Deterministic engines compute:

Risk scores

Priority resolutions

Inventory actions

Streamlit dashboard presents actionable outcomes

LLMs never make final business decisions.

🏗️ Tech Stack Layer Technology Language Python 3.10+ Frontend Streamlit Email Ingestion Gmail API LLM (Optional) Hugging Face / OpenAI compatible Vector Store Lightweight in-memory RAG Data CSV-based ERP simulation Visualization Streamlit Components Architecture Modular, Agent-based

🖥️ Frontend Experience User Workflow

Open Hugo Dashboard

Click Run Hugo Analysis

Hugo:

Fetches latest supplier emails

Processes all datasets

Runs risk, inventory, and priority analysis

User receives:

Alerts

Inventory recommendations

Priority conflict summaries

Hoarding risk insights

No manual data stitching required.

🧪 Sample Outputs

Delivery Delay Alert

Supplier email flagged

Risk score computed

Recommended actions generated

Priority Conflict Resolution

Part: P300

Demand: 962

Stock: 158

Orders fulfilled by priority

Deferred orders clearly listed

Hoarding Risk

Total excess units detected

Estimated capital unlocked

🧠 Why This Fits the Dryft Challenge

✔ Integrates structured + unstructured data ✔ Solves real operational problems ✔ Demonstrates reasoning under constraints ✔ Focuses on depth, not feature sprawl ✔ Aligns with agentic AI principles

Hugo doesn’t “chat”. Hugo thinks operationally.

🔮 Future Extensions

Slack / Email alert automation

What-if simulations (“+20% webshop demand”)

Supplier reliability scoring

Auto-tuned reorder points

PDF BOM ingestion

Environment Variables
To run this project, you will need to add the following environment variables to your .env file

GMAIL_CLIENT_ID=your_google_oauth_client_id GMAIL_CLIENT_SECRET=your_google_oauth_client_secret GMAIL_REFRESH_TOKEN=your_refresh_token GMAIL_USER_EMAIL=your_email@gmail.com

HF_API_TOKEN=your_huggingface_api_key HF_MODEL_NAME=google/flan-t5-large

Badges
Add badges from somewhere like: shields.io

MIT LicenseGPLv3 LicenseAGPL License

Authors
👥 Team

Adnan Mohsin — Backend, Architecture, Intelligence Systems

Al Amin — Frontend & Backend Integration

Tech Stack
🏗️ Tech Stack Layer Technology Language Python 3.10+ Frontend Streamlit Email Ingestion Gmail API LLM (Optional) Hugging Face / OpenAI compatible Vector Store Lightweight in-memory RAG Data CSV-based ERP simulation Visualization Streamlit Components Architecture Modular, Agent-based

Installation
Install my-project with npm

🛠️ Setup & Run 1️⃣ Clone Repository git clone https://github.com/AdnanMohsin21/hugo.git cd hugo

2️⃣ Create Virtual Environment python -m venv .venv source .venv/bin/activate # Windows: .venv\Scripts\activate

3️⃣ Install Dependencies pip install -r requirements.txt

4️⃣ Run Backend python main.py

5️⃣ Run Frontend streamlit run Frontend/app.py

Documentation
📂 Project Structure hugo/ ├── Backend/ │ ├── agents/ │ │ ├── signal_extractor.py │ │ ├── delivery_detector.py │ │ ├── risk_engine.py │ │ ├── priority_arbiter.py │ │ ├── inventory_balancer.py │ │ └── hoarding_detector.py │ ├── services/ │ ├── utils/ │ └── models/ ├── Frontend/ │ └── app.py ├── data/ │ ├── sales_orders.csv │ ├── stock_levels.csv │ ├── stock_movements.csv │ ├── suppliers.csv │ ├── bom.csv │ └── material_master.csv ├── analytics/ ├── config/ ├── main.py └── README.md
