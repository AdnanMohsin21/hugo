"""
Hugo Inventory Optimizer - Integration Examples

Shows how to use the inventory optimizer with other Hugo modules
in real procurement scenarios.
"""

from services.inventory_optimizer import optimize_inventory_settings, PartData
from datetime import datetime


def example_1_alert_triggered_optimization():
    """
    Example: When a supplier alert is triggered, re-optimize inventory.
    
    Scenario: Alert decision detected a supplier delay.
    Now we optimize inventory to handle future delays from this supplier.
    """
    
    print("=" * 70)
    print("Example 1: Alert-Triggered Optimization")
    print("=" * 70)
    print()
    print("Scenario: Supplier alert triggered for MOTOR-X1")
    print("  - 5-day delay detected")
    print("  - Supplier reliability score dropped to 0.65")
    print("  - Decision: Optimize inventory to be more protective")
    print()
    
    # Part was affected by supplier delay
    part = PartData(
        sku="MOTOR-X1",
        part_name="Electric Motor Assembly",
        annual_demand=1000,
        lead_time_days=14,
        lead_time_variability=0.15,
        demand_variability=0.2,
        current_inventory=80,
        current_reorder_point=150,
        current_safety_stock=100,
        current_lot_size=200,
        carrying_cost_per_unit_year=50,
        ordering_cost_per_order=150,
        stockout_cost_per_unit=500,
        service_level_target=0.95,
        supplier_reliability_score=0.65,  # Degraded after delay
        recent_stockouts=1,  # Had recent issue
        forecast_accuracy=0.85
    )
    
    print("Optimizing inventory for increased supplier risk...")
    print()
    
    try:
        rec = optimize_inventory_settings(part)
        
        print("Results:")
        print(f"  Current ROP: {part.current_reorder_point}")
        print(f"  Recommended ROP: {rec.reorder_point:.0f} ({rec.reorder_point_change:+.0f})")
        print()
        print(f"  Current Safety Stock: {part.current_safety_stock}")
        print(f"  Recommended Safety Stock: {rec.safety_stock:.0f} ({rec.safety_stock_change:+.0f})")
        print()
        print("Key Insight:")
        print(f"  '{rec.rationale}'")
        print()
        print("Actions:")
        print("  1. Increase ROP to {:.0f} immediately".format(rec.reorder_point))
        print("  2. Place standing order to maintain {} units safety stock".format(rec.safety_stock))
        print("  3. Consider finding alternate supplier for this part")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()


def example_2_capacity_constrained_optimization():
    """
    Example: Optimize inventory while respecting warehouse space constraints.
    
    Scenario: Warehouse is at 90% capacity. We need to optimize
    inventory for multiple parts while staying within space allocation.
    """
    
    print("=" * 70)
    print("Example 2: Space-Constrained Optimization")
    print("=" * 70)
    print()
    print("Scenario: Warehouse at 90% capacity")
    print("  - Available space for this SKU: 500 units")
    print("  - Current inventory: 450 units")
    print("  - Need to reduce or maintain")
    print()
    
    part = PartData(
        sku="CAP-10UF",
        part_name="Ceramic Capacitor 10uF",
        annual_demand=30000,
        lead_time_days=21,
        lead_time_variability=0.1,
        demand_variability=0.15,
        current_inventory=450,
        current_reorder_point=800,
        current_safety_stock=500,
        current_lot_size=2000,
        carrying_cost_per_unit_year=2,
        ordering_cost_per_order=75,
        stockout_cost_per_unit=10,
        service_level_target=0.92,
        supplier_reliability_score=0.90,
        max_warehouse_space_allocated=500,  # Limited by warehouse
        recent_stockouts=0,
        forecast_accuracy=0.88
    )
    
    print("Optimizing inventory with space constraint...")
    print()
    
    try:
        rec = optimize_inventory_settings(part)
        
        # Calculate expected average inventory
        expected_avg_inventory = rec.reorder_point - (rec.lot_size / 2)
        
        print("Results:")
        print(f"  Current ROP: {part.current_reorder_point}")
        print(f"  Recommended ROP: {rec.reorder_point:.0f}")
        print()
        print(f"  Current Lot Size: {part.current_lot_size}")
        print(f"  Recommended Lot Size: {rec.lot_size:.0f}")
        print()
        print(f"  Expected Average Inventory: {expected_avg_inventory:.0f} units")
        print(f"  Space Limit: {part.max_warehouse_space_allocated}")
        print()
        
        if expected_avg_inventory <= part.max_warehouse_space_allocated:
            print("✓ Recommendation fits within space constraint")
            print()
            print("Actions:")
            print("  1. Implement new ROP of {:.0f} units".format(rec.reorder_point))
            print("  2. Adjust lot size to {:.0f} units".format(rec.lot_size))
            print("  3. This will maintain ~{:.0f} average inventory".format(expected_avg_inventory))
        else:
            print("⚠ Recommendation EXCEEDS space constraint")
            print("  Consider: reduce service level target or split purchases across time")
        
        print()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()


def example_3_cost_service_tradeoff():
    """
    Example: Analyze cost vs. service level trade-offs.
    
    Scenario: Finance wants to reduce inventory carrying costs.
    Operations wants to maintain high service levels.
    Optimizer helps find the right balance.
    """
    
    print("=" * 70)
    print("Example 3: Cost vs. Service Level Trade-Off Analysis")
    print("=" * 70)
    print()
    print("Scenario: Finance vs. Operations")
    print("  Finance: 'We're spending too much on inventory carrying costs'")
    print("  Operations: 'We need high service levels to not disrupt production'")
    print("  Procurement: 'Let's optimize to find the right balance'")
    print()
    
    part = PartData(
        sku="BEARING-X",
        part_name="High-Precision Ball Bearing",
        annual_demand=800,
        lead_time_days=28,
        lead_time_variability=0.2,
        demand_variability=0.15,
        current_inventory=300,
        current_reorder_point=400,
        current_safety_stock=250,
        current_lot_size=300,
        carrying_cost_per_unit_year=100,  # Expensive to hold
        ordering_cost_per_order=200,
        stockout_cost_per_unit=2000,  # Very expensive to stockout
        service_level_target=0.95,
        supplier_reliability_score=0.80,
        recent_stockouts=0,
        forecast_accuracy=0.85
    )
    
    print("Running optimization to balance cost and service...")
    print()
    
    try:
        rec = optimize_inventory_settings(part)
        
        # Calculate impacts
        annual_carrying_change = rec.carrying_cost_change
        annual_ordering_change = rec.ordering_cost_change
        total_change = annual_carrying_change + annual_ordering_change
        
        print("Financial Impact:")
        print(f"  Carrying Cost Change: ${annual_carrying_change:+,.0f}/year")
        print(f"  Ordering Cost Change: ${annual_ordering_change:+,.0f}/year")
        print(f"  Net Annual Cost Change: ${total_change:+,.0f}/year")
        print()
        
        print("Service Level Impact:")
        print(f"  Current Service Level: 95%")
        print(f"  Expected Service Level: {rec.expected_fill_rate*100:.1f}%")
        print(f"  Expected Stockouts/Year: {rec.expected_stockouts_per_year:.1f}")
        print()
        
        print("Trade-Off Analysis:")
        print(f"  {rec.trade_offs}")
        print()
        
        print("Recommendation:")
        if total_change < 0:
            print(f"  ✓ This optimization SAVES ${abs(total_change):,.0f} annually")
            print(f"    while maintaining high service level!")
        elif total_change > 0:
            print(f"  This optimization costs ${total_change:,.0f} annually")
            print(f"    in exchange for better service level and reduced stockout risk")
        
        print()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()


def example_4_batch_portfolio_optimization():
    """
    Example: Optimize multiple parts in a product portfolio.
    
    Scenario: New product launch. Need to optimize inventory for
    all components in the bill of materials.
    """
    
    print("=" * 70)
    print("Example 4: Portfolio Optimization (Multiple Parts)")
    print("=" * 70)
    print()
    print("Scenario: Optimizing 5 critical parts for new product assembly")
    print()
    
    parts = [
        PartData(
            sku="MOTOR-A1",
            part_name="Motor Assembly",
            annual_demand=5000,
            lead_time_days=21,
            carrying_cost_per_unit_year=80,
            ordering_cost_per_order=200,
            stockout_cost_per_unit=1000,
            service_level_target=0.96
        ),
        PartData(
            sku="GEAR-B2",
            part_name="Gear Assembly",
            annual_demand=5000,
            lead_time_days=28,
            carrying_cost_per_unit_year=60,
            ordering_cost_per_order=180,
            stockout_cost_per_unit=800,
            service_level_target=0.96
        ),
        PartData(
            sku="PCB-C3",
            part_name="Control Board",
            annual_demand=5000,
            lead_time_days=35,
            carrying_cost_per_unit_year=150,
            ordering_cost_per_order=250,
            stockout_cost_per_unit=2000,
            service_level_target=0.96
        ),
        PartData(
            sku="CABLE-D4",
            part_name="Power Cable Assembly",
            annual_demand=5000,
            lead_time_days=14,
            carrying_cost_per_unit_year=5,
            ordering_cost_per_order=50,
            stockout_cost_per_unit=100,
            service_level_target=0.95
        ),
        PartData(
            sku="FASTENER-E5",
            part_name="Hardware Kit",
            annual_demand=5000,
            lead_time_days=7,
            carrying_cost_per_unit_year=1,
            ordering_cost_per_order=25,
            stockout_cost_per_unit=50,
            service_level_target=0.92
        ),
    ]
    
    print("Optimizing {}  parts...".format(len(parts)))
    print()
    
    try:
        results = {}
        total_carrying_change = 0
        total_ordering_change = 0
        
        for part in parts:
            rec = optimize_inventory_settings(part)
            results[part.sku] = rec
            total_carrying_change += rec.carrying_cost_change
            total_ordering_change += rec.ordering_cost_change
        
        # Summary table
        print("Portfolio Optimization Results:")
        print()
        print("{:<12} {:<15} {:<10} {:<10} {:<15}".format(
            "SKU", "New ROP", "New Safety Ss", "Lot Size", "Service Level"
        ))
        print("-" * 70)
        
        for part in parts:
            rec = results[part.sku]
            print("{:<12} {:<15.0f} {:<10.0f} {:<10.0f} {:<15.1f}%".format(
                part.sku,
                rec.reorder_point,
                rec.safety_stock,
                rec.lot_size,
                rec.expected_fill_rate * 100
            ))
        
        print()
        print("Portfolio Financial Impact:")
        print(f"  Total Carrying Cost Change: ${total_carrying_change:+,.0f}/year")
        print(f"  Total Ordering Cost Change: ${total_ordering_change:+,.0f}/year")
        print(f"  Net Annual Cost Change: ${total_carrying_change + total_ordering_change:+,.0f}/year")
        print()
        
        print("Key Insight:")
        print("  All components optimized for consistency.")
        print("  Aligned reorder schedule may improve production efficiency.")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()


def example_5_compliance_and_traceability():
    """
    Example: Track optimization decisions for compliance.
    
    Scenario: Auditors need to see how inventory decisions are made.
    Optimizer provides full justification for audit trail.
    """
    
    print("=" * 70)
    print("Example 5: Compliance & Decision Traceability")
    print("=" * 70)
    print()
    print("Scenario: Audit review of inventory management decisions")
    print("  Question: 'Why are we holding 500 units of this part?'")
    print("  Answer: Let the optimizer explain...")
    print()
    
    part = PartData(
        sku="SENSOR-X1",
        part_name="Pressure Sensor",
        annual_demand=2000,
        lead_time_days=45,
        lead_time_variability=0.3,
        demand_variability=0.25,
        current_inventory=400,
        current_reorder_point=500,
        current_safety_stock=400,
        current_lot_size=600,
        carrying_cost_per_unit_year=75,
        ordering_cost_per_order=300,
        stockout_cost_per_unit=3000,
        service_level_target=0.97,
        supplier_reliability_score=0.75,
        recent_stockouts=2,
        forecast_accuracy=0.75
    )
    
    print("Generating audit documentation...")
    print()
    
    try:
        rec = optimize_inventory_settings(part)
        
        # Create audit record
        audit_record = {
            "timestamp": datetime.now().isoformat(),
            "sku": part.sku,
            "part_name": part.part_name,
            "decision_type": "Inventory Optimization",
            "recommended_reorder_point": rec.reorder_point,
            "recommended_safety_stock": rec.safety_stock,
            "recommended_lot_size": rec.lot_size,
            "expected_service_level": rec.expected_fill_rate,
            "rationale": rec.rationale,
            "trade_off_analysis": rec.trade_offs,
            "key_factors": rec.key_factors,
            "cost_impact": {
                "carrying_cost_change": rec.carrying_cost_change,
                "ordering_cost_change": rec.ordering_cost_change,
                "net_annual_change": rec.carrying_cost_change + rec.ordering_cost_change
            }
        }
        
        print("Audit Record Generated:")
        print()
        print("Part: {} ({})".format(part.sku, part.part_name))
        print("Decision: Inventory Optimization")
        print("Timestamp: {}".format(audit_record["timestamp"]))
        print()
        
        print("Recommendations:")
        print("  Reorder Point: {:.0f} units".format(rec.reorder_point))
        print("  Safety Stock: {:.0f} units".format(rec.safety_stock))
        print("  Lot Size: {:.0f} units".format(rec.lot_size))
        print()
        
        print("Justification:")
        print(f"  {rec.rationale}")
        print()
        
        print("Trade-Off Analysis:")
        print(f"  {rec.trade_offs}")
        print()
        
        print("Key Factors Considered:")
        for i, factor in enumerate(rec.key_factors, 1):
            print(f"  {i}. {factor}")
        print()
        
        print("✓ Audit trail complete with full decision justification")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()


if __name__ == "__main__":
    print()
    print("HUGO INVENTORY OPTIMIZER - INTEGRATION EXAMPLES")
    print("=" * 70)
    print()
    print("These examples show real-world scenarios where the inventory")
    print("optimizer helps procurement decisions.")
    print()
    print("Note: Examples require Ollama running on localhost:11434")
    print()
    
    example_1_alert_triggered_optimization()
    example_2_capacity_constrained_optimization()
    example_3_cost_service_tradeoff()
    example_4_batch_portfolio_optimization()
    example_5_compliance_and_traceability()
    
    print("=" * 70)
    print("All examples completed!")
    print("=" * 70)
