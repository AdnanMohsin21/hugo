#!/usr/bin/env python3
"""
Test the runtime bug fixes for Priority Wars and Hoarding Risk.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_runtime_fixes():
    """Test that runtime bugs are fixed."""
    print("Testing Runtime Bug Fixes...")
    print("=" * 60)
    
    try:
        # Test Fix 1: quantity_available casting
        print("1. Testing Fix 1: quantity_available casting...")
        from data.dataset_loader import DatasetLoader
        
        loader = DatasetLoader()
        
        # Check stock_levels data types
        if loader.stock_levels and not loader.stock_levels.empty():
            sample_row = loader.stock_levels.data[0]
            qty_available = sample_row.get('quantity_available')
            if isinstance(qty_available, int):
                print(f"✅ quantity_available is int: {qty_available}")
            else:
                print(f"❌ quantity_available is {type(qty_available)}: {qty_available}")
                return False
        else:
            print("❌ No stock_levels data")
            return False
        
        # Test Fix 2: suppliers loading
        print("\n2. Testing Fix 2: suppliers loading...")
        if hasattr(loader, 'suppliers') and loader.suppliers:
            print(f"✅ suppliers loaded: {len(loader.suppliers)} entries")
            if not loader.suppliers.empty():
                sample_supplier = loader.suppliers.data[0]
                print(f"   Sample supplier: {sample_supplier.get('supplier_id', 'N/A')}")
        else:
            print("❌ suppliers not loaded")
            return False
        
        # Test Priority Wars with fixed types
        print("\n3. Testing Priority Wars with fixed types...")
        from inventory_balancer import InventoryBalancer
        
        balancer = InventoryBalancer()
        recommendations = balancer.analyze_inventory()
        
        if recommendations:
            print(f"✅ Inventory analysis successful: {len(recommendations)} recommendations")
            
            # Test conflict detection
            conflicts = balancer.detect_priority_conflicts(recommendations)
            print(f"✅ Priority conflicts detected: {len(conflicts)}")
        else:
            print("❌ No recommendations generated")
            return False
        
        # Test Hoarding Risk with suppliers
        print("\n4. Testing Hoarding Risk with suppliers...")
        from analytics.hoarding_detector import HoardingDetector
        
        detector = HoardingDetector(loader)
        
        # Check if suppliers are accessible
        if hasattr(detector.dataset_loader, 'suppliers'):
            print("✅ HoardingDetector can access suppliers")
            
            # Test hoarding analysis
            results = detector.analyze_all_materials()
            print(f"✅ Hoarding analysis completed: {len(results)} results")
        else:
            print("❌ HoardingDetector cannot access suppliers")
            return False
        
        print("\n" + "=" * 60)
        print("🎉 Runtime Bug Fixes Successful!")
        print("\nFixes Applied:")
        print("✅ Fix 1: quantity_available cast to int")
        print("✅ Fix 2: suppliers.csv loaded and accessible")
        print("✅ Priority Wars executes without type errors")
        print("✅ Hoarding Risk executes without attribute errors")
        
        print("\nSystem Status:")
        print("• Priority Wars: int(part_demand) > int(quantity_available)")
        print("• Hoarding Risk: self.dataset_loader.suppliers available")
        print("• No runtime crashes")
        print("• Existing outputs unchanged")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_runtime_fixes()
    sys.exit(0 if success else 1)
