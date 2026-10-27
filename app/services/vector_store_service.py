import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
# pyrefly: ignore[missing-import]
import chromadb

from app.core.config import settings
from app.core.logging_config import logger
from app.core.database import get_db_connection
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata
from app.services.embedding_service import EmbeddingService

COLLECTION_NAME = "lpu_announcements"

class VectorStoreService:
    """Manages persistent ChromaDB vector index for announcement documents."""

    def __init__(self):
        self.chroma_path = Path(settings.CHROMA_PATH)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.chroma_path))
        self.embedding_service = EmbeddingService()
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)

    def get_index_status(self) -> Dict[str, Any]:
        """Get status of persistent vector index."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM index_metadata")
        meta = {row["key"]: row["value"] for row in cursor.fetchall()}
        conn.close()

        count = self.collection.count()
        return {
            "total_indexed_documents": count,
            "chroma_path": str(self.chroma_path),
            "collection_name": COLLECTION_NAME,
            "embedding_model": meta.get("embedding_model", settings.GEMINI_EMBEDDING_MODEL),
            "embedding_dimension": int(meta.get("embedding_dimension", settings.EMBEDDING_DIMENSION)),
            "last_indexed_at": meta.get("last_indexed_at", "Never")
        }

    def verify_index_compatibility(self) -> Tuple[bool, str]:
        """Check if index is compatible with current embedding dimension."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM index_metadata WHERE key = 'embedding_dimension'")
        row = cursor.fetchone()
        conn.close()

        if row and row["value"]:
            indexed_dim = int(row["value"])
            if indexed_dim != settings.EMBEDDING_DIMENSION:
                return False, f"Indexed dimension ({indexed_dim}) differs from current config ({settings.EMBEDDING_DIMENSION}). Please rebuild index."

        return True, "Index compatible"

    def prepare_document_text(self, ann: RawAnnouncement, metadata: Optional[ExtractedAnnouncementMetadata] = None) -> str:
        """Combine title, metadata summary, and full content for embedding document text."""
        parts = [
            f"Title: {ann.title}",
            f"Date: {ann.publication_date}",
            f"Reference: {ann.reference_number or 'N/A'}"
        ]
        if metadata:
            parts.append(f"Category: {metadata.category}")
            parts.append(f"Summary: {metadata.summary}")
            if metadata.topics:
                parts.append(f"Topics: {', '.join(metadata.topics)}")
            if metadata.location:
                parts.append(f"Location: {metadata.location}")
            if metadata.room:
                parts.append(f"Room: {metadata.room}")

        parts.append(f"Content: {ann.full_content}")
        return "\n".join(parts)

    def prepare_chroma_metadata(self, ann: RawAnnouncement, metadata: Optional[ExtractedAnnouncementMetadata] = None) -> Dict[str, Any]:
        """Prepare string/int/bool metadata dictionary for ChromaDB filtering."""
        meta: Dict[str, Any] = {
            "announcement_id": ann.announcement_id,
            "title": ann.title[:200],
            "publication_date": ann.publication_date,
            "reference_number": ann.reference_number or "",
            "attachment_present": ann.attachment_present,
            "attachment_names": ", ".join(ann.attachment_names) if ann.attachment_names else "",
            "content_hash": ann.content_hash or ""
        }

        if metadata:
            meta.update({
                "category": metadata.category or "GENERAL",
                "urgency": metadata.urgency.value if hasattr(metadata.urgency, "value") else str(metadata.urgency),
                "global_importance": metadata.global_importance.value if hasattr(metadata.global_importance, "value") else str(metadata.global_importance),
                "decision_completeness": metadata.decision_completeness.value if hasattr(metadata.decision_completeness, "value") else str(metadata.decision_completeness),
                "target_program": metadata.target_program or "",
                "target_department": metadata.target_department or "",
                "action_required": metadata.action_required
            })
        else:
            meta.update({
                "category": "GENERAL",
                "urgency": "LOW",
                "global_importance": "LOW",
                "decision_completeness": "ATTACHMENT_MISSING" if ann.attachment_present else "COMPLETE",
                "target_program": "",
                "target_department": "",
                "action_required": False
            })

        return meta

    def add_or_update_announcements(
        self,
        announcements: List[RawAnnouncement],
        extracted_map: Optional[Dict[str, ExtractedAnnouncementMetadata]] = None,
        force_reindex: bool = False
    ) -> Tuple[int, int]:
        """Incrementally index announcements into ChromaDB. Returns (added_count, skipped_count)."""
        extracted_map = extracted_map or {}

        existing_ids = set(self.collection.get()["ids"]) if not force_reindex else set()

        ids_to_add: List[str] = []
        embeddings_to_add: List[List[float]] = []
        metadatas_to_add: List[Dict[str, Any]] = []
        documents_to_add: List[str] = []

        skipped_count = 0

        for ann in announcements:
            if not force_reindex and ann.announcement_id in existing_ids:
                skipped_count += 1
                continue

            metadata = extracted_map.get(ann.announcement_id)
            doc_text = self.prepare_document_text(ann, metadata)
            embedding = self.embedding_service.embed_text(doc_text)
            chroma_meta = self.prepare_chroma_metadata(ann, metadata)

            ids_to_add.append(ann.announcement_id)
            embeddings_to_add.append(embedding)
            metadatas_to_add.append(chroma_meta)
            documents_to_add.append(doc_text)

        if ids_to_add:
            self.collection.upsert(
                ids=ids_to_add,
                embeddings=embeddings_to_add,
                metadatas=metadatas_to_add,
                documents=documents_to_add
            )
            # Update index metadata in SQLite
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO index_metadata (key, value) VALUES ('embedding_model', ?)",
                (settings.GEMINI_EMBEDDING_MODEL,)
            )
            cursor.execute(
                "INSERT OR REPLACE INTO index_metadata (key, value) VALUES ('embedding_dimension', ?)",
                (str(settings.EMBEDDING_DIMENSION),)
            )
            cursor.execute(
                "INSERT OR REPLACE INTO index_metadata (key, value) VALUES ('last_indexed_at', datetime('now'))"
            )
            conn.commit()
            conn.close()

            logger.info("Successfully indexed %d new/updated announcements into ChromaDB (%d skipped).", len(ids_to_add), skipped_count)

        return len(ids_to_add), skipped_count
