"""
Hugo - Inbox Watchdog Agent
Email Ingestion Service

Fetches and parses supplier emails via Gmail API.
"""

import base64
import os
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
    """
    
    def __init__(self):
        """Initialize email ingestion service."""
        self.service = None
        self._authenticate()
        logger.info("Gmail service initialized successfully")
    
    def _authenticate(self):
        """Handle Gmail OAuth authentication."""
        creds = None
        
        # Load existing token
        if os.path.exists(settings.GMAIL_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(settings.GMAIL_TOKEN_PATH, settings.GMAIL_SCOPES)
        
        # If no valid credentials, let user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(settings.GMAIL_CREDENTIALS_PATH):
                    logger.warning(f"Gmail credentials file not found: {settings.GMAIL_CREDENTIALS_PATH}")
                    # Create mock service for demo
                    self.service = MockGmailService()
                    return
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.GMAIL_CREDENTIALS_PATH, settings.GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials
            with open(settings.GMAIL_TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        
        # Build Gmail service
        self.service = build('gmail', 'v1', credentials=creds)
    
    def fetch_emails(self, query: Optional[str] = None, max_results: int = 10) -> list[Email]:
        """
        Fetch emails from Gmail.
        
        Args:
            query: Gmail search query
            max_results: Maximum number of emails to fetch
        
        Returns:
            List of Email objects
        """
        try:
            # Build query
            if query:
                full_query = query
            else:
                full_query = f"label:{settings.SUPPLIER_LABEL}"
            
            # Get messages
            result = self.service.users().messages().list(
                userId='me',
                q=full_query,
                maxResults=max_results
            ).execute()
            
            messages = result.get('messages', [])
            logger.info(f"Found {len(messages)} emails matching query")
            
            emails = []
            for message in messages:
                email = self._parse_message(message)
                if email:
                    emails.append(email)
            
            return emails
            
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            # Return mock data for demo
            return self._get_mock_emails()
    
    def _parse_message(self, message) -> Optional[Email]:
        """Parse a Gmail message into Email object."""
        try:
            # Get full message
            msg = self.service.users().messages().get(
                userId='me',
                id=message['id'],
                format='full'
            ).execute()
            
            # Extract headers
            headers = msg['payload']['headers']
            subject = ''
            sender = ''
            date = ''
            
            for header in headers:
                if header['name'].lower() == 'subject':
                    subject = header['value']
                elif header['name'].lower() == 'from':
                    sender = header['value']
                elif header['name'].lower() == 'date':
                    date = header['value']
            
            # Parse date
            received_at = parsedate_to_datetime(date) or datetime.now()
            
            # Extract body
            body = self._extract_body(msg['payload'])
            
            # Extract sender name and email
            sender_name = ''
            if '<' in sender:
                sender_name = sender.split('<')[0].strip()
                sender_email = sender.split('<')[1].split('>')[0].strip()
            else:
                sender_name = sender
                sender_email = sender
            
            # Create Email object
            return Email(
                message_id=message['id'],
                thread_id=message.get('threadId', ''),
                sender=sender_email,
                sender_name=sender_name,
                subject=subject,
                body=clean_text(body),
                received_at=received_at,
                labels=[]
            )
            
        except Exception as e:
            logger.error(f"Error parsing message {message['id']}: {e}")
            return None
    
    def _extract_body(self, payload) -> str:
        """Extract email body from message payload."""
        body = ''
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                elif part['mimeType'] == 'text/html':
                    data = part['body']['data']
                    html_body = base64.urlsafe_b64decode(data).decode('utf-8')
                    body = html2text.html2text(html_body)
        else:
            if payload['mimeType'] == 'text/plain':
                data = payload['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
            elif payload['mimeType'] == 'text/html':
                data = payload['body']['data']
                html_body = base64.urlsafe_b64decode(data).decode('utf-8')
                body = html2text.html2text(html_body)
        
        return body
    
    def _get_mock_emails(self) -> list[Email]:
        """Return mock emails for demo purposes."""
        return [
            Email(
                message_id="mock_1",
                thread_id="mock_thread_1",
                sender="supplier@company.com",
                sender_name="Supplier Co",
                subject="Delivery Delay Notice - PO-2024-12345",
                body="We need to delay your shipment by 5 days due to production issues.",
                received_at=datetime.now(),
                labels=["Suppliers"]
            ),
            Email(
                message_id="mock_2",
                thread_id="mock_thread_2",
                sender="logistics@vendor.com",
                sender_name="Logistics Partner",
                subject="Quantity Reduction - PO-2024-67890",
                body="We can only supply 80 units instead of 100 due to material shortage.",
                received_at=datetime.now(),
                labels=["Suppliers"]
            )
        ]


class MockGmailService:
    """Mock Gmail service for demo when credentials are not available."""
    
    def users(self):
        return MockUsersService()


class MockUsersService:
    """Mock users service."""
    
    def messages(self):
        return MockMessagesService()
    
    def list(self, userId, q, maxResults):
        return MockListResult()
    
    def get(self, userId, id, format):
        return MockMessage()


class MockMessagesService:
    """Mock messages service."""
    
    def list(self, userId, q, maxResults):
        return MockListResult()
    
    def get(self, userId, id, format):
        return MockMessage()


class MockListResult:
    """Mock list result."""
    
    def execute(self):
        return {
            'messages': [
                {'id': 'mock_1', 'threadId': 'mock_thread_1'},
                {'id': 'mock_2', 'threadId': 'mock_thread_2'}
            ]
        }


class MockMessage:
    """Mock message."""
    
    def __init__(self):
        self.id = 'mock_1'
        self.threadId = 'mock_thread_1'
        self.payload = {
            'headers': [
                {'name': 'Subject', 'value': 'Mock Subject'},
                {'name': 'From', 'value': 'mock@example.com'},
                {'name': 'Date', 'value': 'Mon, 1 Jan 2024 12:00:00 +0000'}
            ],
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {'data': base64.b64encode(b'Mock email body').decode()}
                }
            ]
        }
