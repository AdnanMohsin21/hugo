"""
Hugo - ERP Matcher Service
Matches delivery changes to purchase orders.
"""

import csv
import logging
from typing import Optional
from pathlib import Path

from models.schemas import DeliveryChange, PurchaseOrder
from utils.helpers import setup_logging

logger = setup_logging()


class ERPMatcher:
    """Matches delivery changes to ERP purchase orders."""
    
    def __init__(self):
        """Initialize ERP matcher."""
        self.purchase_orders = self._load_purchase_orders()
        logger.info(f"Loaded {len(self.purchase_orders)} purchase orders")
    
    def _load_purchase_orders(self) -> dict[str, PurchaseOrder]:
        """Load purchase orders from data file."""
        orders = {}
        
        # Try to load from CSV
        csv_path = Path("hugo_data_samples/material_orders.csv")
        if csv_path.exists():
            try:
                import csv
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        po = PurchaseOrder(
                            po_number=row.get('order_id', ''),
                            supplier_name=row.get('supplier', 'Unknown'),
                            supplier_id=row.get('supplier_id', ''),
                            material_id=row.get('material_id', ''),
                            quantity=int(row.get('quantity', 0)),
                            expected_delivery=None,
                            priority=row.get('priority', 'normal'),
                            total_value=float(row.get('value', 0))
                        )
                        orders[po.po_number] = po
            except Exception as e:
                logger.error(f"Error loading purchase orders: {e}")
        
        return orders
    
    def match_delivery_change(self, change: DeliveryChange, sender_email: str) -> Optional[PurchaseOrder]:
        """Match delivery change to purchase order."""
        # Simple matching by PO reference if available
        if change.po_reference and change.po_reference in self.purchase_orders:
            return self.purchase_orders[change.po_reference]
        
        # Try to match by sender email
        for po in self.purchase_orders.values():
            if sender_email in po.supplier_name.lower():
                return po
        
        return None
    
    def get_all_open_orders(self) -> list[PurchaseOrder]:
        """Get all open purchase orders."""
        return list(self.purchase_orders.values())
