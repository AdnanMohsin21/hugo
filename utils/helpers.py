"""
Hugo - Inbox Watchdog Agent
Utility helpers

Common utility functions for date parsing, text cleaning, and logging.
"""

import re
import logging
from datetime import datetime
from typing import Optional
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure and return a logger for Hugo agent.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("hugo")
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


def parse_date(date_string: str) -> Optional[datetime]:
    """
    Parse various date formats from supplier emails.
    
    Handles formats like:
    - "December 15, 2024"
    - "15/12/2024"
    - "2024-12-15"
    - "next Monday"
    - "in 3 days"
    
    Args:
        date_string: Raw date string from email
    
    Returns:
        Parsed datetime or None if parsing fails
    """
    if not date_string or not isinstance(date_string, str):
        return None
    
    date_string = date_string.strip()
    
    # Handle relative dates
    relative_patterns = {
        r"in (\d+) days?": lambda m: datetime.now() + relativedelta(days=int(m.group(1))),
        r"in (\d+) weeks?": lambda m: datetime.now() + relativedelta(weeks=int(m.group(1))),
        r"next week": lambda m: datetime.now() + relativedelta(weeks=1),
        r"tomorrow": lambda m: datetime.now() + relativedelta(days=1),
    }
    
    for pattern, handler in relative_patterns.items():
        match = re.search(pattern, date_string.lower())
        if match:
            return handler(match)
    
    # Try standard date parsing
    try:
        return date_parser.parse(date_string, fuzzy=True)
    except (ValueError, TypeError):
        return None


def clean_text(text: str) -> str:
    """
    Clean and normalize email text for processing.
    
    - Removes excessive whitespace
    - Strips HTML remnants
    - Normalizes line breaks
    - Removes signatures and disclaimers (basic)
    
    Args:
        text: Raw email text
    
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove common HTML entities
    html_entities = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
    }
    for entity, char in html_entities.items():
        text = text.replace(entity, char)
    
    # Remove any remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    
    # Remove common email signatures (basic detection)
    signature_markers = [
        r"^--\s*$",
        r"^Best regards,",
        r"^Sincerely,",
        r"^Thanks,",
        r"^Sent from my",
        r"^This email and any attachments",
        r"^CONFIDENTIAL",
    ]
    
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if any(re.match(marker, line.strip(), re.IGNORECASE) for marker in signature_markers):
            break
        cleaned_lines.append(line)
    
    text = "\n".join(cleaned_lines)
    
    return text.strip()


def extract_po_numbers(text: str) -> list[str]:
    """
    Extract purchase order numbers from text.
    
    Looks for patterns like:
    - PO#12345
    - PO-2024-0001
    - Purchase Order 12345
    - Order #ABC-123
    
    Args:
        text: Text to search
    
    Returns:
        List of found PO numbers
    """
    patterns = [
        r"PO[#\-\s]?(\d{4,})",
        r"PO[#\-\s]?([A-Z0-9\-]{5,})",
        r"Purchase\s+Order[#:\s]+(\d{4,})",
        r"Order[#:\s]+([A-Z0-9\-]{5,})",
    ]
    
    found = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.update(matches)
    
    return list(found)


def calculate_delay_days(original: datetime, new: datetime) -> int:
    """
    Calculate the number of days between two dates.
    
    Args:
        original: Original delivery date
        new: New delivery date
    
    Returns:
        Days of delay (positive) or early (negative)
    """
    delta = new - original
    return delta.days


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format a currency amount for display.
    
    Args:
        amount: Numeric amount
        currency: Currency code
    
    Returns:
        Formatted string like "$1,234.56"
    """
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"
