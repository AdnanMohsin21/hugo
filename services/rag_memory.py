"""
Hugo - Inbox Watchdog Agent
RAG Memory - Voltway Dataset Integration

Builds a Retrieval-Augmented Generation memory layer from:
- CSV files (material_orders, suppliers, stock_levels, etc.)
- Text files (supplier emails, product specs)

Provides context retrieval for risk assessment and reasoning.
"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime

import pandas as pd
import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings
from services.vertex_ai import generate_embedding, generate_embeddings_batch, is_available
from utils.helpers import setup_logging

logger = setup_logging()

# Batch size for embedding generation (Vertex AI limit)
EMBEDDING_BATCH_SIZE = 100


class RAGMemory:
    """
    RAG Memory layer for Hugo agent.
    
    Loads Voltway dataset (CSVs + text files), converts to natural language
    chunks, generates embeddings, and stores for retrieval.
    """
    
    def __init__(self, collection_name: str = "hugo_memory"):
        """
        Initialize RAG Memory.
        
        Args:
            collection_name: ChromaDB collection name
        """
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self._use_vertex = is_available()
        self._initialize_store()
    
    def _initialize_store(self) -> None:
        """Initialize ChromaDB persistent storage."""
        db_path = Path(settings.VECTOR_DB_PATH)
        db_path.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Hugo RAG Memory - Voltway Dataset"}
        )
        
        logger.info(f"RAG Memory initialized: {self.collection.count()} docs")
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def build_vector_store(self, data_path: str) -> dict:
        """
        Build vector store from Voltway dataset.
        
        Args:
            data_path: Path to data/ folder containing CSVs and subfolders
        
        Returns:
            Dict with counts of loaded records by type
        """
        data_dir = Path(data_path)
        if not data_dir.exists():
            raise FileNotFoundError(f"Data path not found: {data_path}")
        
        logger.info(f"Building vector store from: {data_path}")
        stats = {}
        
        # Clear existing data for fresh build
        self._clear_collection()
        
        # 1. Load CSV files
        csv_loaders = {
            "material_orders.csv": self._load_material_orders,
            "suppliers.csv": self._load_suppliers,
            "stock_levels.csv": self._load_stock_levels,
            "stock_movements.csv": self._load_stock_movements,
            "material_master.csv": self._load_material_master,
            "dispatch_parameters.csv": self._load_dispatch_parameters,
            "sales_orders.csv": self._load_sales_orders,
        }
        
        for filename, loader in csv_loaders.items():
            csv_path = data_dir / filename
            if csv_path.exists():
                count = loader(csv_path)
                stats[filename] = count
                logger.info(f"Loaded {filename}: {count} records")
            else:
                logger.warning(f"CSV not found: {filename}")
        
        # 2. Load text files from emails/ folder
        emails_dir = data_dir / "emails"
        if emails_dir.exists():
            count = self._load_text_folder(emails_dir, "email")
            stats["emails"] = count
            logger.info(f"Loaded emails/: {count} files")
        
        # 3. Load text files from specs/ folder
        specs_dir = data_dir / "specs"
        if specs_dir.exists():
            count = self._load_text_folder(specs_dir, "spec")
            stats["specs"] = count
            logger.info(f"Loaded specs/: {count} files")
        
        logger.info(f"Vector store built: {self.collection.count()} total documents")
        return stats
    
    def retrieve_context(
        self,
        order_id: Optional[str] = None,
        sku: Optional[str] = None,
        supplier_id: Optional[str] = None,
        query_text: Optional[str] = None,
        top_k: int = 5
    ) -> list[dict]:
        """
        Retrieve relevant context from RAG memory.
        
        Args:
            order_id: Filter by order ID (e.g., "MO-1042")
            sku: Filter by SKU (e.g., "CTRL-1001")
            supplier_id: Filter by supplier ID (e.g., "SUP-01")
            query_text: Optional text for semantic search
            top_k: Number of results to return
        
        Returns:
            List of context documents with metadata
        """
        # Build search query from filters
        query_parts = []
        if order_id:
            query_parts.append(f"order {order_id}")
        if sku:
            query_parts.append(f"SKU {sku} component")
        if supplier_id:
            query_parts.append(f"supplier {supplier_id}")
        if query_text:
            query_parts.append(query_text)
        
        if not query_parts:
            query_parts.append("delivery order supplier")
        
        query = " ".join(query_parts)
        
        # Build metadata filter
        where_filter = self._build_where_filter(order_id, sku, supplier_id)
        
        # Query with embedding or text
        try:
            if self._use_vertex:
                query_embedding = generate_embedding(query, task_type="RETRIEVAL_QUERY")
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )
            else:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )
        except Exception as e:
            logger.error(f"Query failed: {e}")
            # Fallback without filter
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
        
        # Format results
        context = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                context.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "relevance": 1 - results["distances"][0][i]
                })
        
        return context
    
    # =========================================================================
    # CSV LOADERS - Convert rows to natural language chunks
    # =========================================================================
    
    def _load_material_orders(self, csv_path: Path) -> int:
        """Load material_orders.csv (ERP purchase orders)."""
        df = pd.read_csv(csv_path)
        
        chunks = []
        for _, row in df.iterrows():
            order_id = self._safe_get(row, "order_id", "")
            sku = self._safe_get(row, "sku", "")
            supplier_id = self._safe_get(row, "supplier_id", "")
            qty = self._safe_get(row, "ordered_qty", "")
            date = self._safe_get(row, "delivery_date", "")
            status = self._safe_get(row, "order_status", "")
            
            text = f"Purchase order {order_id} for {qty} units of {sku} from supplier {supplier_id}. "
            text += f"Expected delivery: {date}. Status: {status}."
            
            chunks.append({
                "id": f"po_{order_id}_{sku}",
                "text": text,
                "metadata": {
                    "source_type": "material_order",
                    "order_id": str(order_id),
                    "sku": str(sku),
                    "supplier_id": str(supplier_id),
                    "delivery_date": str(date),
                    "status": str(status)
                }
            })
        
        self._store_chunks(chunks)
        return len(chunks)
    
    def _load_suppliers(self, csv_path: Path) -> int:
        """Load suppliers.csv."""
        df = pd.read_csv(csv_path)
        
        chunks = []
        for _, row in df.iterrows():
            supplier_id = self._safe_get(row, "supplier_id", "")
            name = self._safe_get(row, "supplier_name", "")
            country = self._safe_get(row, "country", "")
            reliability = self._safe_get(row, "reliability_score", "")
            
            text = f"Supplier {supplier_id} ({name}) based in {country}. "
            text += f"Reliability score: {reliability}."
            
            chunks.append({
                "id": f"sup_{supplier_id}",
                "text": text,
                "metadata": {
                    "source_type": "supplier",
                    "supplier_id": str(supplier_id),
                    "supplier_name": str(name),
                    "country": str(country),
                    "reliability_score": str(reliability)
                }
            })
        
        self._store_chunks(chunks)
        return len(chunks)
    
    def _load_stock_levels(self, csv_path: Path) -> int:
        """Load stock_levels.csv."""
        df = pd.read_csv(csv_path)
        
        chunks = []
        for _, row in df.iterrows():
            sku = self._safe_get(row, "sku", "")
            on_hand = self._safe_get(row, "on_hand", 0)
            reserved = self._safe_get(row, "reserved", 0)
            warehouse = self._safe_get(row, "warehouse", "")
            
            text = f"Stock for {sku} in {warehouse}: {on_hand} on hand, {reserved} reserved. "
            text += f"Available: {int(on_hand) - int(reserved) if on_hand and reserved else 'unknown'}."
            
            chunks.append({
                "id": f"stock_{sku}_{warehouse}",
                "text": text,
                "metadata": {
                    "source_type": "stock_level",
                    "sku": str(sku),
                    "warehouse": str(warehouse),
                    "on_hand": str(on_hand),
                    "reserved": str(reserved)
                }
            })
        
        self._store_chunks(chunks)
        return len(chunks)
    
    def _load_stock_movements(self, csv_path: Path) -> int:
        """Load stock_movements.csv."""
        df = pd.read_csv(csv_path)
        
        chunks = []
        for _, row in df.iterrows():
            movement_id = self._safe_get(row, "movement_id", "")
            sku = self._safe_get(row, "sku", "")
            qty = self._safe_get(row, "qty", "")
            movement_type = self._safe_get(row, "movement_type", "")
            date = self._safe_get(row, "movement_date", "")
            
            direction = "received" if movement_type == "IN" else "shipped out"
            text = f"Stock movement {movement_id}: {qty} units of {sku} {direction} on {date}."
            
            chunks.append({
                "id": f"mov_{movement_id}",
                "text": text,
                "metadata": {
                    "source_type": "stock_movement",
                    "movement_id": str(movement_id),
                    "sku": str(sku),
                    "movement_type": str(movement_type),
                    "movement_date": str(date)
                }
            })
        
        self._store_chunks(chunks)
        return len(chunks)
    
    def _load_material_master(self, csv_path: Path) -> int:
        """Load material_master.csv."""
        df = pd.read_csv(csv_path)
        
        chunks = []
        for _, row in df.iterrows():
            sku = self._safe_get(row, "sku", "")
            description = self._safe_get(row, "description", "")
            category = self._safe_get(row, "category", "")
            cost = self._safe_get(row, "unit_cost", "")
            
            text = f"Material {sku}: {description}. Category: {category}. Unit cost: ${cost}."
            
            chunks.append({
                "id": f"mat_{sku}",
                "text": text,
                "metadata": {
                    "source_type": "material_master",
                    "sku": str(sku),
                    "description": str(description),
                    "category": str(category),
                    "unit_cost": str(cost)
                }
            })
        
        self._store_chunks(chunks)
        return len(chunks)
    
    def _load_dispatch_parameters(self, csv_path: Path) -> int:
        """Load dispatch_parameters.csv."""
        df = pd.read_csv(csv_path)
        
        chunks = []
        for _, row in df.iterrows():
            sku = self._safe_get(row, "sku", "")
            reorder = self._safe_get(row, "reorder_point", "")
            safety = self._safe_get(row, "safety_stock", "")
            lot_size = self._safe_get(row, "lot_size", "")
            
            text = f"Dispatch parameters for {sku}: reorder point {reorder}, "
            text += f"safety stock {safety}, lot size {lot_size}."
            
            chunks.append({
                "id": f"disp_{sku}",
                "text": text,
                "metadata": {
                    "source_type": "dispatch_parameters",
                    "sku": str(sku),
                    "reorder_point": str(reorder),
                    "safety_stock": str(safety),
                    "lot_size": str(lot_size)
                }
            })
        
        self._store_chunks(chunks)
        return len(chunks)
    
    def _load_sales_orders(self, csv_path: Path) -> int:
        """Load sales_orders.csv."""
        df = pd.read_csv(csv_path)
        
        chunks = []
        for _, row in df.iterrows():
            so_id = self._safe_get(row, "sales_order_id", "")
            sku = self._safe_get(row, "sku", "")
            qty = self._safe_get(row, "qty", "")
            channel = self._safe_get(row, "channel", "")
            date = self._safe_get(row, "requested_delivery_date", "")
            
            text = f"Sales order {so_id}: {qty} units of {sku} via {channel}. "
            text += f"Requested delivery: {date}."
            
            chunks.append({
                "id": f"so_{so_id}_{sku}",
                "text": text,
                "metadata": {
                    "source_type": "sales_order",
                    "sales_order_id": str(so_id),
                    "sku": str(sku),
                    "channel": str(channel),
                    "requested_delivery_date": str(date)
                }
            })
        
        self._store_chunks(chunks)
        return len(chunks)
    
    # =========================================================================
    # TEXT FILE LOADERS
    # =========================================================================
    
    def _load_text_folder(self, folder_path: Path, source_type: str) -> int:
        """
        Load all text/markdown files from a folder.
        
        Args:
            folder_path: Path to folder containing .txt or .md files
            source_type: "email" or "spec"
        
        Returns:
            Number of files loaded
        """
        chunks = []
        
        for file_path in folder_path.iterdir():
            if file_path.suffix.lower() in [".txt", ".md", ".markdown"]:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    
                    # Extract metadata from content
                    metadata = self._extract_text_metadata(content, file_path.name, source_type)
                    
                    # Create chunk (limit content length)
                    text = self._create_text_chunk(content, file_path.name, source_type)
                    
                    chunks.append({
                        "id": f"{source_type}_{file_path.stem}",
                        "text": text[:2000],  # Limit chunk size
                        "metadata": metadata
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to load {file_path}: {e}")
        
        if chunks:
            self._store_chunks(chunks)
        
        return len(chunks)
    
    def _extract_text_metadata(self, content: str, filename: str, source_type: str) -> dict:
        """Extract metadata from text file content."""
        metadata = {
            "source_type": source_type,
            "filename": filename,
            "order_id": "",
            "sku": "",
            "supplier_id": ""
        }
        
        # Try to extract order IDs (MO-XXXX pattern)
        import re
        order_matches = re.findall(r"MO-\d+", content, re.IGNORECASE)
        if order_matches:
            metadata["order_id"] = order_matches[0]
        
        # Try to extract SKUs (common patterns)
        sku_matches = re.findall(r"[A-Z]{2,4}-\d{4}", content)
        if sku_matches:
            metadata["sku"] = sku_matches[0]
        
        # Try to extract supplier IDs
        sup_matches = re.findall(r"SUP-\d+", content, re.IGNORECASE)
        if sup_matches:
            metadata["supplier_id"] = sup_matches[0]
        
        return metadata
    
    def _create_text_chunk(self, content: str, filename: str, source_type: str) -> str:
        """Create a natural language chunk from text file."""
        # Take first 1500 chars and summarize
        content_preview = content[:1500].strip()
        
        if source_type == "email":
            return f"Supplier email ({filename}): {content_preview}"
        elif source_type == "spec":
            return f"Product specification ({filename}): {content_preview}"
        else:
            return f"Document ({filename}): {content_preview}"
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _store_chunks(self, chunks: list[dict]) -> None:
        """Store chunks with embeddings in ChromaDB."""
        if not chunks:
            return
        
        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        
        # Generate embeddings in batches
        if self._use_vertex:
            try:
                all_embeddings = []
                for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
                    batch = texts[i:i + EMBEDDING_BATCH_SIZE]
                    embeddings = generate_embeddings_batch(batch, task_type="RETRIEVAL_DOCUMENT")
                    all_embeddings.extend(embeddings)
                
                self.collection.add(
                    ids=ids,
                    embeddings=all_embeddings,
                    documents=texts,
                    metadatas=metadatas
                )
                return
            except Exception as e:
                logger.warning(f"Vertex embedding failed: {e}, using default")
        
        # Fallback to ChromaDB default embeddings
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
    
    def _safe_get(self, row, key: str, default=""):
        """Safely get value from DataFrame row."""
        try:
            val = row.get(key, default)
            if pd.isna(val):
                return default
            return val
        except:
            return default
    
    def _build_where_filter(
        self,
        order_id: Optional[str],
        sku: Optional[str],
        supplier_id: Optional[str]
    ) -> Optional[dict]:
        """Build ChromaDB where filter from optional params."""
        conditions = []
        
        if order_id:
            conditions.append({"order_id": order_id})
        if sku:
            conditions.append({"sku": sku})
        if supplier_id:
            conditions.append({"supplier_id": supplier_id})
        
        if len(conditions) == 0:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$or": conditions}
    
    def _clear_collection(self) -> None:
        """Clear all documents from collection."""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Hugo RAG Memory - Voltway Dataset"}
            )
            logger.info("Cleared existing RAG memory")
        except Exception as e:
            logger.warning(f"Could not clear collection: {e}")
    
    def get_stats(self) -> dict:
        """Get collection statistics."""
        return {
            "collection": self.collection_name,
            "total_documents": self.collection.count() if self.collection else 0,
            "using_vertex_embeddings": self._use_vertex
        }


# =========================================================================
# CONVENIENCE FUNCTIONS (Module-level API)
# =========================================================================

_memory_instance: Optional[RAGMemory] = None


def build_vector_store(data_path: str) -> dict:
    """
    Build vector store from Voltway dataset.
    
    Args:
        data_path: Path to data/ folder
    
    Returns:
        Dict with load statistics
    """
    global _memory_instance
    _memory_instance = RAGMemory()
    return _memory_instance.build_vector_store(data_path)


def retrieve_context(
    order_id: Optional[str] = None,
    sku: Optional[str] = None,
    supplier_id: Optional[str] = None,
    query_text: Optional[str] = None,
    top_k: int = 5
) -> list[dict]:
    """
    Retrieve relevant context from RAG memory.
    
    Args:
        order_id: Filter by order ID
        sku: Filter by SKU
        supplier_id: Filter by supplier ID
        query_text: Optional text for semantic search
        top_k: Number of results
    
    Returns:
        List of context documents
    """
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = RAGMemory()
    return _memory_instance.retrieve_context(order_id, sku, supplier_id, query_text, top_k)
