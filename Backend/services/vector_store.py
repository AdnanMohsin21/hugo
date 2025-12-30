"""
Hugo - Vector Store Service
Handles vector storage and retrieval for RAG.
"""

import csv
import logging
from typing import Optional, List, Dict
from pathlib import Path

from models.schemas import DeliveryChange, PurchaseOrder, HistoricalContext
from utils.helpers import setup_logging

logger = setup_logging()


class VectorStore:
    """Vector store for RAG functionality."""
    
    def __init__(self):
        """Initialize vector store."""
        self.documents = self._load_documents()
        logger.info(f"Vector store initialized with {len(self.documents)} documents")
    
    def _load_documents(self) -> List[Dict]:
        """Load documents from data files."""
        documents = []
        
        # Load from material master
        material_file = Path("hugo_data_samples/material_master.csv")
        if material_file.exists():
            try:
                import csv
                with open(material_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        doc = {
                            'text': f"Material {row.get('part_id', '')}: {row.get('part_name', '')}",
                            'metadata': {
                                'source_type': 'material_master',
                                'part_id': row.get('part_id', ''),
                                'part_name': row.get('part_name', '')
                            }
                        }
                        documents.append(doc)
            except Exception as e:
                logger.error(f"Error loading material master: {e}")
        
        return documents
    
    def build_context(self, change: DeliveryChange, po: Optional[PurchaseOrder]) -> Optional[HistoricalContext]:
        """Build historical context for delivery change."""
        # Mock context for demo
        return HistoricalContext(
            supplier_id=po.supplier_id if po else "UNKNOWN",
            supplier_name=po.supplier_name if po else "Unknown",
            total_past_issues=3,
            supplier_reliability_score=0.8,
            avg_resolution_time_days=2.5
        )
    
    def query_similar(self, query: str, n_results: int = 5) -> List[Dict]:
        """Query for similar documents."""
        # Simple mock implementation
        return self.documents[:n_results]
    
    def get_supplier_history(self, supplier_id: str) -> List[Dict]:
        """Get supplier history."""
        # Mock implementation
        return [
            {
                'incident_id': 'inc_001',
                'date': '2024-01-15',
                'type': 'delay',
                'resolution': 'Rescheduled delivery'
            }
        ]
    
    def add_incident(self, incident_id: str, supplier_id: str, supplier_name: str, 
                    incident_type: str, description: str, delay_days: int, 
                    resolution: str, impact_score: float) -> None:
        """Add incident to history."""
        logger.info(f"Added incident {incident_id} to history")
