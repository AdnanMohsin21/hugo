"""
Hugo - Hoarding Detector
Deterministic inventory hoarding risk detection using real demand and stock data.
"""

import logging
from typing import Dict, List, Optional, Any
from enum import Enum

from data.dataset_loader import DatasetLoader
from utils.helpers import setup_logging

logger = setup_logging()


class HoardingRiskLevel(str, Enum):
    """Hoarding risk levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class HoardingConfidence(str, Enum):
    """Confidence levels for hoarding detection."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class HoardingResult:
    """Result of hoarding risk analysis for a material."""
    
    def __init__(self, material: str, risk_level: str, excess_units: int, confidence: str):
        self.material = material
        self.risk_level = risk_level
        self.excess_units = excess_units
        self.confidence = confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "material": self.material,
            "risk_level": self.risk_level,
            "excess_units": self.excess_units,
            "confidence": self.confidence
        }


class HoardingDetector:
    """
    Detects inventory hoarding risk using deterministic rules.
    
    Analyzes demand patterns vs current stock levels to identify
    potential hoarding issues that tie up capital and storage.
    """
    
    def __init__(self, dataset_loader: DatasetLoader):
        """
        Initialize hoarding detector.
        
        Args:
            dataset_loader: Loaded dataset with sales and stock data
        """
        self.dataset = dataset_loader
        logger.info("HoardingDetector initialized")
    
    def analyze_material(self, material_id: str) -> HoardingResult:
        """
        Analyze hoarding risk for a single material.
        
        Logic:
        - Calculate avg_daily_demand from sales_orders.csv
        - Compare with stock_levels.csv
        - Flag hoarding risk if: stock > (avg_daily_demand * dispatch_days * 1.5)
        
        Args:
            material_id: Material identifier
            
        Returns:
            HoardingResult with risk assessment
        """
        try:
            # Get material summary with proper mapping
            summary = self.dataset.get_material_summary(material_id)
            
            current_stock = summary.get('current_stock', 0) or 0
            avg_daily_demand = summary.get('avg_daily_demand', 0.0)
            dispatch_constraints = summary.get('dispatch_constraints')
            
            # Get dispatch days from constraints or use default
            dispatch_days = self._get_dispatch_days(dispatch_constraints)
            
            # Calculate optimal stock level
            optimal_stock = avg_daily_demand * dispatch_days
            hoarding_threshold = optimal_stock * 1.5  # 50% above optimal
            
            # Calculate excess units
            excess_units = max(0, current_stock - optimal_stock)
            
            # Calculate demand volatility for confidence scoring
            volatility = self._calculate_demand_volatility(material_id)
            
            # Determine risk level with safety for zero demand
            risk_level = self._calculate_risk_level(
                current_stock, optimal_stock, avg_daily_demand, dispatch_days
            )
            
            # Calculate confidence based on data quality and volatility
            confidence = self._calculate_confidence(
                summary.get('recent_sales_count', 0),
                current_stock > 0,
                dispatch_constraints is not None,
                volatility
            )
            
            result = HoardingResult(
                material=material_id,
                risk_level=risk_level,
                excess_units=excess_units,
                confidence=confidence
            )
            
            logger.debug(f"Material {material_id}: stock={current_stock}, "
                        f"avg_demand={avg_daily_demand:.1f}, "
                        f"optimal={optimal_stock:.1f}, "
                        f"volatility={volatility:.1f}, "
                        f"risk={risk_level}, excess={excess_units}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing material {material_id}: {e}")
            # Return conservative result
            return HoardingResult(
                material=material_id,
                risk_level=HoardingRiskLevel.LOW,
                excess_units=0,
                confidence=HoardingConfidence.LOW
            )
    
    def analyze_all_materials(self) -> List[HoardingResult]:
        """
        Analyze hoarding risk for all materials.
        
        Returns:
            List of HoardingResult for all materials
        """
        materials = self.dataset.get_all_materials()
        results = []
        
        logger.info(f"Analyzing hoarding risk for {len(materials)} materials")
        
        for material_id in materials:
            result = self.analyze_material(material_id)
            results.append(result)
        
        # Sort by risk level and excess units
        risk_priority = {HoardingRiskLevel.HIGH: 3, HoardingRiskLevel.MEDIUM: 2, HoardingRiskLevel.LOW: 1}
        results.sort(key=lambda x: (risk_priority.get(x.risk_level, 0), x.excess_units), reverse=True)
        
        high_risk_count = sum(1 for r in results if r.risk_level == HoardingRiskLevel.HIGH)
        medium_risk_count = sum(1 for r in results if r.risk_level == HoardingRiskLevel.MEDIUM)
        total_excess = sum(r.excess_units for r in results)
        
        logger.info(f"Hoarding analysis complete: {high_risk_count} high risk, "
                   f"{medium_risk_count} medium risk, {total_excess} total excess units")
        
        return results
    
    def _get_dispatch_days(self, dispatch_constraints: Optional[Dict[str, Any]]) -> int:
        """
        Extract dispatch days from constraints.
        
        Args:
            dispatch_constraints: Dispatch parameters dict
            
        Returns:
            Dispatch days in integer
        """
        if not dispatch_constraints:
            return 30  # Default dispatch lead time
        
        # Try different field names for dispatch days
        dispatch_day_fields = [
            'dispatch_days', 'lead_time_days', 'delivery_days', 
            'lead_time', 'delivery_lead_time'
        ]
        
        for field in dispatch_day_fields:
            if field in dispatch_constraints:
                try:
                    return int(dispatch_constraints[field])
                except (ValueError, TypeError):
                    continue
        
        return 30  # Default if no valid field found
    
    def _calculate_risk_level(self, current_stock: int, optimal_stock: float, 
                           avg_daily_demand: float, dispatch_days: int) -> str:
        """
        Calculate hoarding risk level using deterministic rules.
        
        Args:
            current_stock: Current inventory level
            optimal_stock: Calculated optimal stock level
            avg_daily_demand: Average daily demand
            dispatch_days: Dispatch lead time in days
            
        Returns:
            Risk level string
        """
        # SAFETY: If no demand, cannot classify as medium/high hoarding risk
        if avg_daily_demand == 0:
            return HoardingRiskLevel.LOW
        
        # Calculate stock ratio
        stock_ratio = current_stock / optimal_stock if optimal_stock > 0 else 0
        
        # Risk thresholds
        if stock_ratio >= 2.0:  # 200%+ of optimal
            return HoardingRiskLevel.HIGH
        elif stock_ratio >= 1.5:  # 150%+ of optimal
            return HoardingRiskLevel.MEDIUM
        elif stock_ratio >= 1.2:  # 120%+ of optimal
            return HoardingRiskLevel.LOW
        else:
            return HoardingRiskLevel.LOW
    
    def _calculate_demand_volatility(self, material_id: str) -> float:
        """
        Calculate demand volatility for a material.
        
        Args:
            material_id: Material identifier
            
        Returns:
            Demand volatility (standard deviation of daily demand)
        """
        try:
            # Get recent sales data
            recent_sales = self.dataset.get_recent_sales(material_id, days=30)
            
            if recent_sales.empty():
                return 0.0
            
            # Calculate daily demand quantities
            daily_quantities = []
            for row in recent_sales.data:
                try:
                    quantity = int(row.get('quantity', 0))
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
    
    def _calculate_confidence(self, recent_sales_count: int, has_stock_data: bool, 
                          has_constraints: bool, volatility: float = 0.0) -> str:
        """
        Calculate confidence level based on data quality and volatility.
        
        Args:
            recent_sales_count: Number of recent sales records
            has_stock_data: Whether stock data is available
            has_constraints: Whether dispatch constraints are available
            volatility: Demand volatility for confidence assessment
            
        Returns:
            Confidence level string
        """
        # Base confidence on data completeness
        data_quality_score = 0
        
        if recent_sales_count >= 10:
            data_quality_score += 2
        elif recent_sales_count >= 5:
            data_quality_score += 1
        
        if has_stock_data:
            data_quality_score += 1
        
        if has_constraints:
            data_quality_score += 1
        
        # Adjust confidence based on volatility
        if volatility > 0:
            if volatility > 20:
                data_quality_score += 1  # High volatility increases confidence
            elif volatility > 10:
                data_quality_score += 0.5  # Medium volatility
            else:
                data_quality_score += 0.2  # Low volatility slightly increases confidence
        
        # Convert to confidence level
        if data_quality_score >= 4:
            return HoardingConfidence.HIGH
        elif data_quality_score >= 2.5:
            return HoardingConfidence.MEDIUM
        else:
            return HoardingConfidence.LOW
    
    def get_redistribution_actions(self, result: HoardingResult) -> List[str]:
        """
        Generate recommended redistribution actions.
        
        Args:
            result: Hoarding analysis result
            
        Returns:
            List of recommended actions
        """
        actions = []
        
        if result.risk_level == HoardingRiskLevel.HIGH:
            actions.extend([
                f"Immediate redistribution of {result.excess_units} excess units",
                "Review procurement policies for material",
                "Consider just-in-time ordering",
                "Free up storage capacity"
            ])
        elif result.risk_level == HoardingRiskLevel.MEDIUM:
            actions.extend([
                f"Plan redistribution of {result.excess_units} excess units",
                "Monitor demand patterns closely",
                "Adjust safety stock levels"
            ])
        elif result.excess_units > 0:
            actions.extend([
                f"Consider reducing stock by {result.excess_units} units",
                "Review reorder points"
            ])
        else:
            actions.append("Stock level appears appropriate")
        
        return actions


# Export for integration
__all__ = ["HoardingDetector", "HoardingResult", "HoardingRiskLevel", "HoardingConfidence"]
