#!/usr/bin/env python3
"""
Test the fixed InventoryBalancer to verify it works with dataset_loader.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_inventory_balancer():
    """Test InventoryBalancer with dataset_loader integration."""
    print("Testing Fixed InventoryBalancer...")
    print("=" * 50)
    
    try:
        # Test InventoryBalancer initialization
        from inventory_balancer import InventoryBalancer
        
        print("1. Testing InventoryBalancer initialization...")
        balancer = InventoryBalancer()
        
        # Check that dataset_loader is properly initialized
        if hasattr(balancer, 'dataset_loader'):
            print("✅ Dataset loader initialized")
        else:
            print("❌ Dataset loader not initialized")
            return False
        
        # Test analysis
        print("\n2. Testing inventory analysis...")
        recommendations = balancer.analyze_inventory()
        
        if recommendations:
            print(f"✅ Generated {len(recommendations)} recommendations")
            
            # Check for non-zero demand
            non_zero_demand = [r for r in recommendations if r.avg_daily_demand > 0]
            print(f"✅ Materials with non-zero demand: {len(non_zero_demand)}")
            
            # Check confidence levels
            confidence_levels = {"LOW", "MEDIUM", "HIGH"}
            valid_confidence = all(r.confidence in confidence_levels for r in recommendations)
            if valid_confidence:
                print("✅ All confidence levels valid")
            else:
                print("❌ Invalid confidence levels found")
            
            # Show sample recommendation
            if recommendations:
                sample = recommendations[0]
                print(f"\nSample recommendation:")
                print(f"  Material: {sample.material_id}")
                print(f"  Daily Demand: {sample.avg_daily_demand:.2f}")
                print(f"  Current Stock: {sample.current_stock}")
                print(f"  Recommendation: {sample.recommendation}")
                print(f"  Confidence: {sample.confidence}")
        else:
            print("❌ No recommendations generated")
            return False
        
        print("\n" + "=" * 50)
        print("🎉 InventoryBalancer working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_inventory_balancer()
    sys.exit(0 if success else 1)
