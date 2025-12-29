
"""
Hugo - Inbox Watchdog Agent
Main Orchestrator

HYBRID ARCHITECTURE: LLMs are constrained to semantic understanding only. All decisions are deterministic.

Entry point that ties all modules together into a complete pipeline.
Designed for Streamlit-compatible async operation.
"""

import asyncio
import os
import requests
import re
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
from services.huggingface_llm import HuggingFaceLLM
from utils.helpers import setup_logging
from enum import Enum

logger = setup_logging()


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def check_llm_provider_status() -> dict:
    """
    Check LLM provider configuration and availability.
    
    Returns:
        dict with 'provider', 'available', and 'model' keys
    """
    # Use Hugging Face as the LLM provider
    hf_token = os.environ.get("HF_TOKEN")
    model = "google/flan-t5-large"
    
    available = hf_token is not None and hf_token != ""
    
    logger.info(f"LLM Provider: Hugging Face (model: {model}, available: {available})")
    
    return {
        "provider": "huggingface",
        "available": available,
        "model": model
    }


def extract_valid_po_reference(subject: str, body: str) -> Optional[str]:
    """
    Extract valid PO reference using strict regex pattern.
    
    Args:
        subject: Email subject
        body: Email body
        
    Returns:
        PO reference if valid, None otherwise
    """
    po_pattern = r'PO-\d{4}-\d{5}'
    
    # Search subject first (higher priority)
    subject_match = re.search(po_pattern, subject, re.IGNORECASE)
    if subject_match:
        return subject_match.group(0).upper()
    
    # Search body
    body_match = re.search(po_pattern, body, re.IGNORECASE)
    if body_match:
        return body_match.group(0).upper()
    
    return None


def is_holiday_or_marketing_email(subject: str, body: str, sender: str) -> bool:
    """
    Filter out holiday, newsletter, and marketing emails.
    
    Args:
        subject: Email subject
        body: Email body
        sender: Sender email
        
    Returns:
        True if holiday/marketing email, False otherwise
    """
    subject_lower = subject.lower()
    body_lower = body.lower()
    sender_lower = sender.lower()
    
    # Holiday and marketing keywords
    marketing_keywords = [
        'holiday', 'christmas', 'new year', 'thanksgiving', 'newsletter',
        'promotion', 'sale', 'discount', 'offer', 'marketing',
        'unsubscribe', 'campaign', 'greetings', 'seasonal'
    ]
    
    # Check for marketing keywords in subject or body
    for keyword in marketing_keywords:
        if keyword in subject_lower or keyword in body_lower:
            return True
    
    # Check for common marketing sender patterns
    marketing_patterns = [
        r'.*@marketing\.',
        r'.*@newsletter\.',
        r'.*@promo\.',
        r'.*@campaign\.',
        r'noreply@',
        r'donotreply@'
    ]
    
    for pattern in marketing_patterns:
        if re.search(pattern, sender_lower):
            return True
    
    return False


def should_generate_alert(change: DeliveryChange, po_reference: Optional[str], unmapped: bool = False) -> bool:
    """
    Determine if an alert should be generated based on delivery change.
    
    CRITICAL: Alert MUST be generated ONLY if valid PO reference exists.
    
    Args:
        change: DeliveryChange object
        po_reference: Valid PO reference or None
        unmapped: Whether the supplier is not in ERP
        
    Returns:
        True if alert should be generated
    """
    # CRITICAL: No valid PO → no alert
    if not po_reference:
        return False
    
    # At least one signal must be true
    if not change.detected:
        return False
    
    # For unmapped suppliers, only generate if signal detected
    if unmapped and change.detected:
        return True
    
    # For mapped suppliers, check alert conditions
    if change.delay_days is not None and change.delay_days > 0:
        return True
    
    if change.quantity_change is not None and change.quantity_change < 0:
        return True
    
    if change.confidence >= 0.6:
        return True
        
    if change.detected:
        return True
    
    return False


def calculate_risk_score(change: DeliveryChange, unmapped: bool = False) -> float:
    """
    Calculate risk score deterministically (0-1).
    
    Args:
        change: DeliveryChange object
        unmapped: Whether supplier is not in ERP
        
    Returns:
        Risk score between 0.0 and 1.0
    """
    base_score = 0.0
    
    # Signal-based risk factors
    if change.delay_days and change.delay_days > 0:
        if change.delay_days >= 7:
            base_score += 0.4
        elif change.delay_days >= 3:
            base_score += 0.3
        else:
            base_score += 0.2
    
    if change.quantity_change and change.quantity_change < 0:
        abs_change = abs(change.quantity_change)
        if abs_change >= 20:
            base_score += 0.3
        elif abs_change >= 10:
            base_score += 0.2
        else:
            base_score += 0.1
    
    # Confidence factor
    if change.confidence >= 0.8:
        base_score += 0.2
    elif change.confidence >= 0.6:
        base_score += 0.1
    
    # Unmapped supplier penalty (but cap at MEDIUM)
    if unmapped:
        base_score += 0.1
    
    # Normalize to 0.0-1.0 range
    return min(max(base_score, 0.0), 1.0)


def get_alert_severity(change: DeliveryChange, unmapped: bool = False) -> AlertSeverity:
    """
    Determine alert severity level based on risk score.
    
    Severity rules:
    - INFO if unmapped supplier (never escalate)
    - CRITICAL if risk_score >= 0.7
    - MEDIUM if risk_score >= 0.4
    - INFO otherwise
    """
    # CRITICAL: Unmapped suppliers never exceed INFO
    if unmapped:
        return AlertSeverity.INFO
    
    risk_score = calculate_risk_score(change, unmapped)
    
    if risk_score >= 0.7:
        return AlertSeverity.CRITICAL
    elif risk_score >= 0.4:
        return AlertSeverity.MEDIUM
    else:
        return AlertSeverity.INFO



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
        
        # Metrics tracking
        metrics = {
            "emails_processed": 0,
            "relevant_emails": 0,
            "signals_detected": 0,
            "alerts_generated": 0,
            "false_positives_prevented": 0,
            "high_risk_alerts": 0
        }
        
        # Step 1: Fetch emails
        emails = self.email_service.fetch_emails(query=query, max_results=max_emails)
        logger.info(f"Fetched {len(emails)} emails")
        
        if not emails:
            self._print_metrics_summary(metrics)
            return alerts
        
        # Step 2-6: Process each email
        for email in emails:
            metrics["emails_processed"] += 1
            
            # Step 2: Filter out holiday/marketing emails
            if is_holiday_or_marketing_email(email.subject, email.body, email.sender):
                logger.debug(f"Filtered marketing email: {email.subject[:40]}...")
                metrics["false_positives_prevented"] += 1
                continue
            
            # Step 3: Extract valid PO reference
            po_reference = extract_valid_po_reference(email.subject, email.body)
            if not po_reference:
                logger.debug(f"No valid PO reference found: {email.subject[:40]}...")
                metrics["false_positives_prevented"] += 1
                continue
            
            metrics["relevant_emails"] += 1
            
            # Step 4: Process email for delivery changes
            alert = self._process_single_email(email, po_reference)
            
            if alert:
                change = alert.delivery_change
                
                if change.detected:
                    metrics["signals_detected"] += 1
                
                # Step 5: Check if alert should be generated (with PO validation)
                is_unmapped = alert.alert_source == "unmapped_supplier"
                if should_generate_alert(change, po_reference, unmapped=is_unmapped):
                    alerts.append(alert)
                    metrics["alerts_generated"] += 1
                    
                    # Track high-risk alerts
                    severity = get_alert_severity(change, unmapped=is_unmapped)
                    if severity == AlertSeverity.CRITICAL:
                        metrics["high_risk_alerts"] += 1
                else:
                    # Alert was gated out
                    metrics["false_positives_prevented"] += 1
                    logger.debug(f"Alert gated: {email.subject[:40]}...")
        
        logger.info(f"Generated {len(alerts)} alerts from {len(emails)} emails")
        self._print_metrics_summary(metrics)
        return alerts
    
    def _print_metrics_summary(self, metrics: dict) -> None:
        """
        Print a clean metrics summary at the end of execution.
        
        Args:
            metrics: Dictionary with metrics data
        """
        print("\n" + "="*60)
        print("PROCESSING METRICS SUMMARY")
        print("="*60)
        print(f"Emails Processed:        {metrics['emails_processed']}")
        print(f"Relevant Emails:         {metrics['relevant_emails']}")
        print(f"Signals Detected:        {metrics['signals_detected']}")
        print(f"Alerts Generated:        {metrics['alerts_generated']}")
        print(f"False Positives Prevented:{metrics['false_positives_prevented']}")
        print(f"High-Risk Alerts:         {metrics['high_risk_alerts']}")
        
        if metrics['alerts_generated'] > 0:
            high_risk_pct = (metrics['high_risk_alerts'] / metrics['alerts_generated']) * 100
            print(f"High-Risk Percentage:     {high_risk_pct:.1f}%")
        
        if metrics['relevant_emails'] > 0:
            alert_rate = (metrics['alerts_generated'] / metrics['relevant_emails']) * 100
            print(f"Alert Generation Rate:   {alert_rate:.1f}%")
        
        print("="*60 + "\n")
    
    def _process_single_email(self, email: Email, po_reference: Optional[str] = None) -> Optional[AlertResult]:
        """
        Process a single email through the full pipeline using hybrid architecture.
        
        LLMs are constrained to semantic understanding only. All decisions are deterministic.
        
        Args:
            email: Email to process
            po_reference: Valid PO reference (already validated)
        
        Returns:
            AlertResult or None
        """
        try:
            # Step 1: Match to PO first (for RAG context and guardrail)
            # Create a temporary change for matching
            temp_change = DeliveryChange(detected=True, confidence=0.5)
            po = self.erp.match_delivery_change(temp_change, email.sender)
            
            alert_source = "mapped_po"
            is_unmapped = False
            
            if not po:
                logger.info(f"Unmapped supplier — severity downgraded: {email.sender}")
                alert_source = "unmapped_supplier"
                is_unmapped = True
            
            # Step 2: Get historical context (for RAG)
            context = self.vector_store.build_context(temp_change, po)
            
            # Step 3: Build RAG context
            rag_context_parts = []
            if po:
                rag_context_parts.append(f"PO: {po.po_number}, Supplier: {po.supplier_name}, Priority: {po.priority}")
            if context:
                rag_context_parts.append(f"Reliability: {context.supplier_reliability_score:.2f}, Past Issues: {context.total_past_issues}")
            rag_context = "\n".join(rag_context_parts) if rag_context_parts else None
            
            # Step 4: Detect delivery changes (extracts signals + calculates values)
            change, signal = self.detector.detect_changes(email, po, rag_context)
            
            # Step 5: Check if alert should be generated (with PO validation)
            if not should_generate_alert(change, po_reference, unmapped=is_unmapped):
                logger.debug(f"Alert creation rules not met: {email.subject[:40]}...")
                return AlertResult(
                    email=email,
                    delivery_change=change,
                    processed_at=datetime.utcnow()
                )
            
            # Step 6: Determine alert severity (deterministic Python logic)
            severity = get_alert_severity(change, unmapped=is_unmapped)
            logger.info(f"Change detected: {change.change_type.value if change.change_type else 'unknown'} (severity: {severity.value})")
            
            if po:
                logger.info(f"Matched to PO: {po.po_number}")
            
            if context:
                logger.info(f"Retrieved context: {context.total_past_issues} past issues")
            
            # Step 7: Assess risk (computes risk_score deterministically)
            risk = self.risk_engine.assess_risk(change, po, context, email.body, signal)
            logger.info(f"Risk assessment: {risk.risk_level.value} ({risk.risk_score:.2f})")
            
            # Step 8: Build alert
            return AlertResult(
                email=email,
                delivery_change=change,
                matched_po=po,
                historical_context=context,
                risk_assessment=risk,
                alert_source=alert_source,
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
    print("HUGO - Inbox Watchdog Agent Demo")
    print("="*60 + "\n")
    
    # Initialize agent
    agent = HugoAgent()
    
    # Process emails (uses mock data without Gmail credentials)
    print("Fetching and processing supplier emails...\n")
    alerts = agent.process_emails(max_emails=5)
    
    # Display results
    for i, alert in enumerate(alerts, 1):
        print(f"\n{'─'*50}")
        print(f"Alert #{i}")
        print(f"{'─'*50}")
        print(f"From: {alert.email.sender_name or alert.email.sender}")
        print(f"Subject: {alert.email.subject}")
        
        if alert.delivery_change.detected:
            change = alert.delivery_change
            print(f"\nChange Detected: {change.change_type.value if change.change_type else 'Unknown'}")
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
                print(f"\nRisk Assessment: {risk.risk_level.value.upper()}")
                print(f"   Score: {risk.risk_score:.0%}")
                print(f"   Impact: {risk.impact_summary}")
                if risk.recommended_actions:
                    print(f"\n   Recommended Actions:")
                    for action in risk.recommended_actions[:3]:
                        print(f"   • {action}")
    
    print(f"\n{'='*60}")
    print(f"Processed {len(alerts)} alerts")
    print("="*60 + "\n")
    
    return alerts


# Entry point
if __name__ == "__main__":
    run_demo()
# >>>>>>> 8a0f741faa9c44c846dccccadea8ded47d968233
