"""
Hugo - Inbox Watchdog Agent
ERP Comparison Service

Deterministic, rule-based comparison of supplier-provided delivery dates
against ERP purchase order records. No LLM involved.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum
from dataclasses import dataclass

import pandas as pd

from utils.helpers import setup_logging

logger = setup_logging()


class ChangeType(str, Enum):
    """Classification of delivery date changes."""
    DELAY = "DELAY"
    EARLY = "EARLY"
    NO_CHANGE = "NO_CHANGE"


@dataclass
class ERPComparison:
    """Result of comparing supplier date with ERP record."""
    order_id: str
    sku: Optional[str]
    erp_delivery_date: Optional[datetime]
    supplier_delivery_date: Optional[datetime]
    delay_days: int
    change_type: ChangeType
    matched: bool
    erp_record: Optional[dict] = None


class ERPComparer:
    """
    Compares supplier-provided delivery information with ERP purchase orders.
    
    Deterministic rule-based logic:
    - Matches by order_id
    - Calculates delay in days
    - Classifies as DELAY, EARLY, or NO_CHANGE
    """
    
    def __init__(self, csv_path: Optional[str] = None):
        """
        Initialize ERP comparer.
        
        Args:
            csv_path: Path to material_orders.csv (or load later)
        """
        self.orders_df: Optional[pd.DataFrame] = None
        self.orders_by_id: dict = {}
        
        if csv_path:
            self.load_orders(csv_path)
    
    def load_orders(self, csv_path: str) -> int:
        """
        Load purchase orders from CSV file.
        
        Expected columns:
        - order_id
        - sku
        - supplier_id
        - ordered_qty
        - delivery_date
        - order_status
        
        Args:
            csv_path: Path to material_orders.csv
        
        Returns:
            Number of orders loaded
        """
        path = Path(csv_path)
        if not path.exists():
            logger.error(f"ERP CSV not found: {csv_path}")
            return 0
        
        self.orders_df = pd.read_csv(csv_path)
        
        # Build lookup index by order_id
        self.orders_by_id = {}
        for _, row in self.orders_df.iterrows():
            order_id = str(row.get("order_id", "")).strip()
            if order_id:
                if order_id not in self.orders_by_id:
                    self.orders_by_id[order_id] = []
                self.orders_by_id[order_id].append(row.to_dict())
        
        logger.info(f"Loaded {len(self.orders_df)} ERP orders ({len(self.orders_by_id)} unique order IDs)")
        return len(self.orders_df)
    
    def find_order(self, order_id: str, sku: Optional[str] = None) -> Optional[dict]:
        """
        Find an ERP order by order_id and optionally SKU.
        
        Args:
            order_id: Order ID to match (e.g., "MO-1042")
            sku: Optional SKU for more precise matching
        
        Returns:
            Matching order record or None
        """
        # Normalize order_id
        order_id = str(order_id).strip().upper()
        
        # Try exact match first
        records = self.orders_by_id.get(order_id)
        
        # Try without prefix variations
        if not records:
            for key in self.orders_by_id:
                if key.upper() == order_id:
                    records = self.orders_by_id[key]
                    break
        
        if not records:
            return None
        
        # If SKU specified, filter by SKU
        if sku and len(records) > 1:
            sku = str(sku).strip().upper()
            for record in records:
                record_sku = str(record.get("sku", "")).strip().upper()
                if record_sku == sku:
                    return record
        
        # Return first matching record
        return records[0]
    
    def compare(
        self,
        order_id: str,
        supplier_date: datetime | str,
        sku: Optional[str] = None
    ) -> ERPComparison:
        """
        Compare supplier-provided date with ERP delivery date.
        
        Args:
            order_id: Order ID from supplier email
            supplier_date: Delivery date provided by supplier
            sku: Optional SKU for precise matching
        
        Returns:
            ERPComparison with delay calculation and classification
        """
        # Parse supplier date if string
        if isinstance(supplier_date, str):
            supplier_date = self._parse_date(supplier_date)
        
        # Find matching ERP record
        erp_record = self.find_order(order_id, sku)
        
        if not erp_record:
            logger.warning(f"No ERP record found for order_id: {order_id}")
            return ERPComparison(
                order_id=order_id,
                sku=sku,
                erp_delivery_date=None,
                supplier_delivery_date=supplier_date,
                delay_days=0,
                change_type=ChangeType.NO_CHANGE,
                matched=False
            )
        
        # Parse ERP delivery date
        erp_date_str = erp_record.get("delivery_date", "")
        erp_date = self._parse_date(erp_date_str)
        
        if not erp_date:
            logger.warning(f"Could not parse ERP date for {order_id}: {erp_date_str}")
            return ERPComparison(
                order_id=order_id,
                sku=erp_record.get("sku"),
                erp_delivery_date=None,
                supplier_delivery_date=supplier_date,
                delay_days=0,
                change_type=ChangeType.NO_CHANGE,
                matched=True,
                erp_record=erp_record
            )
        
        if not supplier_date:
            logger.warning(f"No supplier date provided for {order_id}")
            return ERPComparison(
                order_id=order_id,
                sku=erp_record.get("sku"),
                erp_delivery_date=erp_date,
                supplier_delivery_date=None,
                delay_days=0,
                change_type=ChangeType.NO_CHANGE,
                matched=True,
                erp_record=erp_record
            )
        
        # Calculate delay in days
        delay_days = (supplier_date - erp_date).days
        
        # Classify change
        if delay_days > 0:
            change_type = ChangeType.DELAY
        elif delay_days < 0:
            change_type = ChangeType.EARLY
        else:
            change_type = ChangeType.NO_CHANGE
        
        logger.info(f"Order {order_id}: ERP={erp_date.date()}, Supplier={supplier_date.date()}, Delay={delay_days} days → {change_type.value}")
        
        return ERPComparison(
            order_id=order_id,
            sku=erp_record.get("sku"),
            erp_delivery_date=erp_date,
            supplier_delivery_date=supplier_date,
            delay_days=delay_days,
            change_type=change_type,
            matched=True,
            erp_record=erp_record
        )
    
    def compare_batch(
        self,
        comparisons: list[dict]
    ) -> list[ERPComparison]:
        """
        Compare multiple orders at once.
        
        Args:
            comparisons: List of dicts with order_id, supplier_date, sku
        
        Returns:
            List of ERPComparison results
        """
        results = []
        for item in comparisons:
            result = self.compare(
                order_id=item.get("order_id", ""),
                supplier_date=item.get("supplier_date", ""),
                sku=item.get("sku")
            )
            results.append(result)
        return results
    
    def _parse_date(self, date_val) -> Optional[datetime]:
        """
        Parse various date formats.
        
        Handles:
        - datetime objects
        - "YYYY-MM-DD"
        - "DD/MM/YYYY"
        - "MM/DD/YYYY"
        - pandas Timestamp
        """
        if date_val is None or (isinstance(date_val, float) and pd.isna(date_val)):
            return None
        
        if isinstance(date_val, datetime):
            return date_val
        
        if hasattr(date_val, 'to_pydatetime'):  # pandas Timestamp
            return date_val.to_pydatetime()
        
        if not isinstance(date_val, str):
            date_val = str(date_val)
        
        date_val = date_val.strip()
        if not date_val:
            return None
        
        # Try common formats
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_val, fmt)
            except ValueError:
                continue
        
        # Try dateutil as fallback
        try:
            from dateutil import parser
            return parser.parse(date_val)
        except:
            return None
    
    def get_order_count(self) -> int:
        """Get number of loaded orders."""
        return len(self.orders_df) if self.orders_df is not None else 0
    
    def get_all_order_ids(self) -> list[str]:
        """Get all unique order IDs."""
        return list(self.orders_by_id.keys())


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

_comparer_instance: Optional[ERPComparer] = None


def load_erp_orders(csv_path: str) -> int:
    """
    Load ERP orders from CSV.
    
    Args:
        csv_path: Path to material_orders.csv
    
    Returns:
        Number of orders loaded
    """
    global _comparer_instance
    _comparer_instance = ERPComparer(csv_path)
    return _comparer_instance.get_order_count()


def compare_delivery_date(
    order_id: str,
    supplier_date: datetime | str,
    sku: Optional[str] = None
) -> ERPComparison:
    """
    Compare supplier date with ERP record.
    
    Args:
        order_id: Order ID from supplier
        supplier_date: Date from supplier email
        sku: Optional SKU
    
    Returns:
        ERPComparison result
    """
    global _comparer_instance
    if _comparer_instance is None:
        raise RuntimeError("Call load_erp_orders() first")
    return _comparer_instance.compare(order_id, supplier_date, sku)


def find_erp_order(order_id: str, sku: Optional[str] = None) -> Optional[dict]:
    """
    Find ERP order by ID.
    
    Args:
        order_id: Order ID to find
        sku: Optional SKU
    
    Returns:
        Order record or None
    """
    global _comparer_instance
    if _comparer_instance is None:
        return None
    return _comparer_instance.find_order(order_id, sku)
