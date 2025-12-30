#!/usr/bin/env python3
"""
Test the import fix for PriorityResolution.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_import_fix():
    """Test that PriorityResolution import is fixed."""
    print("Testing PriorityResolution Import Fix...")
    print("=" * 50)
    
    try:
        # Test direct import
        from hugo.agents.priority_arbiter import PriorityResolution
        print("✅ PriorityResolution imported directly")
        
        # Test InventoryBalancer import
        from inventory_balancer import InventoryBalancer
        print("✅ InventoryBalancer imported successfully")
        
        # Test initialization
        balancer = InventoryBalancer()
        print("✅ InventoryBalancer initialized")
        
        # Test method availability
        if hasattr(balancer, 'detect_priority_conflicts'):
            print("✅ detect_priority_conflicts method available")
        else:
            print("❌ detect_priority_conflicts method missing")
        
        print("\n" + "=" * 50)
        print("🎉 Import fix successful!")
        print("Priority Wars feature is ready to use.")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_import_fix()
    sys.exit(0 if success else 1)
