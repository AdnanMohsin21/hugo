"""
Hugo - Inbox Watchdog Agent
Data models and schemas

Pydantic models for type-safe data handling across all services.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class ChangeType(str, Enum):
    """Types of delivery changes detected in supplier emails."""
    DELAY = "delay"
    EARLY = "early"
    QUANTITY_CHANGE = "quantity_change"
    CANCELLATION = "cancellation"
    PARTIAL_SHIPMENT = "partial_shipment"
    RESCHEDULED = "rescheduled"
    OTHER = "other"


class RiskLevel(str, Enum):
    """Risk severity levels for operational impact."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UrgencyLevel(str, Enum):
    """Urgency levels extracted from email signals."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CommitmentConfidence(str, Enum):
    """Confidence levels for supplier commitments."""
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class SupplierSentiment(str, Enum):
    """Supplier sentiment extracted from email."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Email(BaseModel):
    """Email message model."""
    message_id: str
    thread_id: str
    sender: str
    sender_name: Optional[str] = None
    subject: str
    body: str
    received_at: datetime
    labels: list[str] = Field(default_factory=list)


class Signal(BaseModel):
    """Semantic signals extracted from email."""
    delay_mentioned: bool = False
    quantity_change_mentioned: bool = False
    eta_changed: bool = False
    urgency_level: UrgencyLevel = UrgencyLevel.LOW
    commitment_confidence: CommitmentConfidence = CommitmentConfidence.MEDIUM
    supplier_sentiment: SupplierSentiment = SupplierSentiment.NEUTRAL
    ambiguity_detected: bool = False


class DeliveryChange(BaseModel):
    """Delivery change detected from email."""
    detected: bool = False
    change_type: Optional[ChangeType] = None
    original_date: Optional[datetime] = None
    new_date: Optional[datetime] = None
    delay_days: Optional[int] = None
    affected_items: list[str] = Field(default_factory=list)
    quantity_change: Optional[int] = None
    supplier_reason: Optional[str] = None
    po_reference: Optional[str] = None
    confidence: float = 0.0
    raw_extract: Optional[str] = None


class PurchaseOrder(BaseModel):
    """Purchase order model."""
    po_number: str
    supplier_name: str
    supplier_id: str
    material_id: str
    quantity: int
    expected_delivery: Optional[datetime] = None
    priority: str = "normal"
    total_value: float = 0.0


class HistoricalContext(BaseModel):
    """Historical context for supplier."""
    supplier_id: str
    supplier_name: str
    total_past_issues: int
    supplier_reliability_score: float
    avg_resolution_time_days: float


class RiskAssessment(BaseModel):
    """Risk assessment result."""
    risk_level: RiskLevel
    risk_score: float
    impact_summary: str
    affected_operations: list[str]
    recommended_actions: list[str]
    urgency_hours: Optional[int] = None
    financial_impact_estimate: Optional[float] = None
    reasoning: str


class AlertResult(BaseModel):
    """Alert generation result."""
    email: Email
    delivery_change: DeliveryChange
    matched_po: Optional[PurchaseOrder] = None
    historical_context: Optional[HistoricalContext] = None
    risk_assessment: Optional[RiskAssessment] = None
    alert_source: str = "unknown"
    processed_at: datetime
