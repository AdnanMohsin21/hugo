#!/usr/bin/env python3
"""
Test script for Inventory Balancer feature.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_inventory_balancer():
    """Test the inventory balancer with existing data."""
    try:
        from inventory_balancer import InventoryBalancer
        
        print("Testing Inventory Balancer...")
        print("=" * 50)
        
        # Initialize balancer
        ib = InventoryBalancer()
        
        # Load sales data
        sales_data = ib.load_sales_data(days_back=30)
        print(f"✅ Loaded sales data for {len(sales_data)} materials")
        
        # Load stock levels
        stock_levels = ib.load_stock_levels()
        print(f"✅ Loaded stock levels for {len(stock_levels)} materials")
        
        # Test statistics calculation
        if sales_data:
            test_material = list(sales_data.keys())[0]
            quantities = sales_data[test_material]
            avg_demand, volatility = ib.calculate_demand_statistics(quantities)
            print(f"✅ Statistics for {test_material}: avg={avg_demand:.1f}, vol={volatility:.1f}")
        
        # Test recommendation logic
        recommendation, confidence = ib.determine_recommendation(10.0, 8.0)  # High volatility
        print(f"✅ High volatility test: {recommendation} ({confidence})")
        
        recommendation, confidence = ib.determine_recommendation(10.0, 1.0)  # Low volatility
        print(f"✅ Low volatility test: {recommendation} ({confidence})")
        
        # Test memo generation (deterministic fallback)
        from inventory_balancer import InventoryRecommendation
        test_rec = InventoryRecommendation(
            material_id="TEST-001",
            avg_daily_demand=10.0,
            volatility=8.0,
            current_stock=100,
            recommendation="INCREASE_SAFETY_STOCK",
            confidence="HIGH"
        )
        
        memo = ib.generate_manager_memo(test_rec)
        print(f"✅ Memo generation: {memo[:100]}...")
        
        # Full analysis
        print("\nRunning full analysis...")
        recommendations = ib.analyze_inventory()
        print(f"✅ Generated {len(recommendations)} recommendations")
        
        # Print summary
        ib.print_summary(recommendations)
        
        print("=" * 50)
        print("🎉 Inventory Balancer test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_inventory_balancer()
    sys.exit(0 if success else 1)
