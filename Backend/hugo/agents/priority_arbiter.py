"""
Hugo - Priority Wars Arbiter

Deterministic-first priority allocation agent for stock conflicts.
Resolves allocation disputes when demand exceeds available stock.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("hugo")


@dataclass
class AllocationResult:
    """Result of priority allocation for a single order."""
    order_id: str
    order_type: str
    requested_quantity: int
    allocated_quantity: int
    status: str  # "fulfilled", "partial", "delayed"
    customer_id: Optional[str] = None


@dataclass
class PriorityResolution:
    """Complete priority conflict resolution result."""
    material: str
    available_stock: int
    total_demand: int
    allocation: Dict[str, List[AllocationResult]]  # {"fulfilled": [...], "partial": [...], "delayed": [...]}
    delayed_orders: List[str]  # Order IDs that were delayed
    summary: str  # Short text summary
    explanation: Optional[str] = None  # LLM-generated customer explanation


class PriorityArbiter:
    """
    Priority-based stock allocation arbiter.
    
    Resolves conflicts when demand exceeds available stock using deterministic priority rules.
    Optional LLM integration for customer communication generation.
    """
    
    # Priority rules (hardcoded, deterministic)
    PRIORITY_RULES = {
        "fleet_framework": 1,  # Highest priority - contractual penalties
        "fleet_spot": 2,        # Medium priority
        "webshop": 3          # Lowest priority - margin
    }
    
    def __init__(self, logger=None, llm_client=None):
        """
        Initialize Priority Arbiter.
        
        Args:
            logger: Logger instance (defaults to hugo logger)
            llm_client: Optional LLM client for explanation generation
        """
        self.logger = logger or logging.getLogger("hugo")
        self.llm_client = llm_client
        
        self.logger.info("PriorityArbiter initialized")
    
    def resolve_conflict(self, material_id: str, available_stock: int, sales_orders_df) -> PriorityResolution:
        """
        Resolve priority conflict for a material using BOM mapping.
        
        Args:
            material_id: Material identifier (part_id)
            available_stock: Available stock quantity
            sales_orders_df: Sales orders data (SimpleDataFrame)
            
        Returns:
            PriorityResolution with allocation plan
        """
        self.logger.info(f"Resolving priority conflict for {material_id}: {available_stock} available")
        
        try:
            # Expand sales orders into part-level demand using BOM
            part_demand = self._calculate_part_demand(material_id, sales_orders_df)
            
            if not part_demand:
                return self._create_empty_resolution(material_id, available_stock)
            
            # Group part demand by order_type
            grouped_demand = self._group_part_demand_by_type(part_demand)
            
            # Sort groups by priority (fleet_framework > fleet_spot > webshop)
            sorted_groups = self._sort_by_priority(grouped_demand)
            
            # Allocate stock greedily by priority
            allocation_plan = self._allocate_part_stock(available_stock, sorted_groups)
            
            # Calculate total demand
            total_demand = sum(demand['total_quantity'] for demand in part_demand)
            
            # Generate summary
            summary = self._generate_summary(material_id, available_stock, total_demand, allocation_plan)
            
            # Create resolution result
            resolution = PriorityResolution(
                material=material_id,
                available_stock=available_stock,
                total_demand=total_demand,
                allocation=allocation_plan,
                delayed_orders=[order.order_id for order in allocation_plan.get("delayed", [])],
                summary=summary,
                explanation=None  # No LLM for this implementation
            )
            
            self.logger.info(f"Priority resolution complete for {material_id}: {len(allocation_plan.get('fulfilled', []))} fulfilled, {len(allocation_plan.get('delayed', []))} delayed")
            
            return resolution
            
        except Exception as e:
            self.logger.error(f"Error resolving priority conflict for {material_id}: {e}")
            # Return safe fallback
            return self._create_fallback_resolution(material_id, available_stock)
    
    def _calculate_part_demand(self, part_id: str, sales_orders_df) -> List[Dict]:
        """
        Calculate part-level demand from sales orders using BOM mapping.
        
        Args:
            part_id: Part identifier
            sales_orders_df: Sales orders data
            
        Returns:
            List of part demand entries
        """
        part_demand = []
        
        # Get dataset loader for BOM access
        from data.dataset_loader import DatasetLoader
        dataset_loader = DatasetLoader()
        
        for sales_order in sales_orders_df.data:
            model = sales_order.get('model')
            version = sales_order.get('version')
            order_quantity = int(sales_order.get('quantity', 0))
            order_type = sales_order.get('order_type', 'unknown')
            order_id = sales_order.get('sales_order_id', f'unknown_{len(part_demand)}')
            
            # Get BOM mapping for this model/version
            bom_entries = dataset_loader.get_bom_mapping(model, version)
            
            # Find if this part is in the BOM
            for bom_entry in bom_entries:
                if bom_entry.get('part_id') == part_id:
                    qty_per_unit = int(bom_entry.get('qty_per_unit', 1))
                    total_part_demand = order_quantity * qty_per_unit
                    
                    part_demand.append({
                        'order_id': order_id,
                        'order_type': order_type,
                        'model': model,
                        'version': version,
                        'order_quantity': order_quantity,
                        'qty_per_unit': qty_per_unit,
                        'total_quantity': total_part_demand
                    })
                    break
        
        self.logger.debug(f"Calculated part demand for {part_id}: {len(part_demand)} entries")
        return part_demand
    
    def _group_part_demand_by_type(self, part_demand: List[Dict]) -> Dict[str, List[Dict]]:
        """Group part demand by order_type."""
        grouped = {}
        
        for demand in part_demand:
            order_type = demand.get('order_type', 'unknown')
            if order_type not in grouped:
                grouped[order_type] = []
            grouped[order_type].append(demand)
        
        self.logger.debug(f"Grouped part demand by type: {list(grouped.keys())}")
        return grouped
    
    def _allocate_part_stock(self, available_stock: int, sorted_groups: List[Tuple[str, List[Dict]]]) -> Dict[str, List[AllocationResult]]:
        """
        Allocate stock to part-level demand by priority.
        
        Args:
            available_stock: Available stock quantity
            sorted_groups: Demand groups sorted by priority
            
        Returns:
            Dictionary with "fulfilled", "partial", "delayed" allocation results
        """
        allocation = {"fulfilled": [], "partial": [], "delayed": []}
        remaining_stock = available_stock
        
        for order_type, demands in sorted_groups:
            priority = self.PRIORITY_RULES.get(order_type, 999)
            self.logger.debug(f"Processing {order_type} demands (priority {priority}), remaining stock: {remaining_stock}")
            
            for demand in demands:
                order_id = demand.get('order_id', f'unknown_{len(allocation["fulfilled"])}')
                requested_quantity = demand.get('total_quantity', 0)
                model = demand.get('model', 'unknown')
                
                if remaining_stock >= requested_quantity:
                    # Full fulfillment
                    allocation_result = AllocationResult(
                        order_id=order_id,
                        order_type=order_type,
                        requested_quantity=requested_quantity,
                        allocated_quantity=requested_quantity,
                        status="fulfilled"
                    )
                    allocation["fulfilled"].append(allocation_result)
                    remaining_stock -= requested_quantity
                    
                elif remaining_stock > 0:
                    # Partial fulfillment
                    allocation_result = AllocationResult(
                        order_id=order_id,
                        order_type=order_type,
                        requested_quantity=requested_quantity,
                        allocated_quantity=remaining_stock,
                        status="partial"
                    )
                    allocation["partial"].append(allocation_result)
                    remaining_stock = 0
                    
                else:
                    # Delayed
                    allocation_result = AllocationResult(
                        order_id=order_id,
                        order_type=order_type,
                        requested_quantity=requested_quantity,
                        allocated_quantity=0,
                        status="delayed"
                    )
                    allocation["delayed"].append(allocation_result)
        
        return allocation
    
    def _filter_material_orders(self, material_id: str, sales_orders_df) -> List[Dict]:
        """Filter sales orders for the given material."""
        try:
            material_orders = []
            
            for row in sales_orders_df.data:
                # Check if this order is for our material
                if row.get('material_id') == material_id:
                    material_orders.append(row)
            
            self.logger.debug(f"Found {len(material_orders)} orders for {material_id}")
            return material_orders
            
        except Exception as e:
            self.logger.error(f"Error filtering orders for {material_id}: {e}")
            return []
    
    def _group_by_order_type(self, orders: List[Dict]) -> Dict[str, List[Dict]]:
        """Group orders by order_type."""
        grouped = {}
        
        for order in orders:
            order_type = order.get('order_type', 'unknown')
            if order_type not in grouped:
                grouped[order_type] = []
            grouped[order_type].append(order)
        
        self.logger.debug(f"Grouped orders by type: {list(grouped.keys())}")
        return grouped
    
    def _sort_by_priority(self, grouped_orders: Dict[str, List[Dict]]) -> List[Tuple[str, List[Dict]]]:
        """Sort order groups by priority rules."""
        # Sort by priority number (lower = higher priority)
        sorted_groups = sorted(
            grouped_orders.items(),
            key=lambda x: self.PRIORITY_RULES.get(x[0], 999)
        )
        
        self.logger.debug(f"Priority order: {[group_type for group_type, _ in sorted_groups]}")
        return sorted_groups
    
    def _allocate_stock(self, available_stock: int, sorted_groups: List[Tuple[str, List[Dict]]]) -> Dict[str, List[AllocationResult]]:
        """
        Allocate stock greedily by priority.
        
        Args:
            available_stock: Available stock quantity
            sorted_groups: Order groups sorted by priority
            
        Returns:
            Dictionary with "fulfilled", "partial", "delayed" allocation results
        """
        allocation = {"fulfilled": [], "partial": [], "delayed": []}
        remaining_stock = available_stock
        
        for order_type, orders in sorted_groups:
            priority = self.PRIORITY_RULES.get(order_type, 999)
            self.logger.debug(f"Processing {order_type} orders (priority {priority}), remaining stock: {remaining_stock}")
            
            for order in orders:
                order_id = order.get('order_id', f'unknown_{len(allocation["fulfilled"])}')
                requested_quantity = int(order.get('quantity', 0))
                customer_id = order.get('customer_id')
                
                if remaining_stock >= requested_quantity:
                    # Full fulfillment
                    allocation_result = AllocationResult(
                        order_id=order_id,
                        order_type=order_type,
                        requested_quantity=requested_quantity,
                        allocated_quantity=requested_quantity,
                        status="fulfilled",
                        customer_id=customer_id
                    )
                    allocation["fulfilled"].append(allocation_result)
                    remaining_stock -= requested_quantity
                    
                elif remaining_stock > 0:
                    # Partial fulfillment
                    allocation_result = AllocationResult(
                        order_id=order_id,
                        order_type=order_type,
                        requested_quantity=requested_quantity,
                        allocated_quantity=remaining_stock,
                        status="partial",
                        customer_id=customer_id
                    )
                    allocation["partial"].append(allocation_result)
                    remaining_stock = 0
                    
                else:
                    # Delayed
                    allocation_result = AllocationResult(
                        order_id=order_id,
                        order_type=order_type,
                        requested_quantity=requested_quantity,
                        allocated_quantity=0,
                        status="delayed",
                        customer_id=customer_id
                    )
                    allocation["delayed"].append(allocation_result)
        
        return allocation
    
    def _generate_summary(self, material_id: str, available_stock: int, total_demand: int, allocation: Dict[str, List[AllocationResult]]) -> str:
        """Generate short text summary of allocation."""
        fulfilled_count = len(allocation.get("fulfilled", []))
        partial_count = len(allocation.get("partial", []))
        delayed_count = len(allocation.get("delayed", []))
        
        summary = f"Material {material_id}: {fulfilled_count} fulfilled, {partial_count} partial, {delayed_count} delayed (stock: {available_stock}, demand: {total_demand})"
        
        return summary
    
    def _generate_explanation(self, allocation: Dict[str, List[AllocationResult]]) -> Optional[str]:
        """
        Generate customer explanation for delayed orders.
        
        Non-blocking: if LLM fails, returns None and system continues.
        """
        if not self.llm_client:
            return None
        
        delayed_orders = allocation.get("delayed", [])
        if not delayed_orders:
            return None
        
        try:
            # Create explanation prompt
            delayed_count = len(delayed_orders)
            prompt = f"""Generate a brief, professional explanation for customers whose orders are delayed due to high demand.

Context:
- {delayed_count} orders are delayed
- Orders are allocated by business priority
- Fleet framework orders have highest priority (contractual obligations)
- Webshop orders have medium priority
- Fleet spot orders have lowest priority

Generate a polite, professional 2-3 sentence explanation that:
1. Acknowledges the delay
2. Explains it's due to high demand
3. Mentions priority-based allocation
4. Expresses apology and commitment to service

Keep it concise and customer-friendly."""

            response = self.llm_client.generate(prompt)
            if response and len(response.strip()) > 10:
                explanation = response.strip()
                # Clean up common LLM artifacts
                explanation = explanation.replace('"', '').replace("'", "")
                if len(explanation) > 300:
                    explanation = explanation[:300] + "..."
                return explanation
                
        except Exception as e:
            self.logger.warning(f"LLM explanation generation failed: {e}")
        
        # Fallback to None (system will use static template)
        return None
    
    def _create_empty_resolution(self, material_id: str, available_stock: int) -> PriorityResolution:
        """Create resolution for material with no orders."""
        return PriorityResolution(
            material=material_id,
            available_stock=available_stock,
            total_demand=0,
            allocation={"fulfilled": [], "partial": [], "delayed": []},
            delayed_orders=[],
            summary=f"Material {material_id}: No pending orders (stock: {available_stock})"
        )
    
    def _create_fallback_resolution(self, material_id: str, available_stock: int) -> PriorityResolution:
        """Create safe fallback resolution when errors occur."""
        return PriorityResolution(
            material=material_id,
            available_stock=available_stock,
            total_demand=0,
            allocation={"fulfilled": [], "partial": [], "delayed": []},
            delayed_orders=[],
            summary=f"Material {material_id}: Allocation processing error - manual review required (stock: {available_stock})"
        )


# Export for integration
__all__ = ["PriorityArbiter", "PriorityResolution", "AllocationResult"]
