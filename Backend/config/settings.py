"""
Hugo - Inbox Watchdog Agent
Configuration settings module

Loads environment variables and provides centralized configuration
for all services including GCP, Gmail API, and vector store settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


class Settings:
    """Central configuration for Hugo agent."""
    
    # Google Cloud Platform settings
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "your-gcp-project-id")
    GCP_LOCATION: str = os.getenv("GCP_LOCATION", "us-central1")
    
    # Vertex AI model settings
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
    
    # Gmail API settings
    GMAIL_SCOPES: list = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.labels",
    ]
    GMAIL_CREDENTIALS_PATH: str = os.getenv(
        "GMAIL_CREDENTIALS_PATH", 
        str(Path(__file__).parent.parent / "credentials.json")
    )
    GMAIL_TOKEN_PATH: str = os.getenv(
        "GMAIL_TOKEN_PATH",
        str(Path(__file__).parent.parent / "token.json")
    )
    
    # Email filtering settings
    SUPPLIER_LABEL: str = os.getenv("SUPPLIER_LABEL", "Suppliers")
    MAX_EMAILS_PER_FETCH: int = int(os.getenv("MAX_EMAILS_PER_FETCH", "50"))
    
    # Vector store settings (ChromaDB)
    VECTOR_DB_PATH: str = os.getenv(
        "VECTOR_DB_PATH",
        str(Path(__file__).parent.parent / "data" / "chroma_db")
    )
    VECTOR_COLLECTION_NAME: str = os.getenv("VECTOR_COLLECTION_NAME", "supplier_history")
    
    # ERP mock data path
    ERP_DATA_PATH: str = os.getenv(
        "ERP_DATA_PATH",
        str(Path(__file__).parent.parent / "data" / "erp_mock.json")
    )
    
    # Risk thresholds
    HIGH_RISK_THRESHOLD: float = float(os.getenv("HIGH_RISK_THRESHOLD", "0.7"))
    MEDIUM_RISK_THRESHOLD: float = float(os.getenv("MEDIUM_RISK_THRESHOLD", "0.4"))
    
    # Processing settings
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))


# Singleton settings instance
settings = Settings()
