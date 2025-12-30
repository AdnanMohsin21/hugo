"""
Hugo - Inbox Watchdog Agent
Utility helpers

Common utility functions for date parsing, text cleaning, and logging.
"""

import re
import logging
from datetime import datetime
from typing import Optional


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
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(getattr(logging, level.upper()))
    return logger


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Raw text content
    
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\-\.,\!?;:]', '', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def parse_date_flexible(date_str: str) -> Optional[datetime]:
    """
    Parse date string in various formats.
    
    Args:
        date_str: Date string to parse
    
    Returns:
        Parsed datetime or None
    """
    if not date_str:
        return None
    
    # Common date formats
    formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y-%m-%d %H:%M:%S',
        '%m/%d/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M:%S'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def extract_po_reference(text: str) -> Optional[str]:
    """
    Extract PO reference from text.
    
    Args:
        text: Text to search for PO reference
    
    Returns:
        PO reference or None
    """
    # Common PO patterns
    patterns = [
        r'PO[#:\s]*([A-Z0-9\-]+)',
        r'Purchase Order[:\s]*([A-Z0-9\-]+)',
        r'Order[:\s]*([A-Z0-9\-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    return None
