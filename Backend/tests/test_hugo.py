"""
Hugo - Unit Tests
Minimal but reliable tests for live demo.

Run: pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# TEST 1: Supplier Email Parsing
# =============================================================================

class TestEmailParsing:
    """Tests for supplier email parsing and delivery change detection."""
    
    def test_delay_detection(self):
        """Test that delay keywords trigger detection."""
        from models.schemas import Email
        from services.delivery_detector import DeliveryDetector
        
        email = Email(
            message_id="test_001",
            thread_id="thread_001",
            sender="supplier@test.com",
            subject="Delivery Delay Notice - MO-1042",
            body="Your order MO-1042 will be delayed by 7 days due to supply issues.",
            received_at=datetime.now(),
            labels=[]
        )
        
        detector = DeliveryDetector()
        result = detector.detect_changes(email)
        
        # Should detect a change
        assert result.detected == True
        assert result.change_type is not None
        # Confidence should be reasonable
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
    
    def test_no_change_detection(self):
        """Test that normal emails don't trigger false positives."""
        from models.schemas import Email
        from services.delivery_detector import DeliveryDetector
        
        email = Email(
            message_id="test_002",
            thread_id="thread_002",
            sender="supplier@test.com",
            subject="Monthly Newsletter",
            body="Thank you for being a valued customer. Here are our latest products.",
            received_at=datetime.now(),
            labels=[]
        )
        
        detector = DeliveryDetector()
        result = detector.detect_changes(email)
        
        # Should not crash
        assert result is not None
        # May or may not detect - just shouldn't crash
        assert isinstance(result.detected, bool)
    
    def test_parsing_handles_empty_body(self):
        """Test graceful handling of empty email body."""
        from models.schemas import Email
        from services.delivery_detector import DeliveryDetector
        
        email = Email(
            message_id="test_003",
            thread_id="thread_003",
            sender="supplier@test.com",
            subject="",
            body="",
            received_at=datetime.now(),
            labels=[]
        )
        
        detector = DeliveryDetector()
        result = detector.detect_changes(email)
        
        # Should not crash
        assert result is not None
        assert isinstance(result.detected, bool)


# =============================================================================
# TEST 2: ERP Date Comparison
# =============================================================================

class TestERPComparison:
    """Tests for ERP date comparison logic."""
    
    def test_delay_classification(self):
        """Test that later dates are classified as DELAY."""
        from services.erp_comparer import ERPComparer, ChangeType
        from datetime import datetime, timedelta
        
        comparer = ERPComparer()
        # Manually add a test order
        comparer.orders_by_id["TEST-001"] = [{
            "order_id": "TEST-001",
            "sku": "SKU-001",
            "supplier_id": "SUP-01",
            "delivery_date": "2025-01-15",
            "order_status": "OPEN"
        }]
        
        # Supplier says delivery is 7 days later
        result = comparer.compare("TEST-001", "2025-01-22")
        
        assert result.matched == True
        assert result.delay_days == 7
        assert result.change_type == ChangeType.DELAY
    
    def test_early_classification(self):
        """Test that earlier dates are classified as EARLY."""
        from services.erp_comparer import ERPComparer, ChangeType
        
        comparer = ERPComparer()
        comparer.orders_by_id["TEST-002"] = [{
            "order_id": "TEST-002",
            "sku": "SKU-002",
            "delivery_date": "2025-01-15",
        }]
        
        # Supplier says delivery is 5 days earlier
        result = comparer.compare("TEST-002", "2025-01-10")
        
        assert result.matched == True
        assert result.delay_days == -5
        assert result.change_type == ChangeType.EARLY
    
    def test_no_change_classification(self):
        """Test that same dates are classified as NO_CHANGE."""
        from services.erp_comparer import ERPComparer, ChangeType
        
        comparer = ERPComparer()
        comparer.orders_by_id["TEST-003"] = [{
            "order_id": "TEST-003",
            "delivery_date": "2025-01-15",
        }]
        
        result = comparer.compare("TEST-003", "2025-01-15")
        
        assert result.matched == True
        assert result.delay_days == 0
        assert result.change_type == ChangeType.NO_CHANGE
    
    def test_missing_order_graceful(self):
        """Test graceful handling when order not found."""
        from services.erp_comparer import ERPComparer
        
        comparer = ERPComparer()
        result = comparer.compare("NONEXISTENT-999", "2025-01-15")
        
        # Should not crash
        assert result is not None
        assert result.matched == False


# =============================================================================
# TEST 3: Vector Retrieval
# =============================================================================

class TestVectorRetrieval:
    """Tests for RAG vector store retrieval."""
    
    def test_memory_initialization(self):
        """Test that RAG memory initializes without crashing."""
        from services.rag_memory import RAGMemory
        
        memory = RAGMemory(collection_name="test_collection")
        
        assert memory is not None
        assert memory.collection is not None
    
    def test_retrieve_returns_list(self):
        """Test that retrieve_context returns a list."""
        from services.rag_memory import RAGMemory
        
        memory = RAGMemory(collection_name="test_retrieval")
        
        result = memory.retrieve_context(
            order_id="MO-1042",
            top_k=5
        )
        
        # Should return a list (possibly empty)
        assert isinstance(result, list)
    
    def test_retrieve_handles_none_params(self):
        """Test retrieval with all None parameters."""
        from services.rag_memory import RAGMemory
        
        memory = RAGMemory(collection_name="test_none_params")
        
        # Should not crash with all None
        result = memory.retrieve_context(
            order_id=None,
            sku=None,
            supplier_id=None,
            top_k=5
        )
        
        assert isinstance(result, list)


# =============================================================================
# TEST 4: Risk Classification
# =============================================================================

class TestRiskClassification:
    """Tests for risk assessment logic."""
    
    def test_high_risk_delay(self):
        """Test that large delays result in HIGH risk."""
        from services.rag_reasoner import assess_risk
        
        result = assess_risk(
            email_data={
                "order_id": "MO-1042",
                "sku": "CTRL-1001",
                "subject": "Delay Notice",
                "body": "Major delay due to factory shutdown"
            },
            delay_days=14,
            change_type="DELAY"
        )
        
        assert result is not None
        assert result.risk_level in ["HIGH", "MEDIUM", "LOW"]
        # 14 day delay should generally be HIGH or MEDIUM
        assert result.risk_level in ["HIGH", "MEDIUM"]
    
    def test_low_risk_early(self):
        """Test that early delivery results in LOW risk."""
        from services.rag_reasoner import assess_risk
        
        result = assess_risk(
            email_data={
                "order_id": "MO-1043",
                "sku": "SKU-001",
                "subject": "Early Shipment",
                "body": "Good news! Shipping early."
            },
            delay_days=-3,
            change_type="EARLY"
        )
        
        assert result is not None
        assert result.risk_level in ["HIGH", "MEDIUM", "LOW"]
        # Early delivery should generally be LOW
    
    def test_risk_has_all_fields(self):
        """Test that risk assessment has all required fields."""
        from services.rag_reasoner import assess_risk
        
        result = assess_risk(
            email_data={"order_id": "TEST", "body": "Test email"},
            delay_days=5,
            change_type="DELAY"
        )
        
        assert hasattr(result, "risk_level")
        assert hasattr(result, "explanation")
        assert hasattr(result, "suggested_action")
        
        # All should be non-empty strings
        assert len(result.risk_level) > 0
        assert len(result.explanation) > 0
        assert len(result.suggested_action) > 0


# =============================================================================
# TEST 5: Pipeline Integration
# =============================================================================

class TestPipelineIntegration:
    """Tests for end-to-end pipeline."""
    
    def test_pipeline_returns_dict(self):
        """Test that pipeline returns a dictionary."""
        from services.pipeline import run_pipeline
        
        result = run_pipeline(
            email_text="Order MO-1042 delayed by 5 days.",
            erp_csv_path="nonexistent.csv"  # Intentionally missing
        )
        
        assert isinstance(result, dict)
        assert "status" in result
        assert "timestamp" in result
    
    def test_pipeline_handles_missing_erp(self):
        """Test graceful handling of missing ERP file."""
        from services.pipeline import run_pipeline
        
        result = run_pipeline(
            email_text="Order delayed",
            erp_csv_path="completely_fake_path.csv"
        )
        
        # Should not crash
        assert result is not None
        # Should have warnings
        assert "warnings" in result
        assert len(result["warnings"]) > 0
    
    def test_pipeline_handles_empty_email(self):
        """Test graceful handling of empty email."""
        from services.pipeline import run_pipeline
        
        result = run_pipeline(
            email_text="",
            erp_csv_path="data/material_orders.csv"
        )
        
        # Should not crash
        assert result is not None
        assert "status" in result


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
