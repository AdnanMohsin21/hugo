#!/usr/bin/env python3
"""
Test Hugo system imports and basic functionality.
"""

import sys
import os

def test_imports():
    """Test all critical imports."""
    print("Testing Hugo System Imports...")
    print("=" * 50)
    
    try:
        # Test config
        from config.settings import settings
        print("✅ config.settings")
        
        # Test models
        from models.schemas import Email, DeliveryChange, PurchaseOrder, AlertResult
        print("✅ models.schemas")
        
        # Test services
        from services.json_repair import attempt_json_repair, clean_json_text, normalize_json_output
        print("✅ services.json_repair")
        
        from services.huggingface_llm import HuggingFaceLLM
        print("✅ services.huggingface_llm")
        
        from services.signal_extractor import SignalExtractor
        print("✅ services.signal_extractor")
        
        from services.deterministic_logic import calculate_delay_days, build_delivery_change
        print("✅ services.deterministic_logic")
        
        from services.delivery_detector import DeliveryDetector
        print("✅ services.delivery_detector")
        
        from services.email_ingestion import EmailIngestionService
        print("✅ services.email_ingestion")
        
        from services.erp_matcher import ERPMatcher
        print("✅ services.erp_matcher")
        
        from services.vector_store import VectorStore
        print("✅ services.vector_store")
        
        from services.risk_engine import RiskEngine
        print("✅ services.risk_engine")
        
        # Test utils
        from utils.helpers import setup_logging, clean_text
        print("✅ utils.helpers")
        
        # Test inventory balancer
        from inventory_balancer import InventoryBalancer, InventoryRecommendation
        print("✅ inventory_balancer")
        
        print("\n" + "=" * 50)
        print("🎉 All imports successful!")
        
        # Test basic functionality
        print("\nTesting basic functionality...")
        
        # Test JSON repair
        test_json = clean_json_text('{"key": "value"}')
        print(f"✅ JSON repair: {test_json}")
        
        # Test inventory balancer initialization
        ib = InventoryBalancer()
        print("✅ Inventory Balancer initialized")
        
        # Test data loading
        sales_data = ib.load_sales_data(days_back=30)
        stock_data = ib.load_stock_levels()
        print(f"✅ Loaded {len(sales_data)} sales records, {len(stock_data)} stock records")
        
        print("\n" + "=" * 50)
        print("🚀 System is ready to run!")
        print("\nTo see the full demo:")
        print("python main.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
