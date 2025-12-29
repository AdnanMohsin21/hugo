"""
Hugo - Inventory Balancer (Hoarding Issue Detection)

Deterministic-first inventory analysis with LLM explanation.
Detects overstocking vs understocking risk using statistical analysis.
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from utils.helpers import setup_logging
from services.huggingface_llm import HuggingFaceLLM
from data.dataset_loader import DatasetLoader
from hugo.agents.priority_arbiter import PriorityArbiter, PriorityResolution

logger = setup_logging()


@dataclass
class InventoryRecommendation:
    """Inventory analysis result for a material."""
    material_id: str
    avg_daily_demand: float
    volatility: float
    current_stock: int
    recommendation: str  # INCREASE_SAFETY_STOCK, DECREASE_SAFETY_STOCK, KEEP_STOCK
    confidence: str  # HIGH, MEDIUM, LOW
    manager_memo: Optional[str] = None


class InventoryBalancer:
    """
    Analyzes inventory levels to detect hoarding issues and recommend safety stock adjustments.
    
    Deterministic-first approach:
    1. Statistical analysis for demand patterns
    2. Rule-based recommendations
    3. LLM only for manager-facing explanations
    """
    
    def __init__(self, data_dir: str = "hugo_data_samples"):
        """
        Initialize Inventory Balancer.
        
        Args:
            data_dir: Directory containing CSV files
        """
        self.data_dir = Path(data_dir)
        self.sales_orders_file = self.data_dir / "sales_orders.csv"
        self.stock_levels_file = self.data_dir / "stock_levels.csv"
        self.llm = HuggingFaceLLM()
        
        # Initialize dataset loader for proper material mapping
        self.dataset_loader = DatasetLoader(data_dir)
        
        # Initialize Priority Arbiter for conflict resolution
        self.priority_arbiter = PriorityArbiter(logger=logger, llm_client=self.llm)
        
        logger.info("InventoryBalancer initialized")
    
    def load_sales_data(self, days_back: int = 30) -> Dict[str, List[float]]:
        """
        Load sales orders from the last N days.
        
        Args:
            days_back: Number of days to look back for sales data
            
        Returns:
            Dict mapping material_id to list of daily quantities
        """
        if not self.sales_orders_file.exists():
            logger.warning(f"Sales orders file not found: {self.sales_orders_file}")
            return {}
        
        try:
            with open(self.sales_orders_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Skip header
            if not lines:
                return {}
            
            header = lines[0].strip().split(',')
            logger.debug(f"Sales orders header: {header}")
            
            # Find column indices
            try:
                model_idx = header.index('model')
                quantity_idx = header.index('quantity')
                order_date_idx = header.index('requested_date')
            except ValueError as e:
                logger.error(f"Missing required columns in sales_orders.csv: {e}")
                return {}
            
            cutoff_date = datetime.now() - timedelta(days=days_back)
            daily_sales = {}
            
            for line in lines[1:]:
                try:
                    columns = line.strip().split(',')
                    if len(columns) < max(model_idx, quantity_idx, order_date_idx) + 1:
                        continue
                    
                    material_id = columns[model_idx]
                    quantity = float(columns[quantity_idx])
                    order_date_str = columns[order_date_idx]
                    
                    # Parse date
                    try:
                        order_date = datetime.strptime(order_date_str, '%Y-%m-%d')
                    except ValueError:
                        continue
                    
                    # Only include recent orders
                    if order_date >= cutoff_date:
                        if material_id not in daily_sales:
                            daily_sales[material_id] = []
                        daily_sales[material_id].append(quantity)
                
                except (ValueError, IndexError) as e:
                    logger.debug(f"Skipping malformed sales row: {e}")
                    continue
            
            logger.info(f"Loaded sales data for {len(daily_sales)} materials (last {days_back} days)")
            return daily_sales
            
        except Exception as e:
            logger.error(f"Error loading sales data: {e}")
            return {}
    
    def load_stock_levels(self) -> Dict[str, int]:
        """
        Load current stock levels.
        
        Returns:
            Dict mapping material_id to current stock quantity
        """
        if not self.stock_levels_file.exists():
            logger.warning(f"Stock levels file not found: {self.stock_levels_file}")
            return {}
        
        try:
            with open(self.stock_levels_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if not lines:
                return {}
            
            header = lines[0].strip().split(',')
            logger.debug(f"Stock levels header: {header}")
            
            # Find column indices
            try:
                part_id_idx = header.index('part_id')
                quantity_idx = header.index('quantity_available')
            except ValueError as e:
                logger.error(f"Missing required columns in stock_levels.csv: {e}")
                return {}
            
            stock_levels = {}
            
            for line in lines[1:]:
                try:
                    columns = line.strip().split(',')
                    if len(columns) < max(part_id_idx, quantity_idx) + 1:
                        continue
                    
                    material_id = columns[part_id_idx]
                    quantity = int(columns[quantity_idx])
                    
                    stock_levels[material_id] = quantity
                
                except (ValueError, IndexError) as e:
                    logger.debug(f"Skipping malformed stock row: {e}")
                    continue
            
            logger.info(f"Loaded stock levels for {len(stock_levels)} materials")
            return stock_levels
            
        except Exception as e:
            logger.error(f"Error loading stock levels: {e}")
            return {}
    
    def calculate_demand_statistics(self, daily_quantities: List[float]) -> Tuple[float, float]:
        """
        Calculate average daily demand and volatility.
        
        Args:
            daily_quantities: List of daily demand quantities
            
        Returns:
            Tuple of (avg_daily_demand, volatility_std)
        """
        if not daily_quantities:
            return 0.0, 0.0
        
        avg_demand = statistics.mean(daily_quantities)
        
        if len(daily_quantities) == 1:
            volatility = 0.0
        else:
            volatility = statistics.stdev(daily_quantities)
        
        return avg_demand, volatility
    
    def determine_recommendation(self, avg_demand: float, volatility: float) -> Tuple[str, str]:
        """
        Determine inventory recommendation using deterministic rules.
        
        Args:
            avg_demand: Average daily demand
            volatility: Standard deviation of demand
            
        Returns:
            Tuple of (recommendation, confidence)
        """
        if avg_demand == 0:
            return "KEEP_STOCK", "LOW"
        
        volatility_ratio = volatility / avg_demand
        
        # Deterministic rules
        if volatility_ratio > 0.6:
            recommendation = "INCREASE_SAFETY_STOCK"
            confidence = "HIGH" if volatility_ratio > 0.8 else "MEDIUM"
        elif volatility_ratio < 0.2:
            recommendation = "DECREASE_SAFETY_STOCK"
            confidence = "HIGH" if volatility_ratio < 0.1 else "MEDIUM"
        else:
            recommendation = "KEEP_STOCK"
            confidence = "HIGH" if 0.3 <= volatility_ratio <= 0.5 else "MEDIUM"
        
        return recommendation, confidence
    
    def generate_manager_memo(
        self,
        material_id: str,
        current_stock: int,
        daily_demand: float,
        days_of_cover: float,
        volatility: float,
        confidence: str
    ) -> str:
        """
        Generate manager-facing explanation using LLM.
        
        Args:
            material_id: Material identifier
            current_stock: Current stock quantity
            daily_demand: Average daily demand
            days_of_cover: Days of cover (current_stock / daily_demand)
            volatility: Demand volatility
            confidence: Confidence level
            
        Returns:
            Manager memo string
        """
        memo_prompt = f"""Generate a brief manager memo (2-3 sentences) explaining this inventory recommendation:

Material: {material_id}
Current Stock: {current_stock} units
Average Daily Demand: {daily_demand:.1f} units
Days of Cover: {days_of_cover:.1f} days
Demand Volatility: {volatility:.1f} units
Confidence: {confidence}

Focus on business impact and action needed. Be concise and professional."""

        try:
            response = self.llm.generate(memo_prompt)
            if response and len(response.strip()) > 10:
                memo = response.strip()
                # Clean up common LLM artifacts
                memo = memo.replace('"', '').replace("'", "")
                if len(memo) > 200:
                    memo = memo[:200] + "..."
                return memo
        except Exception as e:
            logger.warning(f"LLM memo generation failed for {material_id}: {e}")
        
        # Deterministic fallback based on analysis context
        if daily_demand == 0:
            return f"No recent sales data for {material_id}. Current stock of {current_stock} units should be reviewed."
        elif days_of_cover > 90:
            return f"Excess inventory detected for {material_id}. {current_stock} units represents {days_of_cover:.0f} days of cover - consider reducing safety stock."
        elif days_of_cover < 30:
            return f"Low inventory level for {material_id}. {current_stock} units represents only {days_of_cover:.0f} days of cover - monitor closely."
        else:
            return f"Inventory level for {material_id} appears appropriate with {days_of_cover:.0f} days of cover based on current demand patterns."
    
    def _calculate_demand_volatility(self, material_id: str) -> float:
        """
        Calculate demand volatility for confidence scoring.
        
        Args:
            material_id: Material identifier
            
        Returns:
            Demand volatility (standard deviation of daily demand)
        """
        try:
            # Get recent sales data
            recent_sales = self.dataset_loader.get_recent_sales(material_id, days=30)
            
            if recent_sales.empty():
                return 0.0
            
            # Extract daily quantities
            daily_quantities = []
            for row in recent_sales.data:
                try:
                    quantity = float(row.get('quantity', 0))
                    daily_quantities.append(quantity)
                except (ValueError, TypeError):
                    continue
            
            if len(daily_quantities) < 2:
                return 0.0
            
            # Calculate standard deviation
            mean_demand = sum(daily_quantities) / len(daily_quantities)
            variance = sum((q - mean_demand) ** 2 for q in daily_quantities) / len(daily_quantities)
            volatility = variance ** 0.5  # Standard deviation
            
            return volatility
            
        except Exception as e:
            logger.debug(f"Error calculating volatility for {material_id}: {e}")
            return 0.0
    
    def detect_priority_conflicts(self, recommendations: List[InventoryRecommendation]) -> List[PriorityResolution]:
        """
        Detect and resolve priority conflicts for materials with demand > stock using BOM mapping.
        
        Args:
            recommendations: List of inventory recommendations
            
        Returns:
            List of priority resolutions for conflicted materials
        """
        conflicts = []
        
        for recommendation in recommendations:
            try:
                # Get current stock
                stock_info = self.dataset_loader.get_current_stock(recommendation.material_id)
                current_stock = stock_info.get('quantity_available', 0) if stock_info else 0
                
                # Get all sales orders (not filtered by material_id)
                all_sales_data = self.dataset_loader.sales_orders
                
                if not all_sales_data or all_sales_data.empty():
                    continue
                
                # Calculate part-level demand using BOM
                total_part_demand = 0
                has_demand = False
                
                for sales_order in all_sales_data.data:
                    model = sales_order.get('model')
                    version = sales_order.get('version')
                    order_quantity = int(sales_order.get('quantity', 0))
                    
                    # Get BOM mapping for this model/version
                    bom_entries = self.dataset_loader.get_bom_mapping(model, version)
                    
                    # Check if this part is in the BOM
                    for bom_entry in bom_entries:
                        if bom_entry.get('part_id') == recommendation.material_id:
                            qty_per_unit = int(bom_entry.get('qty_per_unit', 1))
                            part_demand = order_quantity * qty_per_unit
                            total_part_demand += part_demand
                            has_demand = True
                            break
                
                # Check if part-level demand exceeds available stock
                if has_demand and total_part_demand > current_stock:
                    logger.info(f"⚔️ PRIORITY CONFLICT DETECTED: {recommendation.material_id} - demand: {total_part_demand}, stock: {current_stock}")
                    
                    # Resolve conflict using Priority Arbiter
                    resolution = self.priority_arbiter.resolve_conflict(
                        recommendation.material_id,
                        current_stock,
                        all_sales_data
                    )
                    
                    conflicts.append(resolution)
                    
            except Exception as e:
                logger.error(f"Error detecting priority conflict for {recommendation.material_id}: {e}")
                continue
        
        if conflicts:
            logger.info(f"Resolved {len(conflicts)} priority conflicts")
        else:
            logger.debug("No priority conflicts detected")
        
        return conflicts
    
    def analyze_inventory(self) -> List[InventoryRecommendation]:
        """
        Perform complete inventory analysis.
        
        Returns:
            List of inventory recommendations
        """
        logger.info("Starting inventory analysis...")
        
        # Load data using dataset loader (for proper time windows and mapping)
        recommendations = []
        
        # Process each material with proper mapping
        all_materials = self.dataset_loader.get_all_materials()
        
        for material_id in all_materials:
            try:
                # Get current stock using dataset loader
                stock_info = self.dataset_loader.get_current_stock(material_id)
                current_stock = stock_info.get('quantity_available', 0) if stock_info else 0
                
                # Calculate average daily demand using dataset loader
                avg_daily_demand = self.dataset_loader.calculate_avg_daily_demand(material_id)
                
                # Compute volatility for confidence scoring
                volatility = self._calculate_demand_volatility(material_id)
                
                # Apply deterministic rules
                recommendation, confidence = self.determine_recommendation(avg_daily_demand, volatility)
                
                # Generate manager memo
                days_of_cover = current_stock / avg_daily_demand if avg_daily_demand > 0 else 999
                memo = self.generate_manager_memo(
                    material_id=material_id,
                    current_stock=current_stock,
                    daily_demand=avg_daily_demand,
                    days_of_cover=days_of_cover,
                    volatility=volatility,
                    confidence=confidence
                )
                
                # Create recommendation
                inv_rec = InventoryRecommendation(
                    material_id=material_id,
                    avg_daily_demand=avg_daily_demand,
                    volatility=volatility,
                    current_stock=current_stock,
                    recommendation=recommendation,
                    confidence=confidence,
                    manager_memo=memo
                )
                
                recommendations.append(inv_rec)
                
                logger.info(f"Analyzed {material_id}: {recommendation} ({confidence})")
                
            except Exception as e:
                logger.error(f"Error analyzing {material_id}: {e}")
                continue
        
        logger.info(f"Generated {len(recommendations)} inventory recommendations")
        return recommendations
    
    def print_priority_wars_summary(self, conflicts: List[PriorityResolution]) -> None:
        """
        Print CLI summary of priority wars resolution.
        
        Args:
            conflicts: List of priority resolution results
        """
        if not conflicts:
            return
        
        print("\n" + "="*60)
        print("⚔️ PRIORITY WARS SUMMARY")
        print("="*60)
        
        for conflict in conflicts:
            print(f"\nPart ID: {conflict.material}")
            print(f"Total Demand: {conflict.total_demand}")
            print(f"Available Stock: {conflict.available_stock}")
            
            # Show conflicting order types
            allocation = conflict.allocation
            order_types = set()
            for status_orders in allocation.values():
                for order in status_orders:
                    order_types.add(order.order_type)
            
            print(f"Conflicting Order Types: {', '.join(sorted(order_types))}")
            
            # Show allocation decision
            fulfilled_count = len(allocation.get("fulfilled", []))
            partial_count = len(allocation.get("partial", []))
            delayed_count = len(allocation.get("delayed", []))
            
            if fulfilled_count > 0:
                print(f"Allocation Decision: Fulfill {fulfilled_count} orders by priority")
            else:
                print(f"Allocation Decision: Insufficient stock for all orders")
            
            # Show losers (deferred orders)
            if delayed_count > 0:
                delayed_order_ids = [order.order_id for order in allocation.get("delayed", [])]
                print(f"Losers (deferred orders): {', '.join(delayed_order_ids[:5])}")
                if len(delayed_order_ids) > 5:
                    print(f"  ... and {len(delayed_order_ids) - 5} more")
            else:
                print("Losers (deferred orders): None")
        
        print("\n" + "="*60)
    
    def print_summary(self, recommendations: List[InventoryRecommendation]) -> None:
        """
        Print CLI summary of inventory analysis.
        
        Args:
            recommendations: List of inventory recommendations
        """
        print("\n" + "="*60)
        print("📦 INVENTORY BALANCER SUMMARY")
        print("="*60)
        
        if not recommendations:
            print("No inventory recommendations available.")
            return
        
        # Group by recommendation type
        by_type = {}
        for rec in recommendations:
            if rec.recommendation not in by_type:
                by_type[rec.recommendation] = []
            by_type[rec.recommendation].append(rec)
        
        # Print high-priority recommendations first
        priority_order = ["INCREASE_SAFETY_STOCK", "DECREASE_SAFETY_STOCK", "KEEP_STOCK"]
        
        for rec_type in priority_order:
            if rec_type in by_type:
                recs = by_type[rec_type]
                print(f"\n{rec_type.replace('_', ' ').title()} ({len(recs)} items):")
                print("-" * 40)
                
                # Show top 3 items of each type
                for rec in recs[:3]:
                    vol_level = "High" if rec.volatility > rec.avg_daily_demand * 0.5 else "Medium" if rec.volatility > rec.avg_daily_demand * 0.2 else "Low"
                    print(f"  Material: {rec.material_id}")
                    print(f"  Current Stock: {rec.current_stock} units")
                    print(f"  Daily Demand: {rec.avg_daily_demand:.1f} units")
                    print(f"  Volatility: {vol_level}")
                    print(f"  Confidence: {rec.confidence}")
                    print(f"  Memo: {rec.manager_memo}")
                    print()
                
                if len(recs) > 3:
                    print(f"  ... and {len(recs) - 3} more items")
        
        print("="*60)


# Export for main integration
__all__ = ["InventoryBalancer", "InventoryRecommendation"]
