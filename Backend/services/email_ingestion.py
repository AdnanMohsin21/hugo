"""
Hugo - Inbox Watchdog Agent
Email Ingestion Service

Fetches and parses supplier emails via Gmail API.
"""

import base64
from datetime import datetime
from typing import Optional
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import html2text

from config.settings import settings
from models.schemas import Email
from utils.helpers import clean_text, setup_logging

logger = setup_logging()


class EmailIngestionService:
    """
    Service for fetching and parsing emails from Gmail.
    
    Handles OAuth authentication, email fetching, and body parsing.
    Designed to work with supplier inbox labels.
    """
    
    def __init__(self):
        """Initialize Gmail service with authentication."""
        self.service = None
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self._authenticate()
    
    def _authenticate(self) -> None:
        """
        Authenticate with Gmail API using OAuth2.
        
        Uses stored token if available, otherwise initiates OAuth flow.
        """
        creds = None
        
        # Load existing token
        try:
            import json
            from pathlib import Path
            token_path = Path(settings.GMAIL_TOKEN_PATH)
            if token_path.exists():
                with open(token_path, "r") as f:
                    token_data = json.load(f)
                    creds = Credentials.from_authorized_user_info(token_data, settings.GMAIL_SCOPES)
        except Exception as e:
            logger.warning(f"Could not load token: {e}")
        
        # Refresh or get new credentials
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        
        if not creds or not creds.valid:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.GMAIL_CREDENTIALS_PATH, 
                    settings.GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
                
                # Save token for future use
                import json
                with open(settings.GMAIL_TOKEN_PATH, "w") as f:
                    f.write(creds.to_json())
            except Exception as e:
                logger.error(f"Gmail authentication failed: {e}")
                logger.info("Running in mock mode - no Gmail access")
                return
        
        # Build Gmail service
        self.service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail service initialized successfully")
    
    def fetch_emails(
        self, 
        query: Optional[str] = None,
        max_results: Optional[int] = None,
        label: Optional[str] = None
    ) -> list[Email]:
        """
        Fetch emails from Gmail inbox.
        
        Args:
            query: Gmail search query (e.g., "from:supplier@example.com")
            max_results: Maximum number of emails to fetch
            label: Gmail label to filter by
        
        Returns:
            List of parsed Email objects
        """
        if not self.service:
            logger.warning("Gmail service not available, returning mock data")
            return self._get_mock_emails()
        
        max_results = max_results or settings.MAX_EMAILS_PER_FETCH
        label = label or settings.SUPPLIER_LABEL
        
        try:
            # Build query with label
            full_query = f"label:{label}"
            if query:
                full_query = f"{full_query} {query}"
            
            # Fetch message list
            results = self.service.users().messages().list(
                userId="me",
                q=full_query,
                maxResults=max_results
            ).execute()
            
            messages = results.get("messages", [])
            logger.info(f"Found {len(messages)} emails matching query")
            
            # Fetch full message content
            emails = []
            for msg in messages:
                email = self._parse_message(msg["id"])
                if email:
                    emails.append(email)
            
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return []
    
    def _parse_message(self, message_id: str) -> Optional[Email]:
        """
        Parse a Gmail message into Email model.
        
        Args:
            message_id: Gmail message ID
        
        Returns:
            Parsed Email object or None
        """
        try:
            msg = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()
            
            headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
            
            # Extract sender info
            sender_full = headers.get("from", "")
            sender_email = sender_full
            sender_name = None
            if "<" in sender_full:
                parts = sender_full.split("<")
                sender_name = parts[0].strip().strip('"')
                sender_email = parts[1].rstrip(">")
            
            # Parse date
            date_str = headers.get("date", "")
            try:
                received_at = parsedate_to_datetime(date_str)
            except Exception:
                received_at = datetime.utcnow()
            
            # Extract body
            body = self._extract_body(msg["payload"])
            
            # Get labels
            labels = msg.get("labelIds", [])
            
            return Email(
                message_id=msg["id"],
                thread_id=msg["threadId"],
                sender=sender_email,
                sender_name=sender_name,
                subject=headers.get("subject", "(No Subject)"),
                body=clean_text(body),
                received_at=received_at,
                labels=labels
            )
            
        except Exception as e:
            logger.error(f"Error parsing message {message_id}: {e}")
            return None
    
    def _extract_body(self, payload: dict) -> str:
        """
        Extract plain text body from message payload.
        
        Handles multipart messages and HTML conversion.
        """
        body = ""
        
        if "body" in payload and payload["body"].get("data"):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        
        elif "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                
                if mime_type == "text/plain":
                    if part["body"].get("data"):
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                        break
                
                elif mime_type == "text/html":
                    if part["body"].get("data"):
                        html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                        body = self.html_converter.handle(html)
                
                elif "parts" in part:
                    body = self._extract_body(part)
                    if body:
                        break
        
        return body
    
    def _get_mock_emails(self) -> list[Email]:
        """
        Return mock emails for testing without Gmail access.
        """
        return [
            Email(
                message_id="mock_001",
                thread_id="thread_001",
                sender="logistics@acme-supplies.com",
                sender_name="ACME Logistics Team",
                subject="RE: PO-2024-0892 - Delivery Update",
                body="""Hi Team,

We need to inform you about a delay in your recent order PO-2024-0892.

Due to unexpected supply chain disruptions at our manufacturing facility, 
the delivery originally scheduled for January 5, 2025 will now be 
delayed by approximately 7 days to January 12, 2025.

Affected items:
- Widget A (SKU: WDG-A100) - 500 units
- Widget B (SKU: WDG-B200) - 250 units

We apologize for any inconvenience this may cause and are working 
to expedite the shipment where possible.

Best regards,
ACME Logistics Team""",
                received_at=datetime.utcnow(),
                labels=["INBOX", "Suppliers"]
            ),
            Email(
                message_id="mock_002",
                thread_id="thread_002",
                sender="shipping@globalparts.io",
                sender_name="Global Parts Shipping",
                subject="Shipment Notification - Order #GP-78234",
                body="""Dear Customer,

Good news! Your order #GP-78234 is shipping earlier than expected.

Original delivery date: January 15, 2025
New delivery date: January 10, 2025

Your shipment contains:
- Industrial Bearings (x100)
- Precision Gears (x50)

Tracking number: 1Z999AA10123456784

Thank you for your business!

Global Parts Team""",
                received_at=datetime.utcnow(),
                labels=["INBOX", "Suppliers"]
            ),
            Email(
                message_id="mock_003",
                thread_id="thread_003",
                sender="orders@techcomponents.com",
                sender_name="Tech Components",
                subject="URGENT: Partial Shipment Notice - PO#TC-2024-445",
                body="""IMPORTANT NOTICE

Reference: PO#TC-2024-445

We regret to inform you that we can only fulfill a partial shipment 
of your order due to component shortage.

Original Order:
- Microcontroller Units: 1000 pcs
- Sensor Modules: 500 pcs

What we can ship now:
- Microcontroller Units: 600 pcs (60%)
- Sensor Modules: 500 pcs (100%)

The remaining 400 Microcontroller Units will be shipped in 
approximately 3 weeks (estimated: February 1, 2025).

Please confirm if you want us to proceed with the partial shipment.

Regards,
Tech Components Order Desk""",
                received_at=datetime.utcnow(),
                labels=["INBOX", "Suppliers", "IMPORTANT"]
            )
        ]
