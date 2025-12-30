#!/usr/bin/env python3
"""
Test script to check all imports for main.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test all imports needed for main.py"""
    
    try:
        print("Testing imports...")
        
        # Test config
        from config.settings import settings
        print("✅ config.settings")
        
        # Test models
        from models.schemas import Email, DeliveryChange, PurchaseOrder, AlertResult
        print("✅ models.schemas")
        
        # Test services
        from services.email_ingestion import EmailIngestionService
        print("✅ services.email_ingestion")
        
        from services.delivery_detector import DeliveryDetector
        print("✅ services.delivery_detector")
        
        from services.erp_matcher import ERPMatcher
        print("✅ services.erp_matcher")
        
        from services.vector_store import VectorStore
        print("✅ services.vector_store")
        
        from services.risk_engine import RiskEngine
        print("✅ services.risk_engine")
        
        from services.huggingface_llm import HuggingFaceLLM
        print("✅ services.huggingface_llm")
        
        # Test utils
        from utils.helpers import setup_logging
        print("✅ utils.helpers")
        
        # Test inventory balancer
        from inventory_balancer import InventoryBalancer
        print("✅ inventory_balancer")
        
        print("\n🎉 All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Other error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\nNow testing main.py execution...")
        try:
            import main
            print("✅ main.py imported successfully")
        except Exception as e:
            print(f"❌ main.py import failed: {e}")
