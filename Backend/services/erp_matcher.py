"""
Hugo - Inbox Watchdog Agent
ERP Matcher Service

Matches detected delivery changes with purchase orders from ERP system.
Uses mock JSON data for hackathon demo.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from difflib import SequenceMatcher

from config.settings import settings
from models.schemas import PurchaseOrder, DeliveryChange
from utils.helpers import setup_logging

logger = setup_logging()

# Sample ERP data for hackathon demo
MOCK_ERP_DATA = {
    "purchase_orders": [
        {
            "po_number": "PO-2024-0892",
            "supplier_id": "SUP-001",
            "supplier_name": "ACME Supplies",
            "supplier_email": "logistics@acme-supplies.com",
            "order_date": "2024-12-15",
            "expected_delivery": "2025-01-05",
            "items": [
                {"sku": "WDG-A100", "description": "Widget A", "quantity": 500, "unit_price": 12.50},
                {"sku": "WDG-B200", "description": "Widget B", "quantity": 250, "unit_price": 18.75}
            ],
            "total_value": 10937.50,
            "currency": "USD",
            "status": "open",
            "priority": "high"
        },
        {
            "po_number": "GP-78234",
            "supplier_id": "SUP-002",
            "supplier_name": "Global Parts",
            "supplier_email": "shipping@globalparts.io",
            "order_date": "2024-12-10",
            "expected_delivery": "2025-01-15",
            "items": [
                {"sku": "BRG-IND-100", "description": "Industrial Bearings", "quantity": 100, "unit_price": 45.00},
                {"sku": "GR-PREC-50", "description": "Precision Gears", "quantity": 50, "unit_price": 125.00}
            ],
            "total_value": 10750.00,
            "currency": "USD",
            "status": "open",
            "priority": "normal"
        },
        {
            "po_number": "TC-2024-445",
            "supplier_id": "SUP-003",
            "supplier_name": "Tech Components",
            "supplier_email": "orders@techcomponents.com",
            "order_date": "2024-12-01",
            "expected_delivery": "2025-01-08",
            "items": [
                {"sku": "MCU-ARM-1000", "description": "Microcontroller Units", "quantity": 1000, "unit_price": 8.50},
                {"sku": "SENS-MOD-500", "description": "Sensor Modules", "quantity": 500, "unit_price": 15.00}
            ],
            "total_value": 16000.00,
            "currency": "USD",
            "status": "open",
            "priority": "critical"
        },
        {
            "po_number": "PO-2024-0755",
            "supplier_id": "SUP-001",
            "supplier_name": "ACME Supplies",
            "supplier_email": "logistics@acme-supplies.com",
            "order_date": "2024-11-20",
            "expected_delivery": "2024-12-20",
            "items": [
                {"sku": "WDG-C300", "description": "Widget C Premium", "quantity": 100, "unit_price": 55.00}
            ],
            "total_value": 5500.00,
            "currency": "USD",
            "status": "complete",
            "priority": "normal"
        },
        {
            "po_number": "PO-2024-0999",
            "supplier_id": "SUP-004",
            "supplier_name": "Pacific Logistics",
            "supplier_email": "orders@pacificlog.com",
            "order_date": "2024-12-20",
            "expected_delivery": "2025-01-20",
            "items": [
                {"sku": "PKG-MAT-2000", "description": "Packaging Materials", "quantity": 2000, "unit_price": 2.25},
                {"sku": "LBL-STD-5000", "description": "Standard Labels", "quantity": 5000, "unit_price": 0.15}
            ],
            "total_value": 5250.00,
            "currency": "USD",
            "status": "open",
            "priority": "low"
        }
    ]
}


class ERPMatcher:
    """
    Matches delivery changes with purchase orders from ERP system.
    
    For hackathon: Uses in-memory mock data.
    Production: Would integrate with actual ERP API (SAP, Oracle, etc.)
    """
    
    def __init__(self):
        """Initialize ERP data store."""
        self.purchase_orders: list[PurchaseOrder] = []
        self._load_data()
    
    def _load_data(self) -> None:
        """
        Load ERP data from file or use mock data.
        """
        data_path = Path(settings.ERP_DATA_PATH)
        
        # Try to load from file first
        if data_path.exists():
            try:
                with open(data_path, "r") as f:
                    data = json.load(f)
                logger.info(f"Loaded ERP data from {data_path}")
            except Exception as e:
                logger.warning(f"Failed to load ERP data: {e}, using mock data")
                data = MOCK_ERP_DATA
        else:
            # Ensure data directory exists and save mock data
            data_path.parent.mkdir(parents=True, exist_ok=True)
            with open(data_path, "w") as f:
                json.dump(MOCK_ERP_DATA, f, indent=2)
            logger.info(f"Created mock ERP data at {data_path}")
            data = MOCK_ERP_DATA
        
        # Parse into PurchaseOrder models
        for po_data in data.get("purchase_orders", []):
            try:
                po = PurchaseOrder(
                    po_number=po_data["po_number"],
                    supplier_id=po_data["supplier_id"],
                    supplier_name=po_data["supplier_name"],
                    supplier_email=po_data["supplier_email"],
                    order_date=datetime.fromisoformat(po_data["order_date"]),
                    expected_delivery=datetime.fromisoformat(po_data["expected_delivery"]),
                    items=po_data["items"],
                    total_value=po_data["total_value"],
                    currency=po_data["currency"],
                    status=po_data["status"],
                    priority=po_data["priority"]
                )
                self.purchase_orders.append(po)
            except Exception as e:
                logger.error(f"Failed to parse PO: {e}")
        
        logger.info(f"Loaded {len(self.purchase_orders)} purchase orders")
    
    def find_by_po_number(self, po_number: str) -> Optional[PurchaseOrder]:
        """
        Find a purchase order by exact PO number.
        
        Args:
            po_number: PO number to search for
        
        Returns:
            PurchaseOrder if found, None otherwise
        """
        # Normalize PO number
        po_number = po_number.strip().upper()
        
        for po in self.purchase_orders:
            if po.po_number.upper() == po_number:
                return po
            # Also check without prefix variations
            if po.po_number.upper().replace("-", "").replace("#", "") == po_number.replace("-", "").replace("#", ""):
                return po
        
        return None
    
    def find_by_supplier_email(self, email: str) -> list[PurchaseOrder]:
        """
        Find all open purchase orders for a supplier by email.
        
        Args:
            email: Supplier email address
        
        Returns:
            List of matching PurchaseOrders
        """
        email = email.lower().strip()
        return [
            po for po in self.purchase_orders
            if po.supplier_email.lower() == email and po.status == "open"
        ]
    
    def match_delivery_change(
        self, 
        change: DeliveryChange, 
        sender_email: str
    ) -> Optional[PurchaseOrder]:
        """
        Match a delivery change to a purchase order.
        
        Matching strategy:
        1. Exact PO number match (if extracted)
        2. Supplier email + affected items match
        3. Supplier email + date match
        
        Args:
            change: Detected delivery change
            sender_email: Email sender address
        
        Returns:
            Best matching PurchaseOrder or None
        """
        # Strategy 1: Exact PO match
        if change.po_reference:
            po = self.find_by_po_number(change.po_reference)
            if po:
                logger.info(f"Matched by PO number: {po.po_number}")
                return po
        
        # Get supplier's open POs
        supplier_pos = self.find_by_supplier_email(sender_email)
        if not supplier_pos:
            logger.warning(f"No open POs found for supplier: {sender_email}")
            return None
        
        if len(supplier_pos) == 1:
            logger.info(f"Single PO match for supplier: {supplier_pos[0].po_number}")
            return supplier_pos[0]
        
        # Strategy 2: Match by affected items
        if change.affected_items:
            for po in supplier_pos:
                po_items = {item.get("description", "").lower() for item in po.items}
                po_skus = {item.get("sku", "").lower() for item in po.items}
                
                for affected in change.affected_items:
                    affected_lower = affected.lower()
                    if affected_lower in po_items or affected_lower in po_skus:
                        logger.info(f"Matched by item: {affected} → {po.po_number}")
                        return po
                    
                    # Fuzzy match on descriptions
                    for item_desc in po_items:
                        if self._fuzzy_match(affected_lower, item_desc) > 0.6:
                            logger.info(f"Fuzzy matched: {affected} ≈ {item_desc}")
                            return po
        
        # Strategy 3: Match by original date
        if change.original_date:
            for po in supplier_pos:
                if po.expected_delivery.date() == change.original_date.date():
                    logger.info(f"Matched by date: {po.po_number}")
                    return po
        
        # Return highest priority PO as fallback
        supplier_pos.sort(key=lambda x: {"critical": 0, "high": 1, "normal": 2, "low": 3}.get(x.priority, 2))
        logger.info(f"Fallback to highest priority PO: {supplier_pos[0].po_number}")
        return supplier_pos[0]
    
    def _fuzzy_match(self, str1: str, str2: str) -> float:
        """
        Calculate fuzzy match ratio between two strings.
        """
        return SequenceMatcher(None, str1, str2).ratio()
    
    def get_all_open_orders(self) -> list[PurchaseOrder]:
        """
        Get all open purchase orders.
        
        Returns:
            List of open PurchaseOrders
        """
        return [po for po in self.purchase_orders if po.status == "open"]
    
    def update_po_status(self, po_number: str, new_status: str) -> bool:
        """
        Update the status of a purchase order.
        
        Args:
            po_number: PO to update
            new_status: New status value
        
        Returns:
            True if updated successfully
        """
        po = self.find_by_po_number(po_number)
        if po:
            po.status = new_status
            logger.info(f"Updated {po_number} status to: {new_status}")
            return True
        return False
