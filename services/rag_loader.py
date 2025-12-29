"""
Hugo - Inbox Watchdog Agent
RAG Data Loader

Loads supplier emails and ERP purchase orders from CSV files,
creates embeddings using Vertex AI, and stores in ChromaDB for RAG.

Hackathon-friendly: Simple CSV loading with minimal dependencies.
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings
from services.vertex_ai import generate_embedding, generate_embeddings_batch, is_available
from utils.helpers import setup_logging

logger = setup_logging()


class RAGLoader:
    """
    Loads and indexes data for Retrieval-Augmented Generation.
    
    Features:
    - Load supplier emails from CSV
    - Load ERP purchase orders from CSV
    - Create embeddings using Vertex AI
    - Store in ChromaDB for similarity search
    - Search by order_id and sku
    """
    
    def __init__(self, collection_name: str = "hugo_rag"):
        """
        Initialize RAG loader with ChromaDB.
        
        Args:
            collection_name: Name for the ChromaDB collection
        """
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self._use_vertex_embeddings = is_available()
        self._initialize_store()
    
    def _initialize_store(self) -> None:
        """Initialize ChromaDB client."""
        try:
            db_path = Path(settings.VECTOR_DB_PATH)
            db_path.mkdir(parents=True, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=str(db_path),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            
            # Create collection (recreate if exists for fresh load)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Hugo RAG - Emails and POs"}
            )
            
            logger.info(f"RAG collection '{self.collection_name}' ready ({self.collection.count()} docs)")
            
            if self._use_vertex_embeddings:
                logger.info("Using Vertex AI embeddings")
            else:
                logger.info("Using ChromaDB default embeddings (Vertex AI not available)")
                
        except Exception as e:
            logger.error(f"Failed to initialize RAG store: {e}")
            raise
    
    def load_emails_csv(self, csv_path: str) -> int:
        """
        Load supplier emails from CSV file.
        
        Expected CSV columns:
        - email_id: Unique identifier
        - sender: Sender email address
        - subject: Email subject
        - body: Email body text
        - order_id: Related order/PO number (optional)
        - sku: Related SKU (optional)
        - received_date: Date received (optional)
        
        Args:
            csv_path: Path to CSV file
        
        Returns:
            Number of records loaded
        """
        path = Path(csv_path)
        if not path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return 0
        
        records = []
        ids = []
        documents = []
        metadatas = []
        
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                email_id = row.get("email_id", f"email_{len(records)}")
                
                # Create text chunk from email
                text_chunk = self._email_to_chunk(row)
                
                ids.append(f"email_{email_id}")
                documents.append(text_chunk)
                metadatas.append({
                    "type": "email",
                    "email_id": email_id,
                    "sender": row.get("sender", ""),
                    "subject": row.get("subject", ""),
                    "order_id": row.get("order_id", ""),
                    "sku": row.get("sku", ""),
                    "received_date": row.get("received_date", "")
                })
                records.append(row)
        
        if not records:
            logger.warning(f"No records found in {csv_path}")
            return 0
        
        # Generate embeddings and store
        self._store_documents(ids, documents, metadatas)
        
        logger.info(f"Loaded {len(records)} emails from {csv_path}")
        return len(records)
    
    def load_purchase_orders_csv(self, csv_path: str) -> int:
        """
        Load ERP purchase orders from CSV file.
        
        Expected CSV columns:
        - order_id: PO number
        - supplier_name: Supplier name
        - supplier_email: Supplier email
        - sku: SKU or comma-separated list
        - description: Item description
        - quantity: Order quantity
        - order_date: Date ordered
        - expected_delivery: Expected delivery date
        - status: Order status
        
        Args:
            csv_path: Path to CSV file
        
        Returns:
            Number of records loaded
        """
        path = Path(csv_path)
        if not path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return 0
        
        records = []
        ids = []
        documents = []
        metadatas = []
        
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                order_id = row.get("order_id", f"po_{len(records)}")
                
                # Create text chunk from PO
                text_chunk = self._po_to_chunk(row)
                
                ids.append(f"po_{order_id}")
                documents.append(text_chunk)
                metadatas.append({
                    "type": "purchase_order",
                    "order_id": order_id,
                    "supplier_name": row.get("supplier_name", ""),
                    "supplier_email": row.get("supplier_email", ""),
                    "sku": row.get("sku", ""),
                    "expected_delivery": row.get("expected_delivery", ""),
                    "status": row.get("status", "open")
                })
                records.append(row)
        
        if not records:
            logger.warning(f"No records found in {csv_path}")
            return 0
        
        # Generate embeddings and store
        self._store_documents(ids, documents, metadatas)
        
        logger.info(f"Loaded {len(records)} purchase orders from {csv_path}")
        return len(records)
    
    def _email_to_chunk(self, row: dict) -> str:
        """
        Convert email row to text chunk for embedding.
        
        Args:
            row: CSV row dict
        
        Returns:
            Text chunk summarizing the email
        """
        parts = []
        
        if row.get("subject"):
            parts.append(f"Email Subject: {row['subject']}")
        
        if row.get("sender"):
            parts.append(f"From: {row['sender']}")
        
        if row.get("order_id"):
            parts.append(f"Order Reference: {row['order_id']}")
        
        if row.get("sku"):
            parts.append(f"SKU: {row['sku']}")
        
        if row.get("body"):
            # Take first 500 chars of body
            body = row["body"][:500]
            parts.append(f"Content: {body}")
        
        return " | ".join(parts)
    
    def _po_to_chunk(self, row: dict) -> str:
        """
        Convert purchase order row to text chunk for embedding.
        
        Args:
            row: CSV row dict
        
        Returns:
            Text chunk summarizing the PO
        """
        parts = []
        
        if row.get("order_id"):
            parts.append(f"Purchase Order: {row['order_id']}")
        
        if row.get("supplier_name"):
            parts.append(f"Supplier: {row['supplier_name']}")
        
        if row.get("sku"):
            parts.append(f"SKU: {row['sku']}")
        
        if row.get("description"):
            parts.append(f"Items: {row['description']}")
        
        if row.get("quantity"):
            parts.append(f"Quantity: {row['quantity']}")
        
        if row.get("expected_delivery"):
            parts.append(f"Expected Delivery: {row['expected_delivery']}")
        
        if row.get("status"):
            parts.append(f"Status: {row['status']}")
        
        return " | ".join(parts)
    
    def _store_documents(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict]
    ) -> None:
        """
        Store documents with embeddings in ChromaDB.
        
        Uses Vertex AI embeddings if available, otherwise falls back
        to ChromaDB's default embedding function.
        """
        if self._use_vertex_embeddings:
            # Generate embeddings using Vertex AI
            logger.info(f"Generating Vertex AI embeddings for {len(documents)} documents...")
            try:
                embeddings = generate_embeddings_batch(documents, task_type="RETRIEVAL_DOCUMENT")
                
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
            except Exception as e:
                logger.warning(f"Vertex AI embedding failed: {e}, falling back to default")
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
        else:
            # Use ChromaDB default embeddings
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
    
    def search_by_order_id(self, order_id: str, n_results: int = 5) -> list[dict]:
        """
        Search for documents related to a specific order ID.
        
        Args:
            order_id: Order/PO number to search for
            n_results: Maximum results to return
        
        Returns:
            List of matching documents with metadata
        """
        # Search by text similarity first
        query = f"Order {order_id} PO {order_id}"
        
        if self._use_vertex_embeddings:
            try:
                query_embedding = generate_embedding(query, task_type="RETRIEVAL_QUERY")
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"]
                )
            except Exception as e:
                logger.warning(f"Vertex AI query failed: {e}, using text query")
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"]
                )
        else:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
        
        # Also filter by metadata if exact match needed
        filtered = []
        for i in range(len(results["ids"][0])):
            doc = {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            }
            # Prioritize exact order_id matches
            if doc["metadata"].get("order_id", "").upper() == order_id.upper():
                filtered.insert(0, doc)
            else:
                filtered.append(doc)
        
        return filtered[:n_results]
    
    def search_by_sku(self, sku: str, n_results: int = 5) -> list[dict]:
        """
        Search for documents related to a specific SKU.
        
        Args:
            sku: SKU to search for
            n_results: Maximum results to return
        
        Returns:
            List of matching documents with metadata
        """
        query = f"SKU {sku} product {sku}"
        
        if self._use_vertex_embeddings:
            try:
                query_embedding = generate_embedding(query, task_type="RETRIEVAL_QUERY")
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"]
                )
            except Exception as e:
                logger.warning(f"Vertex AI query failed: {e}, using text query")
                results = self.collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"]
                )
        else:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
        
        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        
        return formatted
    
    def search_similar(self, query_text: str, n_results: int = 5) -> list[dict]:
        """
        General similarity search.
        
        Args:
            query_text: Text to search for
            n_results: Maximum results to return
        
        Returns:
            List of similar documents with metadata
        """
        if self._use_vertex_embeddings:
            try:
                query_embedding = generate_embedding(query_text, task_type="RETRIEVAL_QUERY")
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"]
                )
            except Exception as e:
                logger.warning(f"Vertex AI query failed: {e}, using text query")
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"]
                )
        else:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
        
        # Format results
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "similarity": 1 - results["distances"][0][i]
            })
        
        return formatted
    
    def get_stats(self) -> dict:
        """Get collection statistics."""
        return {
            "collection_name": self.collection_name,
            "total_documents": self.collection.count() if self.collection else 0,
            "using_vertex_embeddings": self._use_vertex_embeddings
        }
    
    def clear(self) -> None:
        """Clear all documents from the collection."""
        if self.client:
            try:
                self.client.delete_collection(self.collection_name)
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Hugo RAG - Emails and POs"}
                )
                logger.info(f"Cleared collection '{self.collection_name}'")
            except Exception as e:
                logger.error(f"Failed to clear collection: {e}")
