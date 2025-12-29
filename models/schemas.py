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
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Signal(BaseModel):
    """
    Semantic signals extracted from supplier emails by LLM.
    
    LLMs are constrained to semantic understanding only. All decisions are deterministic.
    This schema contains ONLY semantic signals - no numbers, no calculations, no decisions.
    """
    delay_mentioned: bool = Field(False, description="Whether delay is mentioned in email")
    quantity_change_mentioned: bool = Field(False, description="Whether quantity change is mentioned")
    eta_changed: bool = Field(False, description="Whether ETA/delivery date changed")
    urgency_level: UrgencyLevel = Field(UrgencyLevel.LOW, description="Perceived urgency level")
    commitment_confidence: CommitmentConfidence = Field(CommitmentConfidence.MEDIUM, description="Confidence in supplier commitment")
    supplier_sentiment: SupplierSentiment = Field(SupplierSentiment.NEUTRAL, description="Supplier sentiment")
    ambiguity_detected: bool = Field(False, description="Whether ambiguity or uncertainty detected")


class Email(BaseModel):
    """Parsed email from supplier inbox."""
    
    message_id: str = Field(..., description="Unique Gmail message ID")
    thread_id: str = Field(..., description="Gmail thread ID for conversation tracking")
    sender: str = Field(..., description="Sender email address")
    sender_name: Optional[str] = Field(None, description="Sender display name")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Plain text email body")
    received_at: datetime = Field(..., description="Email receipt timestamp")
    labels: list[str] = Field(default_factory=list, description="Gmail labels")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DeliveryChange(BaseModel):
    """Extracted delivery change information from email."""
    
    detected: bool = Field(..., description="Whether a delivery change was detected")
    change_type: Optional[ChangeType] = Field(None, description="Type of delivery change")
    original_date: Optional[datetime] = Field(None, description="Original delivery date")
    new_date: Optional[datetime] = Field(None, description="New delivery date if changed")
    delay_days: Optional[int] = Field(None, description="Number of days delayed (negative for early)")
    affected_items: list[str] = Field(default_factory=list, description="Items/SKUs affected")
    quantity_change: Optional[int] = Field(None, description="Quantity change if applicable")
    supplier_reason: Optional[str] = Field(None, description="Reason provided by supplier")
    po_reference: Optional[str] = Field(None, description="Referenced PO number if mentioned")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Detection confidence score")
    raw_extract: str = Field("", description="Raw extracted text from LLM")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class PurchaseOrder(BaseModel):
    """Purchase order from ERP system."""
    
    po_number: str = Field(..., description="Purchase order number")
    supplier_id: str = Field(..., description="Supplier identifier")
    supplier_name: str = Field(..., description="Supplier company name")
    supplier_email: str = Field(..., description="Supplier contact email")
    order_date: datetime = Field(..., description="Date order was placed")
    expected_delivery: datetime = Field(..., description="Expected delivery date")
    items: list[dict] = Field(default_factory=list, description="Line items with SKU, qty, description")
    total_value: float = Field(0.0, description="Total order value")
    currency: str = Field("USD", description="Currency code")
    status: str = Field("open", description="PO status: open, partial, complete, cancelled")
    priority: str = Field("normal", description="Priority: low, normal, high, critical")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class HistoricalContext(BaseModel):
    """Retrieved historical context from vector store."""
    
    similar_incidents: list[dict] = Field(default_factory=list, description="Past similar delivery issues")
    supplier_reliability_score: float = Field(0.5, ge=0.0, le=1.0, description="Historical reliability")
    avg_delay_days: float = Field(0.0, description="Average delay in days for this supplier")
    total_past_issues: int = Field(0, description="Total number of past delivery issues")
    resolution_patterns: list[str] = Field(default_factory=list, description="How past issues were resolved")


class RiskAssessment(BaseModel):
    """Operational risk assessment output."""
    
    risk_level: RiskLevel = Field(..., description="Overall risk level")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Numerical risk score")
    impact_summary: str = Field(..., description="Summary of potential business impact")
    affected_operations: list[str] = Field(default_factory=list, description="Operations that may be impacted")
    recommended_actions: list[str] = Field(default_factory=list, description="Suggested mitigation actions")
    urgency_hours: Optional[int] = Field(None, description="Hours until action needed")
    financial_impact_estimate: Optional[float] = Field(None, description="Estimated financial impact")
    reasoning: str = Field("", description="LLM reasoning explanation")


class AlertResult(BaseModel):
    """Complete alert result combining all analysis."""
    
    email: Email = Field(..., description="Source email")
    delivery_change: DeliveryChange = Field(..., description="Detected change")
    matched_po: Optional[PurchaseOrder] = Field(None, description="Matched purchase order")
    historical_context: Optional[HistoricalContext] = Field(None, description="Retrieved context")
    risk_assessment: Optional[RiskAssessment] = Field(None, description="Risk analysis")
    alert_source: str = Field("default", description="Source of the alert (e.g., mapped_po, unmapped_supplier)")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
