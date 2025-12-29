"""
Hugo - Inbox Watchdog Agent
Pipeline Orchestrator

Single entry point that orchestrates the entire flow:
1. Parse supplier email
2. Load ERP data
3. Retrieve vector context
4. Perform RAG-based reasoning

Designed for Streamlit integration with graceful fallbacks.
"""

import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from services.delivery_detector import DeliveryDetector
from services.erp_comparer import ERPComparer, ChangeType
from services.rag_memory import RAGMemory
from services.rag_reasoner import assess_risk_json
from services.vertex_ai import is_available
from utils.helpers import setup_logging

logger = setup_logging()


def run_pipeline(
    email_text: str,
    erp_csv_path: str,
    data_path: Optional[str] = None,
    sender: str = "unknown@supplier.com",
    subject: str = "Delivery Update"
) -> dict:
    """
    Run the complete Hugo pipeline.
    
    Orchestrates:
    1. Email parsing (extract order_id, sku, dates)
    2. ERP comparison (match with purchase orders)
    3. Vector context retrieval (RAG)
    4. Risk reasoning (LLM assessment)
    
    Args:
        email_text: Raw supplier email content
        erp_csv_path: Path to material_orders.csv
        data_path: Optional path to data/ folder for RAG context
        sender: Email sender address
        subject: Email subject line
    
    Returns:
        JSON-serializable dict for Streamlit UI:
        {
            "status": "success" | "partial" | "error",
            "order_id": str | null,
            "sku": str | null,
            "supplier_id": str | null,
            "parsing": { ... },
            "erp_comparison": { ... },
            "rag_context": [ ... ],
            "risk_assessment": { ... },
            "warnings": [ ... ],
            "timestamp": str
        }
    """
    result = {
        "status": "success",
        "order_id": None,
        "sku": None,
        "supplier_id": None,
        "parsing": None,
        "erp_comparison": None,
        "rag_context": [],
        "risk_assessment": None,
        "warnings": [],
        "timestamp": datetime.now().isoformat()
    }
    
    # =========================================================================
    # STEP 1: Parse supplier email
    # =========================================================================
    logger.info("Step 1: Parsing supplier email...")
    
    try:
        parsing_result = _parse_email(email_text, sender, subject)
        result["parsing"] = parsing_result
        
        # Extract key fields
        result["order_id"] = parsing_result.get("order_id")
        result["sku"] = parsing_result.get("sku")
        result["supplier_id"] = parsing_result.get("supplier_id")
        
        if not result["order_id"]:
            result["warnings"].append("Could not extract order_id from email")
            result["status"] = "partial"
        
        logger.info(f"  Parsed: order_id={result['order_id']}, sku={result['sku']}")
        
    except Exception as e:
        logger.error(f"Email parsing failed: {e}")
        result["warnings"].append(f"Email parsing failed: {str(e)}")
        result["parsing"] = {"error": str(e), "raw_text": email_text[:500]}
        result["status"] = "partial"
    
    # =========================================================================
    # STEP 2: Load ERP and compare dates
    # =========================================================================
    logger.info("Step 2: Loading ERP and comparing dates...")
    
    erp_comparer = None
    try:
        if Path(erp_csv_path).exists():
            erp_comparer = ERPComparer(erp_csv_path)
            logger.info(f"  Loaded {erp_comparer.get_order_count()} ERP orders")
        else:
            result["warnings"].append(f"ERP file not found: {erp_csv_path}")
            result["status"] = "partial"
    except Exception as e:
        logger.error(f"ERP load failed: {e}")
        result["warnings"].append(f"ERP load failed: {str(e)}")
    
    # Compare if we have order_id and ERP data
    comparison_result = {
        "matched": False,
        "erp_delivery_date": None,
        "supplier_delivery_date": None,
        "delay_days": 0,
        "change_type": "NO_CHANGE",
        "erp_record": None
    }
    
    if result["order_id"] and erp_comparer:
        try:
            supplier_date = result["parsing"].get("new_delivery_date")
            comparison = erp_comparer.compare(
                order_id=result["order_id"],
                supplier_date=supplier_date or datetime.now().isoformat(),
                sku=result["sku"]
            )
            
            comparison_result = {
                "matched": comparison.matched,
                "erp_delivery_date": comparison.erp_delivery_date.isoformat() if comparison.erp_delivery_date else None,
                "supplier_delivery_date": comparison.supplier_delivery_date.isoformat() if comparison.supplier_delivery_date else None,
                "delay_days": comparison.delay_days,
                "change_type": comparison.change_type.value,
                "erp_record": comparison.erp_record
            }
            
            if not comparison.matched:
                result["warnings"].append(f"No ERP record found for order {result['order_id']}")
            
            logger.info(f"  Comparison: {comparison.change_type.value}, delay={comparison.delay_days} days")
            
        except Exception as e:
            logger.error(f"ERP comparison failed: {e}")
            result["warnings"].append(f"ERP comparison failed: {str(e)}")
    
    result["erp_comparison"] = comparison_result
    
    # =========================================================================
    # STEP 3: Retrieve vector context (RAG)
    # =========================================================================
    logger.info("Step 3: Retrieving vector context...")
    
    rag_context = []
    try:
        if data_path and Path(data_path).exists():
            memory = RAGMemory()
            
            # Check if we need to build the store
            if memory.collection.count() == 0:
                logger.info("  Building vector store...")
                memory.build_vector_store(data_path)
            
            # Retrieve context
            rag_context = memory.retrieve_context(
                order_id=result["order_id"],
                sku=result["sku"],
                supplier_id=result["supplier_id"],
                top_k=5
            )
            
            logger.info(f"  Retrieved {len(rag_context)} context documents")
        else:
            # Fallback: try to use existing memory
            try:
                memory = RAGMemory()
                if memory.collection.count() > 0:
                    rag_context = memory.retrieve_context(
                        order_id=result["order_id"],
                        sku=result["sku"],
                        supplier_id=result["supplier_id"],
                        top_k=5
                    )
                    logger.info(f"  Retrieved {len(rag_context)} context documents (existing store)")
            except:
                pass
        
        if not rag_context:
            result["warnings"].append("No relevant context found in vector store")
            
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        result["warnings"].append(f"RAG retrieval failed: {str(e)}")
    
    # Simplify context for JSON output
    result["rag_context"] = [
        {
            "text": ctx.get("text", "")[:300],
            "source_type": ctx.get("metadata", {}).get("source_type", "unknown"),
            "relevance": round(ctx.get("relevance", 0), 3)
        }
        for ctx in rag_context
    ]
    
    # =========================================================================
    # STEP 4: RAG-based risk reasoning
    # =========================================================================
    logger.info("Step 4: Performing risk assessment...")
    
    try:
        # Build email data dict for reasoner
        email_data = {
            "order_id": result["order_id"] or "Unknown",
            "sku": result["sku"] or "Unknown",
            "supplier_id": result["supplier_id"] or "Unknown",
            "subject": subject,
            "body": email_text,
            "new_delivery_date": result["parsing"].get("new_delivery_date") if result["parsing"] else None
        }
        
        risk_result = assess_risk_json(
            email_data=email_data,
            erp_data=comparison_result.get("erp_record"),
            rag_context=rag_context,
            delay_days=comparison_result.get("delay_days", 0),
            change_type=comparison_result.get("change_type", "NO_CHANGE")
        )
        
        result["risk_assessment"] = risk_result
        logger.info(f"  Risk level: {risk_result.get('risk_level')}")
        
    except Exception as e:
        logger.error(f"Risk assessment failed: {e}")
        result["warnings"].append(f"Risk assessment failed: {str(e)}")
        
        # Provide fallback risk assessment
        result["risk_assessment"] = {
            "risk_level": "MEDIUM",
            "explanation": "Unable to complete full analysis. Manual review recommended.",
            "suggested_action": "Review email manually and check ERP system."
        }
    
    # =========================================================================
    # FINALIZE
    # =========================================================================
    if len(result["warnings"]) > 2:
        result["status"] = "partial"
    elif result["warnings"]:
        result["status"] = "partial" if result["status"] != "error" else "error"
    
    logger.info(f"Pipeline complete: status={result['status']}, warnings={len(result['warnings'])}")
    
    return result


def _parse_email(email_text: str, sender: str, subject: str) -> dict:
    """
    Parse supplier email to extract structured data.
    
    Returns dict with:
    - detected: bool
    - order_id: str | None
    - sku: str | None
    - supplier_id: str | None
    - new_delivery_date: str | None
    - change_type: str | None
    - confidence: float
    """
    from models.schemas import Email
    
    # Create Email object for detector
    email = Email(
        message_id=f"pipeline_{datetime.now().timestamp()}",
        thread_id="pipeline_thread",
        sender=sender,
        subject=subject,
        body=email_text,
        received_at=datetime.now(),
        labels=["Pipeline"]
    )
    
    # Use DeliveryDetector
    detector = DeliveryDetector()
    change, _ = detector.detect_changes(email)
    
    # Extract supplier_id from sender if not in email
    supplier_id = None
    import re
    sup_match = re.search(r"SUP-\d+", email_text, re.IGNORECASE)
    if sup_match:
        supplier_id = sup_match.group(0).upper()
    
    # Get SKU - could be list or string
    sku = None
    if change.affected_items:
        sku = change.affected_items[0] if isinstance(change.affected_items, list) else change.affected_items
    
    return {
        "detected": change.detected,
        "order_id": change.po_reference,
        "sku": sku,
        "supplier_id": supplier_id,
        "new_delivery_date": change.new_date.isoformat() if change.new_date else None,
        "original_delivery_date": change.original_date.isoformat() if change.original_date else None,
        "change_type": change.change_type.value if change.change_type else None,
        "delay_days": change.delay_days,
        "reason": change.supplier_reason,
        "confidence": change.confidence
    }


def run_pipeline_from_file(
    email_file_path: str,
    erp_csv_path: str,
    data_path: Optional[str] = None
) -> dict:
    """
    Run pipeline from an email file.
    
    Args:
        email_file_path: Path to .txt or .md email file
        erp_csv_path: Path to material_orders.csv
        data_path: Optional path to data/ folder
    
    Returns:
        Pipeline result dict
    """
    email_path = Path(email_file_path)
    if not email_path.exists():
        return {
            "status": "error",
            "warnings": [f"Email file not found: {email_file_path}"],
            "timestamp": datetime.now().isoformat()
        }
    
    email_text = email_path.read_text(encoding="utf-8")
    
    return run_pipeline(
        email_text=email_text,
        erp_csv_path=erp_csv_path,
        data_path=data_path,
        sender=f"supplier@{email_path.stem}.com",
        subject=email_path.stem.replace("_", " ").title()
    )
