"""
Hugo - Inbox Watchdog Agent
Main Orchestrator

Entry point that ties all modules together into a complete pipeline.
Designed for Streamlit-compatible async operation.
"""

import asyncio
import os
import requests
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from config.settings import settings
from models.schemas import Email, DeliveryChange, PurchaseOrder, AlertResult
from services.email_ingestion import EmailIngestionService
from services.delivery_detector import DeliveryDetector
from services.erp_matcher import ERPMatcher
from services.vector_store import VectorStore
from services.risk_engine import RiskEngine
from services.ollama_llm import check_ollama_status
from utils.helpers import setup_logging

logger = setup_logging()


def check_llm_provider_status() -> dict:
    """
    Check LLM provider configuration and availability.
    
    Returns:
        dict with 'provider', 'available', and 'model' keys
    """
    # Force Ollama as the only LLM provider
    ollama_model = os.environ.get("OLLAMA_MODEL", "gemma:2b")
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    
    logger.info(f"LLM Provider: Ollama (model: {ollama_model}, url: {ollama_url})")
    available = check_ollama_status(ollama_url)
    
    return {
        "provider": "ollama",
        "available": available,
        "model": ollama_model
    }



class HugoAgent:
    """
    Hugo - Inbox Watchdog Agent
    
    Monitors supplier emails for delivery changes, matches with POs,
    retrieves historical context, and assesses operational risk.
    
    Pipeline:
    1. Fetch emails from supplier inbox
    2. Detect delivery changes using LLM
    3. Match changes to purchase orders
    4. Retrieve historical context via vector search
    5. Assess operational risk
    6. Return actionable alerts
    """
    
    def __init__(self):
        """Initialize all Hugo services."""
        logger.info("Initializing Hugo Agent...")
        
        # Check LLM provider availability at startup
        self.llm_provider = check_llm_provider_status()
        
        self.email_service = EmailIngestionService()
        self.detector = DeliveryDetector()
        self.erp = ERPMatcher()
        self.vector_store = VectorStore()
        self.risk_engine = RiskEngine()
        
        logger.info("Hugo Agent ready")
    
    def process_emails(
        self,
        query: Optional[str] = None,
        max_emails: int = 10
    ) -> list[AlertResult]:
        """
        Main processing pipeline - synchronous version.
        
        Args:
            query: Optional Gmail search query
            max_emails: Maximum emails to process
        
        Returns:
            List of AlertResult for emails with detected changes
        """
        logger.info(f"Starting email processing (max: {max_emails})")
        alerts = []
        
        # Step 1: Fetch emails
        emails = self.email_service.fetch_emails(query=query, max_results=max_emails)
        logger.info(f"Fetched {len(emails)} emails")
        
        if not emails:
            return alerts
        
        # Step 2-6: Process each email
        for email in emails:
            alert = self._process_single_email(email)
            if alert and alert.delivery_change.detected:
                alerts.append(alert)
        
        logger.info(f"Generated {len(alerts)} alerts from {len(emails)} emails")
        return alerts
    
    def _process_single_email(self, email: Email) -> Optional[AlertResult]:
        """
        Process a single email through the full pipeline.
        
        Args:
            email: Email to process
        
        Returns:
            AlertResult or None
        """
        try:
            # Step 2: Detect delivery changes
            change = self.detector.detect_changes(email)
            
            if not change.detected:
                logger.debug(f"No change detected in: {email.subject[:40]}...")
                return AlertResult(
                    email=email,
                    delivery_change=change,
                    processed_at=datetime.utcnow()
                )
            
            logger.info(f"Change detected: {change.change_type.value if change.change_type else 'unknown'}")
            
            # Step 3: Match to PO
            po = self.erp.match_delivery_change(change, email.sender)
            if po:
                logger.info(f"Matched to PO: {po.po_number}")
            
            # Step 4: Get historical context
            context = self.vector_store.build_context(change, po)
            logger.info(f"Retrieved context: {context.total_past_issues} past issues")
            
            # Step 5: Assess risk
            risk = self.risk_engine.assess_risk(change, po, context, email.body)
            logger.info(f"Risk assessment: {risk.risk_level.value} ({risk.risk_score:.2f})")
            
            # Step 6: Build alert
            return AlertResult(
                email=email,
                delivery_change=change,
                matched_po=po,
                historical_context=context,
                risk_assessment=risk,
                processed_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error processing email {email.message_id}: {e}")
            return AlertResult(
                email=email,
                delivery_change=DeliveryChange(detected=False, raw_extract=str(e)),
                processed_at=datetime.utcnow()
            )
    
    async def process_emails_async(
        self,
        query: Optional[str] = None,
        max_emails: int = 10
    ) -> list[AlertResult]:
        """
        Async version for Streamlit compatibility.
        
        Runs the synchronous pipeline in a thread pool to avoid blocking.
        """
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool,
                lambda: self.process_emails(query, max_emails)
            )
    
    def process_single_email_from_text(
        self,
        sender: str,
        subject: str,
        body: str
    ) -> AlertResult:
        """
        Process a single email from raw text inputs.
        
        Useful for testing or direct API calls without Gmail.
        
        Args:
            sender: Sender email address
            subject: Email subject
            body: Email body text
        
        Returns:
            AlertResult with analysis
        """
        email = Email(
            message_id=f"manual_{datetime.now().timestamp()}",
            thread_id="manual_thread",
            sender=sender,
            subject=subject,
            body=body,
            received_at=datetime.utcnow(),
            labels=["Manual"]
        )
        
        return self._process_single_email(email)
    
    def get_open_orders(self) -> list[PurchaseOrder]:
        """Get all open purchase orders from ERP."""
        return self.erp.get_all_open_orders()
    
    def get_supplier_history(self, supplier_id: str) -> list[dict]:
        """Get historical incidents for a supplier."""
        return self.vector_store.get_supplier_history(supplier_id)
    
    def search_similar_incidents(self, query: str, n_results: int = 5) -> list[dict]:
        """Search for similar historical incidents."""
        return self.vector_store.query_similar(query, n_results=n_results)
    
    def add_incident_to_history(
        self,
        alert: AlertResult,
        resolution: str = ""
    ) -> None:
        """
        Add a processed alert to historical context for future RAG.
        
        Args:
            alert: Processed alert result
            resolution: How the issue was resolved
        """
        if not alert.delivery_change.detected:
            return
        
        incident_id = f"inc_{alert.email.message_id}_{datetime.now().timestamp()}"
        
        description = f"{alert.delivery_change.change_type.value if alert.delivery_change.change_type else 'Unknown'} "
        description += f"- {alert.delivery_change.supplier_reason or 'No reason provided'}. "
        if alert.delivery_change.delay_days:
            description += f"Delay: {alert.delivery_change.delay_days} days. "
        if alert.matched_po:
            description += f"Affected PO: {alert.matched_po.po_number}."
        
        self.vector_store.add_incident(
            incident_id=incident_id,
            supplier_id=alert.matched_po.supplier_id if alert.matched_po else "UNKNOWN",
            supplier_name=alert.matched_po.supplier_name if alert.matched_po else "Unknown Supplier",
            incident_type=alert.delivery_change.change_type.value if alert.delivery_change.change_type else "other",
            description=description,
            delay_days=alert.delivery_change.delay_days or 0,
            resolution=resolution,
            impact_score=alert.risk_assessment.risk_score if alert.risk_assessment else 0.5
        )
        
        logger.info(f"Added incident {incident_id} to history")


def run_demo():
    """Run a demo of the Hugo agent with mock data."""
    print("\n" + "="*60)
    print("🐕 HUGO - Inbox Watchdog Agent Demo")
    print("="*60 + "\n")
    
    # Initialize agent
    agent = HugoAgent()
    
    # Process emails (uses mock data without Gmail credentials)
    print("📬 Fetching and processing supplier emails...\n")
    alerts = agent.process_emails(max_emails=5)
    
    # Display results
    for i, alert in enumerate(alerts, 1):
        print(f"\n{'─'*50}")
        print(f"📧 Alert #{i}")
        print(f"{'─'*50}")
        print(f"From: {alert.email.sender_name or alert.email.sender}")
        print(f"Subject: {alert.email.subject}")
        
        if alert.delivery_change.detected:
            change = alert.delivery_change
            print(f"\n⚠️  Change Detected: {change.change_type.value if change.change_type else 'Unknown'}")
            if change.delay_days:
                print(f"   Delay: {change.delay_days} days")
            if change.affected_items:
                print(f"   Items: {', '.join(change.affected_items)}")
            if change.po_reference:
                print(f"   PO Ref: {change.po_reference}")
            
            if alert.matched_po:
                po = alert.matched_po
                print(f"\n📦 Matched PO: {po.po_number}")
                print(f"   Supplier: {po.supplier_name}")
                print(f"   Value: ${po.total_value:,.2f}")
                print(f"   Priority: {po.priority.upper()}")
            
            if alert.risk_assessment:
                risk = alert.risk_assessment
                level_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
                print(f"\n🎯 Risk Assessment: {level_emoji.get(risk.risk_level.value, '⚪')} {risk.risk_level.value.upper()}")
                print(f"   Score: {risk.risk_score:.0%}")
                print(f"   Impact: {risk.impact_summary}")
                if risk.recommended_actions:
                    print(f"\n   Recommended Actions:")
                    for action in risk.recommended_actions[:3]:
                        print(f"   • {action}")
    
    print(f"\n{'='*60}")
    print(f"✅ Processed {len(alerts)} alerts")
    print("="*60 + "\n")
    
    return alerts


# Entry point
if __name__ == "__main__":
    run_demo()
