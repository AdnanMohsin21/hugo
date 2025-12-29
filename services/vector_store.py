"""
Hugo - Inbox Watchdog Agent
Vector Store Service

ChromaDB-based vector store for RAG (Retrieval Augmented Generation).
Stores and retrieves historical supplier delivery context.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, List

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings
from models.schemas import HistoricalContext, DeliveryChange, PurchaseOrder
from utils.helpers import setup_logging

logger = setup_logging()

# -------------------------------------------------------------------
# Sample historical data (used ONLY for demo + offline testing)
# -------------------------------------------------------------------

SAMPLE_HISTORY = [
    {
        "id": "hist_001",
        "supplier_id": "SUP-001",
        "supplier_name": "ACME Supplies",
        "incident_date": "2024-09-15",
        "incident_type": "delay",
        "description": "7-day delay due to port congestion. Affected 3 POs worth $45,000.",
        "delay_days": 7,
        "resolution": "Expedited shipping arranged",
        "impact_score": 0.6,
    },
    {
        "id": "hist_002",
        "supplier_id": "SUP-001",
        "supplier_name": "ACME Supplies",
        "incident_date": "2024-06-20",
        "incident_type": "partial_shipment",
        "description": "Partial shipment, remaining items delayed two weeks.",
        "delay_days": 14,
        "resolution": "Production schedule adjusted",
        "impact_score": 0.4,
    },
    {
        "id": "hist_003",
        "supplier_id": "SUP-003",
        "supplier_name": "Tech Components",
        "incident_date": "2024-10-01",
        "incident_type": "delay",
        "description": "Critical component shortage caused 3-week delay.",
        "delay_days": 21,
        "resolution": "Alternative supplier sourced",
        "impact_score": 0.9,
    },
]

# -------------------------------------------------------------------
# Vector Store
# -------------------------------------------------------------------

class VectorStore:
    """
    Vector store for historical supplier context using ChromaDB.
    Designed to run safely WITHOUT network access during tests.
    """

    def __init__(self) -> None:
        self.client = None
        self.collection = None
        self._initialize_store()

    # -------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------

    def _initialize_store(self) -> None:
        try:
            db_path = Path(settings.VECTOR_DB_PATH)
            db_path.mkdir(parents=True, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=str(db_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )

            # 🔥 CRITICAL: Disable embedding function (offline-safe)
            self.collection = self.client.get_or_create_collection(
                name=settings.VECTOR_COLLECTION_NAME,
                metadata={"description": "Supplier delivery history"},
                embedding_function=None,
            )

            if self.collection.count() == 0:
                self._seed_sample_data()

            logger.info(
                "Vector store initialized with %d documents",
                self.collection.count(),
            )

        except Exception as e:
            logger.warning(
                "Vector store initialization failed. Running in degraded mode. Error: %s",
                str(e),
            )
            self.collection = None

    def _seed_sample_data(self) -> None:
        ids, documents, metadatas = [], [], []

        for item in SAMPLE_HISTORY:
            ids.append(item["id"])
            documents.append(item["description"])
            metadatas.append(
                {
                    "supplier_id": item["supplier_id"],
                    "supplier_name": item["supplier_name"],
                    "incident_date": item["incident_date"],
                    "incident_type": item["incident_type"],
                    "delay_days": item["delay_days"],
                    "resolution": item["resolution"],
                    "impact_score": item["impact_score"],
                }
            )

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def query_similar(
        self,
        query_text: str,
        supplier_id: Optional[str] = None,
        n_results: int = 5,
    ) -> List[dict]:
        """
        Query for similar historical incidents.

        ALWAYS returns a list.
        NEVER raises.
        NEVER makes network calls.
        """

        if not self.collection or not query_text:
            return []

        try:
            where = {"supplier_id": supplier_id} if supplier_id else None

            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            dists = results.get("distances", [])

            if not docs or not docs[0]:
                return []

            incidents = []
            for i in range(len(docs[0])):
                incidents.append(
                    {
                        "description": docs[0][i],
                        "metadata": metas[0][i],
                        "similarity": 1 - dists[0][i],
                    }
                )

            return incidents

        except Exception as e:
            logger.warning(
                "Vector retrieval failed. Returning empty list. Error: %s",
                str(e),
            )
            return []

    def get_supplier_history(self, supplier_id: str) -> List[dict]:
        if not self.collection or not supplier_id:
            return []

        try:
            results = self.collection.get(
                where={"supplier_id": supplier_id},
                include=["documents", "metadatas"],
            )

            return [
                {
                    "description": results["documents"][i],
                    "metadata": results["metadatas"][i],
                }
                for i in range(len(results["documents"]))
            ]

        except Exception:
            return []

    # -------------------------------------------------------------------
    # Context Builder (RAG Output)
    # -------------------------------------------------------------------

    def build_context(
        self,
        change: DeliveryChange,
        po: Optional[PurchaseOrder] = None,
    ) -> HistoricalContext:

        supplier_id = po.supplier_id if po else None

        query_parts = []
        if change.change_type:
            query_parts.append(change.change_type.value)
        if change.supplier_reason:
            query_parts.append(change.supplier_reason)

        query = " ".join(query_parts) if query_parts else "delivery delay"

        similar = self.query_similar(query, supplier_id)
        supplier_history = (
            self.get_supplier_history(supplier_id) if supplier_id else similar
        )

        total_issues = len(supplier_history)
        avg_delay = (
            sum(
                inc.get("metadata", {}).get("delay_days", 0)
                for inc in supplier_history
            )
            / max(total_issues, 1)
        )

        if supplier_history:
            avg_impact = sum(
                inc.get("metadata", {}).get("impact_score", 0.5)
                for inc in supplier_history
            ) / total_issues
            reliability = 1 - avg_impact
        else:
            reliability = 0.5

        resolutions = list(
            {
                inc.get("metadata", {}).get("resolution", "")
                for inc in supplier_history
                if inc.get("metadata", {}).get("resolution")
            }
        )

        return HistoricalContext(
            similar_incidents=similar[:3],
            supplier_reliability_score=reliability,
            avg_delay_days=avg_delay,
            total_past_issues=total_issues,
            resolution_patterns=resolutions[:5],
        )
