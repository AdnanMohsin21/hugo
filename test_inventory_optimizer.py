"""
Tests for Hugo Inventory Optimizer module.

Demonstrates inventory optimization across different scenarios.
Requires Ollama running on localhost:11434.
"""

from services.inventory_optimizer import (
    optimize_inventory_settings,
    PartData,
    InventoryRecommendation
)


def test_high_value_critical_part():
    """Test optimization for expensive, high-priority part."""
    
    print("=" * 70)
    print("Scenario 1: High-Value Critical Part (Expensive, Risk-Averse)")
    print("-" * 70)
    print()
    
    part = PartData(
        sku="CRIT-001",
        part_name="High-Precision Bearing Assembly",
        annual_demand=500,  # 500 units/year = ~10/week
        lead_time_days=28,  # Long lead time from supplier
        lead_time_variability=0.2,  # Some variability
        demand_variability=0.15,  # Relatively stable demand
        current_inventory=150,
        current_reorder_point=150,
        current_safety_stock=100,
        current_lot_size=100,
        carrying_cost_per_unit_year=75,  # Expensive to hold (capital, space)
        ordering_cost_per_order=250,  # High procurement cost
        stockout_cost_per_unit=5000,  # VERY expensive to stockout (production stops)
        service_level_target=0.98,  # HIGH service level target
        supplier_reliability_score=0.75,  # Moderate reliability
        recent_stockouts=0,  # No recent issues
        forecast_accuracy=0.85
    )
    
    print("Input Parameters:")
    print(f"  SKU: {part.sku} ({part.part_name})")
    print(f"  Demand: {part.annual_demand} units/year ({part.annual_demand/52:.1f} units/week)")
    print(f"  Lead Time: {part.lead_time_days} days (variability: {part.lead_time_variability})")
    print(f"  Carrying Cost: ${part.carrying_cost_per_unit_year}/unit/year")
    print(f"  Stockout Cost: ${part.stockout_cost_per_unit}/unit (VERY HIGH)")
    print(f"  Service Level Target: {part.service_level_target*100}%")
    print(f"  Supplier Reliability: {part.supplier_reliability_score*100}%")
    print()
    
    try:
        rec = optimize_inventory_settings(part)
        
        print("Optimization Result:")
        print(f"  New Reorder Point: {rec.reorder_point:.0f} (change: {rec.reorder_point_change:+.0f})")
        print(f"  New Safety Stock: {rec.safety_stock:.0f} (change: {rec.safety_stock_change:+.0f})")
        print(f"  New Lot Size: {rec.lot_size:.0f} (change: {rec.lot_size_change_percent:+.1f}%)")
        print(f"  Expected Service Level: {rec.expected_fill_rate*100:.1f}%")
        print(f"  Expected Stockouts/Year: {rec.expected_stockouts_per_year:.1f}")
        print()
        
        print("Cost Impact:")
        print(f"  Carrying Cost Change: ${rec.carrying_cost_change:+.0f}/year")
        print(f"  Ordering Cost Change: ${rec.ordering_cost_change:+.0f}/year")
        print()
        
        print("Rationale:")
        print(f"  {rec.rationale}")
        print()
        
        print("Trade-Offs Explanation:")
        print(f"  {rec.trade_offs}")
        print()
        
        if rec.key_factors:
            print("Key Factors:")
            for factor in rec.key_factors:
                print(f"  • {factor}")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
        print("(Ollama likely not running. Start with: ollama run gemma:2b)")
    
    print()


def test_high_volume_commodity():
    """Test optimization for high-volume commodity part."""
    
    print("=" * 70)
    print("Scenario 2: High-Volume Commodity (Cost-Focused)")
    print("-" * 70)
    print()
    
    part = PartData(
        sku="COMM-250",
        part_name="Standard M5 Bolt",
        annual_demand=50000,  # Very high volume
        lead_time_days=14,
        lead_time_variability=0.05,  # Very stable supplier
        demand_variability=0.25,  # Some seasonal variation
        current_inventory=2000,
        current_reorder_point=2000,
        current_safety_stock=1000,
        current_lot_size=5000,
        carrying_cost_per_unit_year=0.05,  # Very cheap to hold
        ordering_cost_per_order=50,  # Minimal procurement cost
        stockout_cost_per_unit=1,  # Low impact (easy to substitute)
        service_level_target=0.90,  # Lower service level acceptable
        supplier_reliability_score=0.95,  # Very reliable
        recent_stockouts=0,
        forecast_accuracy=0.90
    )
    
    print("Input Parameters:")
    print(f"  SKU: {part.sku} ({part.part_name})")
    print(f"  Demand: {part.annual_demand} units/year ({part.annual_demand/52:.0f} units/week)")
    print(f"  Lead Time: {part.lead_time_days} days (very stable)")
    print(f"  Carrying Cost: ${part.carrying_cost_per_unit_year}/unit/year (VERY LOW)")
    print(f"  Stockout Cost: ${part.stockout_cost_per_unit}/unit (minimal impact)")
    print(f"  Service Level Target: {part.service_level_target*100}%")
    print(f"  Supplier Reliability: {part.supplier_reliability_score*100}% (excellent)")
    print()
    
    try:
        rec = optimize_inventory_settings(part)
        
        print("Optimization Result:")
        print(f"  New Reorder Point: {rec.reorder_point:.0f} (change: {rec.reorder_point_change:+.0f})")
        print(f"  New Safety Stock: {rec.safety_stock:.0f} (change: {rec.safety_stock_change:+.0f})")
        print(f"  New Lot Size: {rec.lot_size:.0f} (change: {rec.lot_size_change_percent:+.1f}%)")
        print()
        
        print("Rationale:")
        print(f"  {rec.rationale}")
        print()
        
        print("Trade-Offs Explanation:")
        print(f"  {rec.trade_offs}")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()


def test_unreliable_supplier_volatile_demand():
    """Test optimization for unreliable supplier and volatile demand."""
    
    print("=" * 70)
    print("Scenario 3: Unreliable Supplier + Volatile Demand (Safety-Focused)")
    print("-" * 70)
    print()
    
    part = PartData(
        sku="RISK-789",
        part_name="Specialty Sensor Module",
        annual_demand=2000,
        lead_time_days=45,  # LONG lead time
        lead_time_variability=0.4,  # HIGH variability
        demand_variability=0.5,  # HIGHLY volatile demand
        current_inventory=500,
        current_reorder_point=500,
        current_safety_stock=300,
        current_lot_size=400,
        carrying_cost_per_unit_year=120,  # Expensive
        ordering_cost_per_order=300,
        stockout_cost_per_unit=2000,  # High impact
        service_level_target=0.95,  # Want reliability
        supplier_reliability_score=0.60,  # UNRELIABLE supplier
        recent_stockouts=3,  # Had problems
        forecast_accuracy=0.70  # Poor forecast accuracy
    )
    
    print("Input Parameters:")
    print(f"  SKU: {part.sku} ({part.part_name})")
    print(f"  Lead Time: {part.lead_time_days} days (HIGH variability: {part.lead_time_variability})")
    print(f"  Demand Variability: {part.demand_variability} (VERY VOLATILE)")
    print(f"  Supplier Reliability: {part.supplier_reliability_score*100}% (UNRELIABLE)")
    print(f"  Recent Stockouts: {part.recent_stockouts} (has had issues)")
    print(f"  Forecast Accuracy: {part.forecast_accuracy*100}% (POOR)")
    print()
    
    try:
        rec = optimize_inventory_settings(part)
        
        print("Optimization Result:")
        print(f"  New Reorder Point: {rec.reorder_point:.0f} (change: {rec.reorder_point_change:+.0f})")
        print(f"  New Safety Stock: {rec.safety_stock:.0f} (change: {rec.safety_stock_change:+.0f})")
        print()
        
        print("Trade-Offs Explanation:")
        print(f"  {rec.trade_offs}")
        print()
        
        print("Implementation Notes:")
        print(f"  {rec.implementation_notes}")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()


def test_balanced_standard_part():
    """Test optimization for balanced, standard part."""
    
    print("=" * 70)
    print("Scenario 4: Balanced Standard Part (Optimized Cost/Service)")
    print("-" * 70)
    print()
    
    part = PartData(
        sku="STD-450",
        part_name="Standard Capacitor 10uF",
        annual_demand=10000,
        lead_time_days=21,
        lead_time_variability=0.15,
        demand_variability=0.20,
        current_inventory=800,
        current_reorder_point=600,
        current_safety_stock=400,
        current_lot_size=1000,
        carrying_cost_per_unit_year=5,
        ordering_cost_per_order=100,
        stockout_cost_per_unit=50,
        service_level_target=0.92,  # Balanced target
        supplier_reliability_score=0.88,
        recent_stockouts=0,
        forecast_accuracy=0.85
    )
    
    print("Input Parameters:")
    print(f"  SKU: {part.sku} ({part.part_name})")
    print(f"  Balanced demand, lead time, supplier reliability")
    print()
    
    try:
        rec = optimize_inventory_settings(part)
        
        print("Optimization Result:")
        print(f"  Reorder Point: {rec.reorder_point:.0f}")
        print(f"  Safety Stock: {rec.safety_stock:.0f}")
        print(f"  Lot Size: {rec.lot_size:.0f}")
        print(f"  Expected Service Level: {rec.expected_fill_rate*100:.1f}%")
        print()
        
        print("Rationale:")
        print(f"  {rec.rationale}")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()


def test_fallback_behavior():
    """Test safe fallback behavior when Ollama is unavailable."""
    
    print("=" * 70)
    print("Scenario 5: Fallback Behavior (Ollama Unavailable)")
    print("-" * 70)
    print()
    
    part = PartData(
        sku="FB-001",
        part_name="Test Part",
        annual_demand=1000,
        current_reorder_point=100,
        current_safety_stock=50,
        current_lot_size=200
    )
    
    print("Testing fallback with invalid Ollama URL...")
    
    try:
        # Use invalid URL to trigger fallback
        rec = optimize_inventory_settings(
            part,
            ollama_url="http://invalid-ollama:11434"
        )
        
        if rec.is_fallback:
            print(f"✓ Fallback activated: {rec.error}")
            print(f"  Conservative ROP: {rec.reorder_point:.0f} (was {part.current_reorder_point})")
            print(f"  Conservative SS: {rec.safety_stock:.0f} (was {part.current_safety_stock})")
            print(f"  Conservative Lot: {rec.lot_size:.0f} (was {part.current_lot_size})")
            print()
            print("Trade-offs (fallback):")
            print(f"  {rec.trade_offs}")
        else:
            print("Unexpected: fallback not activated")
    except Exception as e:
        print(f"Error during fallback test: {e}")
    
    print()


if __name__ == "__main__":
    print()
    print("HUGO INVENTORY OPTIMIZER - TEST SCENARIOS")
    print("=" * 70)
    print()
    print("NOTE: This test requires Ollama running on localhost:11434")
    print("Start Ollama with: ollama run gemma:2b")
    print()
    
    test_high_value_critical_part()
    test_high_volume_commodity()
    test_unreliable_supplier_volatile_demand()
    test_balanced_standard_part()
    test_fallback_behavior()
    
    print("=" * 70)
    print("All test scenarios completed!")
    print("=" * 70)
