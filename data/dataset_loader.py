"""
Hugo - Dataset Loader
Production-grade CSV data loading with normalization and accessors.
"""

import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from utils.helpers import setup_logging

logger = setup_logging()


class SimpleDataFrame:
    """Simple DataFrame-like class for CSV data without pandas."""
    
    def __init__(self, data: List[Dict[str, Any]], columns: List[str]):
        self.data = data
        self.columns = [col.lower().strip() for col in columns]
        self._normalize_columns()
    
    def _normalize_columns(self):
        """Normalize column names and data."""
        for row in self.data:
            # Create new dict with normalized keys
            normalized = {}
            for key, value in row.items():
                norm_key = key.lower().strip()
                normalized[norm_key] = value
            row.clear()
            row.update(normalized)
    
    def __len__(self) -> int:
        return len(self.data)
    
    def empty(self) -> bool:
        return len(self.data) == 0
    
    def iloc(self, index: int):
        """Get row by index."""
        if 0 <= index < len(self.data):
            return SimpleRow(self.data[index])
        raise IndexError("Index out of range")


class SimpleRow:
    """Simple row wrapper for dict-like access."""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
    
    def to_dict(self) -> Dict[str, Any]:
        return self.data.copy()


class DatasetLoader:
    """
    Production-grade dataset loader for Hugo inventory analysis.
    
    Loads and normalizes all CSV files with proper date handling.
    Provides deterministic accessors for hoarding detection.
    """
    
    def __init__(self, data_dir: str = "hugo_data_samples"):
        """
        Initialize DatasetLoader with all CSV files.
        
        Args:
            data_dir: Directory containing CSV files
        """
        self.data_dir = Path(data_dir)
        
        # Load all datasets
        self.sales_orders = self._load_csv("sales_orders.csv")
        self.stock_levels = self._load_csv("stock_levels.csv")
        self.material_master = self._load_csv("material_master.csv")
        self.dispatch_parameters = self._load_csv("dispatch_parameters.csv")
        self.bom = self._load_csv("bom.csv")  # NEW: Bill of Materials
        self.suppliers = self._load_csv("suppliers.csv")  # Fix 2: Load suppliers.csv
        
        # Set reference date from sales orders
        self.reference_date = self._calculate_reference_date()
        
        logger.info(f"DatasetLoader initialized with all CSV files")
        logger.info(f"Loaded datasets: {len(self.sales_orders)} sales orders, {len(self.material_master)} materials, {len(self.stock_levels)} stock levels, {len(self.bom)} BOM entries, {len(self.suppliers) if self.suppliers else 0} suppliers")
    
    def _calculate_reference_date(self):
        """Calculate reference date from sales orders."""
        if not self.sales_orders or self.sales_orders.empty():
            return datetime.now()
        
        dates = []
        for row in self.sales_orders.data:
            created_date = row.get('created_at')
            if created_date:
                # Handle both string and datetime formats
                if isinstance(created_date, str):
                    try:
                        created_date = datetime.strptime(created_date, '%Y-%m-%d')
                        dates.append(created_date)
                    except (ValueError, TypeError):
                        continue
                else:
                    dates.append(created_date)
        
        if dates:
            return max(dates)
        else:
            return datetime.now()
    
    def _load_all_datasets(self):
        """Load and normalize all CSV datasets."""
        try:
            # Load sales orders first to establish reference date
            self.sales_orders = self._load_csv("sales_orders.csv", parse_dates=['requested_date', 'created_at', 'accepted_request_date'])
            
            # Set reference date as max of sales dates for proper time windows
            if self.sales_orders and not self.sales_orders.empty():
                dates = []
                for row in self.sales_orders.data:
                    created_date = row.get('created_at')
                    if created_date:
                        dates.append(created_date)
                if dates:
                    self.reference_date = max(dates)
                    logger.info(f"Reference date set to: {self.reference_date.strftime('%Y-%m-%d')}")
                else:
                    self.reference_date = datetime.now()
                    logger.warning("No valid dates in sales data, using system date")
            else:
                self.reference_date = datetime.now()
                logger.warning("No sales data available, using system date")
            
            # Load remaining datasets
            self.material_master = self._load_csv("material_master.csv")
            self.material_orders = self._load_csv("material_orders.csv", parse_dates=['order_date'])
            self.stock_levels = self._load_csv("stock_levels.csv")
            self.stock_movements = self._load_csv("stock_movements.csv", parse_dates=['movement_date'])
            self.dispatch_parameters = self._load_csv("dispatch_parameters.csv")
            self.suppliers = self._load_csv("suppliers.csv")
            
            logger.info(f"Loaded datasets: {len(self.sales_orders) if self.sales_orders else 0} sales orders, "
                       f"{len(self.material_master) if self.material_master else 0} materials, "
                       f"{len(self.stock_levels) if self.stock_levels else 0} stock levels")
            
        except Exception as e:
            logger.error(f"Error loading datasets: {e}")
            raise
    
    def _load_csv(self, filename: str, parse_dates: Optional[List[str]] = None) -> Optional[SimpleDataFrame]:
        """
        Load and normalize a CSV file.
        
        Args:
            filename: CSV filename
            parse_dates: List of date columns to parse
            
        Returns:
            Normalized SimpleDataFrame or None
        """
        file_path = self.data_dir / filename
        
        if not file_path.exists():
            logger.warning(f"Dataset file not found: {file_path}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
                columns = reader.fieldnames or []
            
            # Parse date columns
            if parse_dates:
                for row in data:
                    for col in parse_dates:
                        if col in row:
                            try:
                                row[col] = datetime.strptime(row[col], '%Y-%m-%d')
                            except (ValueError, TypeError):
                                row[col] = None
            
            # Fix 1: Cast quantity_available to int for stock_levels.csv
            if filename == "stock_levels.csv":
                for row in data:
                    if 'quantity_available' in row:
                        try:
                            # Remove commas and convert to int
                            qty_str = str(row['quantity_available']).replace(',', '').strip()
                            row['quantity_available'] = int(qty_str)
                        except (ValueError, TypeError):
                            row['quantity_available'] = 0
            
            # Remove rows with critical null values
            data = [row for row in data if row and list(row.values())[0]]
            
            logger.debug(f"Loaded {filename}: {len(data)} rows, {len(columns)} columns")
            return SimpleDataFrame(data, columns)
            
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return None
    
    def get_recent_sales(self, material_id: str, days: int = 30) -> SimpleDataFrame:
        """
        Get recent sales for a material using dataset-driven time window.
        
        Args:
            material_id: Material identifier
            days: Number of days to look back
            
        Returns:
            SimpleDataFrame with recent sales for material
        """
        if not self.sales_orders or not self.reference_date:
            return SimpleDataFrame([], [])
        
        # Use reference date for proper time windows
        cutoff_date = self.reference_date - timedelta(days=days)
        
        # Filter by material and date
        filtered_data = []
        for row in self.sales_orders.data:
            try:
                requested_date = row.get('requested_date')
                # Handle both string and datetime formats
                if isinstance(requested_date, str):
                    try:
                        requested_date = datetime.strptime(requested_date, '%Y-%m-%d')
                    except (ValueError, TypeError):
                        continue
                
                if (row.get('model') == material_id and 
                    requested_date and requested_date >= cutoff_date):
                    filtered_data.append(row)
            except Exception:
                continue
        
        return SimpleDataFrame(filtered_data, self.sales_orders.columns)
    
    def get_current_stock(self, material_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current stock level for a material.
        
        Args:
            material_id: Material identifier
            
        Returns:
            Stock info dict or None
        """
        if not self.stock_levels:
            return None
        
        for row in self.stock_levels.data:
            if row.get('part_id') == material_id:
                return row
        
        return None
    
    def get_supplier(self, material_id: str) -> Optional[Dict[str, Any]]:
        """
        Get supplier information for a material.
        
        Args:
            material_id: Material identifier
            
        Returns:
            Supplier info dict or None
        """
        if not self.material_master or not self.suppliers:
            return None
        
        # Find material in master
        material_row = None
        for row in self.material_master.data:
            if row.get('part_id') == material_id:
                material_row = row
                break
        
        if not material_row:
            return None
        
        supplier_id = material_row.get('supplier_id')
        
        if not supplier_id:
            return None
        
        # Find supplier
        for row in self.suppliers.data:
            if row.get('supplier_id') == supplier_id:
                return row
        
        return None
    
    def get_dispatch_constraints(self, material_id: str) -> Optional[Dict[str, Any]]:
        """
        Get dispatch parameters for a material.
        
        Args:
            material_id: Material identifier
            
        Returns:
            Dispatch constraints dict or None
        """
        if not self.dispatch_parameters:
            return None
        
        for row in self.dispatch_parameters.data:
            if row.get('material_id') == material_id:
                return row
        
        return None
    
    def calculate_avg_daily_demand(self, material_id: str, days: int = 30) -> float:
        """
        Calculate average daily demand for a material.
        
        Args:
            material_id: Material identifier
            days: Number of days to analyze
            
        Returns:
            Average daily demand (units per day)
        """
        recent_sales = self.get_recent_sales(material_id, days)
        
        if recent_sales.empty():
            return 0.0
        
        total_quantity = 0
        for row in recent_sales.data:
            try:
                quantity = int(row.get('quantity', 0))
                total_quantity += quantity
            except (ValueError, TypeError):
                continue
        
        avg_daily = total_quantity / days
        return avg_daily
    
    def get_material_summary(self, material_id: str) -> Dict[str, Any]:
        """
        Get comprehensive summary for a material.
        
        Args:
            material_id: Material identifier
            
        Returns:
            Material summary dict
        """
        summary = {
            'material_id': material_id,
            'current_stock': None,
            'avg_daily_demand': 0.0,
            'supplier': None,
            'dispatch_constraints': None,
            'recent_sales_count': 0
        }
        
        # Get current stock
        stock_info = self.get_current_stock(material_id)
        if stock_info:
            try:
                summary['current_stock'] = int(stock_info.get('quantity_available', 0))
            except (ValueError, TypeError):
                summary['current_stock'] = 0
        
        # Calculate average demand
        summary['avg_daily_demand'] = self.calculate_avg_daily_demand(material_id)
        
        # Get supplier info
        supplier_info = self.get_supplier(material_id)
        if supplier_info:
            summary['supplier'] = supplier_info
        
        # Get dispatch constraints
        dispatch_info = self.get_dispatch_constraints(material_id)
        if dispatch_info:
            summary['dispatch_constraints'] = dispatch_info
        
        # Get recent sales count
        recent_sales = self.get_recent_sales(material_id, 30)
        summary['recent_sales_count'] = len(recent_sales.data)
        
        return summary
    
    def get_bom_mapping(self, model: str, version: str) -> List[Dict[str, Any]]:
        """
        Get BOM mapping for a specific model and version.
        
        Args:
            model: Model identifier
            version: Version identifier
            
        Returns:
            List of BOM entries for this model/version
        """
        if not self.bom:
            return []
        
        bom_entries = []
        for row in self.bom.data:
            if (row.get('model') == model and 
                row.get('version') == version):
                bom_entries.append(row)
        
        return bom_entries
    
    def get_all_materials(self) -> List[str]:
        """
        Get all unique material IDs from stock levels.
        
        Returns:
            List of material IDs
        """
        if not self.stock_levels:
            return []
        
        materials = set()
        for row in self.stock_levels.data:
            part_id = row.get('part_id')
            if part_id:
                materials.add(part_id)
        # Remove None and empty values
        materials.discard(None)
        materials.discard('')
        
        return sorted(list(materials))


# Export for integration
__all__ = ["DatasetLoader"]
