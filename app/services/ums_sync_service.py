"""Incremental Synchronization Service for UMS Announcements.

Coordinates fetching, deduplicating, revising, extracting metadata with Gemini,
and upserting into SQLite and ChromaDB vector index without modifying historical datasets.
"""

import hashlib
import json
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.database import get_db_connection
from app.core.logging_config import logger
from app.models.announcement import RawAnnouncement
from app.services.embedding_service import EmbeddingService
from app.services.extraction_service import ExtractionService
from app.services.ums_source import UMSSourceAdapter
from app.services.vector_store_service import VectorStoreService


class UMSSyncService:
    """Manages incremental synchronization of UMS announcements into SmartNotice."""

    _sync_lock = threading.Lock()

    def __init__(
        self,
        source_adapter: Optional[UMSSourceAdapter] = None,
        extraction_service: Optional[ExtractionService] = None,
        vector_store: Optional[VectorStoreService] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.source = source_adapter or UMSSourceAdapter()
        self.extraction_service = extraction_service or ExtractionService()
        self.vector_store = vector_store or VectorStoreService()
        self.embedding_service = embedding_service or EmbeddingService()

    def is_sync_running(self) -> bool:
        """Check if a sync is currently in progress."""
        if self._sync_lock.locked():
            return True
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM ums_sync_history WHERE status = 'RUNNING'")
        row = cursor.fetchone()
        conn.close()
        return bool(row and row["cnt"] > 0)

    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent sync execution records."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sync_id, started_at, completed_at, status,
                   fetched_count, candidate_count, inserted_count, updated_count,
                   skipped_count, failed_count, indexed_count, message,
                   error_message, triggered_by
            FROM ums_sync_history
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_latest_sync_status(self) -> Optional[Dict[str, Any]]:
        """Get summary of the most recent sync run."""
        history = self.get_sync_history(limit=1)
        return history[0] if history else None

    def get_synced_announcements(self) -> List[RawAnnouncement]:
        """Load all live/synced announcements from the SQLite database."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT announcement_id, title, publication_date, reference_number,
                   full_content, attachment_present, attachment_names,
                   content_hash, source, source_url,
                   is_detail_complete, detail_fetch_error
            FROM live_announcements
            ORDER BY publication_date DESC, created_at DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()

        results: List[RawAnnouncement] = []
        for r in rows:
            attach_names = json.loads(r["attachment_names"]) if r["attachment_names"] else []
            keys = r.keys()
            is_detail_complete = bool(r["is_detail_complete"]) if "is_detail_complete" in keys and r["is_detail_complete"] is not None else True
            detail_fetch_error = r["detail_fetch_error"] if "detail_fetch_error" in keys else None

            results.append(
                RawAnnouncement(
                    announcement_id=r["announcement_id"],
                    title=r["title"],
                    publication_date=r["publication_date"],
                    reference_number=r["reference_number"],
                    full_content=r["full_content"],
                    attachment_present=bool(r["attachment_present"]),
                    attachment_names=attach_names,
                    content_hash=r["content_hash"],
                    source=r["source"] or "ums",
                    source_url=r["source_url"],
                    is_detail_complete=is_detail_complete,
                    detail_fetch_error=detail_fetch_error,
                )
            )
        return results

    def run_sync(self, triggered_by: str = "manual", limit: int = 25) -> Dict[str, Any]:
        """Execute incremental sync by fetching from configured source adapter."""
        raw_list = self.source.fetch_latest_announcements(limit=limit)
        return self.ingest_announcements(raw_list, triggered_by=triggered_by)

    def ingest_announcements(self, raw_list: List[Dict[str, Any]], triggered_by: str = "manual") -> Dict[str, Any]:
        """Ingest, deduplicate, persist, extract metadata, and embed raw announcement records."""
        if not self._sync_lock.acquire(blocking=False):
            raise RuntimeError("Another synchronization operation is already in progress.")

        sync_id = f"SYNC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        started_at = datetime.now().isoformat()

        # Record start in DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ums_sync_history (
                sync_id, started_at, status, triggered_by
            ) VALUES (?, ?, 'RUNNING', ?)
            """,
            (sync_id, started_at, triggered_by),
        )
        conn.commit()
        conn.close()

        metrics = {
            "sync_id": sync_id,
            "started_at": started_at,
            "completed_at": None,
            "status": "RUNNING",
            "message": "Synchronization in progress...",
            "fetched_count": len(raw_list),
            "candidate_count": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "indexed_count": 0,
            "error_message": None,
        }

        try:
            # Pre-load known live announcements to avoid redundant network calls and queries
            conn_pre = get_db_connection()
            cursor_pre = conn_pre.cursor()
            cursor_pre.execute(
                """
                SELECT announcement_id, reference_number, content_hash, revision_count,
                       full_content, is_detail_complete
                FROM live_announcements
                """
            )
            known_rows = cursor_pre.fetchall()
            conn_pre.close()

            known_existing_map: Dict[str, Dict[str, Any]] = {}
            for kr in known_rows:
                k_dict = dict(kr)
                ann_id_key = k_dict.get("announcement_id")
                if ann_id_key:
                    known_existing_map[ann_id_key] = k_dict
                    clean_id = ann_id_key.replace("ANN-UMS-", "")
                    if clean_id:
                        known_existing_map[clean_id] = k_dict
                ref_key = k_dict.get("reference_number")
                if ref_key:
                    known_existing_map[ref_key] = k_dict

            # 1. Enrich any candidate items that require detail fetching, using fast pre-lookup
            if hasattr(self.source, "_enrich_candidates_with_details") and callable(getattr(self.source, "_enrich_candidates_with_details")):
                try:
                    import inspect
                    sig = inspect.signature(self.source._enrich_candidates_with_details)
                    if "known_existing_map" in sig.parameters:
                        enriched = self.source._enrich_candidates_with_details(raw_list, known_existing_map=known_existing_map)
                    else:
                        enriched = self.source._enrich_candidates_with_details(raw_list)
                    if isinstance(enriched, list):
                        raw_list = enriched
                except Exception as e:
                    logger.debug("Candidate enrichment fallback: %s", e)

            metrics["fetched_count"] = len(raw_list)

            # Process each announcement incrementally using batch DB connection
            new_or_updated: List[Tuple[RawAnnouncement, str]] = []  # (ann, 'INSERT'|'UPDATE')
            conn_batch = get_db_connection()
            try:
                for raw_item in raw_list:
                    try:
                        ann = self.source.normalize_announcement(raw_item)
                        metrics["candidate_count"] += 1
                        action = self._persist_announcement_with_conn(ann, conn_batch)
                        if action == "INSERTED":
                            metrics["inserted_count"] += 1
                            new_or_updated.append((ann, "INSERT"))
                        elif action == "UPDATED":
                            metrics["updated_count"] += 1
                            new_or_updated.append((ann, "UPDATE"))
                        else:
                            metrics["skipped_count"] += 1
                    except Exception as exc:
                        logger.error("Error processing announcement item: %s", exc)
                        metrics["failed_count"] += 1
                conn_batch.commit()
            finally:
                conn_batch.close()

            # Connect to AI Pipeline (Extraction & Vector Indexing)
            for ann, action_type in new_or_updated:
                indexed = self._process_ai_pipeline(ann)
                if indexed:
                    metrics["indexed_count"] += 1

            # Determine truthful, nuanced status and user message (Phase 8)
            if metrics["failed_count"] > 0 and metrics["inserted_count"] == 0 and metrics["updated_count"] == 0 and metrics["skipped_count"] == 0:
                metrics["status"] = "FAILED"
                metrics["message"] = f"Failed to ingest announcements ({metrics['failed_count']} error(s) occurred)."
            elif metrics["fetched_count"] == 0:
                metrics["status"] = "EMPTY_SOURCE"
                metrics["message"] = "Source returned 0 announcements. Please verify portal connectivity or session credentials."
            elif metrics["inserted_count"] == 0 and metrics["updated_count"] == 0 and metrics["skipped_count"] > 0:
                metrics["status"] = "UP_TO_DATE"
                metrics["message"] = f"All {metrics['skipped_count']} announcements are already up to date in SmartNotice."
            elif metrics["inserted_count"] > 0 or metrics["updated_count"] > 0:
                metrics["status"] = "SUCCESS"
                summary_parts = []
                if metrics["inserted_count"] > 0:
                    summary_parts.append(f"{metrics['inserted_count']} new")
                if metrics["updated_count"] > 0:
                    summary_parts.append(f"{metrics['updated_count']} revised")
                if metrics["skipped_count"] > 0:
                    summary_parts.append(f"{metrics['skipped_count']} unchanged")
                metrics["message"] = f"Successfully synced: {', '.join(summary_parts)}."
            else:
                metrics["status"] = "SUCCESS"
                metrics["message"] = "Synchronization completed successfully."

        except Exception as exc:
            logger.exception("UMS ingestion failed: %s", exc)
            metrics["status"] = "FAILED"
            metrics["error_message"] = str(exc)
            metrics["message"] = f"Synchronization error: {str(exc)}"

        finally:
            completed_at = datetime.now().isoformat()
            metrics["completed_at"] = completed_at

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE ums_sync_history
                SET completed_at = ?, status = ?, fetched_count = ?,
                    candidate_count = ?, inserted_count = ?, updated_count = ?,
                    skipped_count = ?, failed_count = ?, indexed_count = ?,
                    message = ?, error_message = ?
                WHERE sync_id = ?
                """,
                (
                    completed_at,
                    metrics["status"],
                    metrics["fetched_count"],
                    metrics["candidate_count"],
                    metrics["inserted_count"],
                    metrics["updated_count"],
                    metrics["skipped_count"],
                    metrics["failed_count"],
                    metrics["indexed_count"],
                    metrics["message"],
                    metrics["error_message"],
                    sync_id,
                ),
            )
            conn.commit()
            conn.close()
            self._sync_lock.release()

        return metrics

    def _persist_announcement(self, ann: RawAnnouncement) -> str:
        """Persist announcement in SQLite with deduplication and revision detection."""
        conn = get_db_connection()
        try:
            action = self._persist_announcement_with_conn(ann, conn)
            conn.commit()
            return action
        finally:
            conn.close()

    def _persist_announcement_with_conn(self, ann: RawAnnouncement, conn) -> str:
        """Persist announcement using provided connection for high-throughput batch operations."""
        if not ann.content_hash:
            ann.content_hash = hashlib.sha256(ann.full_content.encode("utf-8")).hexdigest()[:16]

        cursor = conn.cursor()
        # Check by announcement_id or (reference_number when available)
        existing = None
        if ann.announcement_id:
            cursor.execute(
                "SELECT announcement_id, content_hash, revision_count, full_content, is_detail_complete FROM live_announcements WHERE announcement_id = ?",
                (ann.announcement_id,),
            )
            existing = cursor.fetchone()

        if not existing and ann.reference_number:
            cursor.execute(
                "SELECT announcement_id, content_hash, revision_count, full_content, is_detail_complete FROM live_announcements WHERE reference_number = ?",
                (ann.reference_number,),
            )
            existing = cursor.fetchone()

        # Exact match check by content_hash to avoid duplicate inserts
        if not existing:
            cursor.execute(
                "SELECT announcement_id, content_hash, full_content, is_detail_complete FROM live_announcements WHERE content_hash = ?",
                (ann.content_hash,),
            )
            hash_match = cursor.fetchone()
            if hash_match:
                return "SKIPPED"

        if existing:
            # If hash is identical, skip unchanged notice
            if existing["content_hash"] == ann.content_hash:
                return "SKIPPED"

            # Safe protection: do NOT overwrite existing longer/complete content with shorter preview!
            existing_content = existing["full_content"] or ""
            is_existing_complete = bool(existing["is_detail_complete"]) if "is_detail_complete" in existing.keys() else True
            if len(ann.full_content) < len(existing_content) and is_existing_complete and not ann.is_detail_complete:
                logger.info(
                    "Preserving complete content for %s (%d chars); skipping shorter preview (%d chars)",
                    ann.announcement_id,
                    len(existing_content),
                    len(ann.full_content)
                )
                return "SKIPPED"

            # Content revised or repaired! Update existing record and increment revision count
            rev = (existing["revision_count"] or 1) + 1
            cursor.execute(
                """
                UPDATE live_announcements
                SET title = ?, publication_date = ?, full_content = ?,
                    attachment_present = ?, attachment_names = ?,
                    content_hash = ?, source_url = ?, revision_count = ?,
                    is_detail_complete = ?, detail_fetch_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE announcement_id = ?
                """,
                (
                    ann.title,
                    ann.publication_date,
                    ann.full_content,
                    1 if ann.attachment_present else 0,
                    json.dumps(ann.attachment_names),
                    ann.content_hash,
                    ann.source_url,
                    rev,
                    1 if ann.is_detail_complete else 0,
                    ann.detail_fetch_error,
                    existing["announcement_id"],
                ),
            )
            logger.info("Updated announcement %s to revision %d (complete=%s)", ann.announcement_id, rev, ann.is_detail_complete)
            return "UPDATED"

        # Brand new announcement
        cursor.execute(
            """
            INSERT INTO live_announcements (
                announcement_id, source_id, title, publication_date,
                reference_number, full_content, attachment_present,
                attachment_names, content_hash, source, source_url, revision_count,
                is_detail_complete, detail_fetch_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                ann.announcement_id,
                ann.announcement_id.replace("ANN-UMS-", ""),
                ann.title,
                ann.publication_date,
                ann.reference_number,
                ann.full_content,
                1 if ann.attachment_present else 0,
                json.dumps(ann.attachment_names),
                ann.content_hash,
                ann.source or "ums",
                ann.source_url,
                1 if ann.is_detail_complete else 0,
                ann.detail_fetch_error,
            ),
        )
        logger.info("Inserted new live announcement: %s (%s, complete=%s)", ann.announcement_id, ann.title[:40], ann.is_detail_complete)
        return "INSERTED"


    def backfill_incomplete_notices(self, limit: int = 50, force: bool = False) -> Dict[str, Any]:
        """Safe backfill process to repair incomplete records without duplicates or data loss.

        1. Identifies records with missing, incomplete, or suspiciously short content.
        2. Queries authorized detail endpoint or adapter.
        3. Only updates if newly retrieved content is longer and richer than existing.
        4. Re-runs extraction & updates ChromaDB vector index.
        5. Preserves historical dates, ref numbers, and metadata.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        if force:
            cursor.execute(
                """
                SELECT announcement_id, source_id, title, publication_date, reference_number,
                       full_content, attachment_present, attachment_names, source, source_url,
                       is_detail_complete
                FROM live_announcements
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        else:
            cursor.execute(
                """
                SELECT announcement_id, source_id, title, publication_date, reference_number,
                       full_content, attachment_present, attachment_names, source, source_url,
                       is_detail_complete
                FROM live_announcements
                WHERE is_detail_complete = 0 OR length(full_content) < 250 OR full_content = title
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        conn.close()

        scanned = len(rows)
        repaired = 0
        skipped = 0
        failed = 0
        repair_details: List[Dict[str, Any]] = []

        for r in rows:
            ann_id = r["announcement_id"]
            src_id = r["source_id"] or ann_id.replace("ANN-UMS-", "")
            curr_content = r["full_content"] or ""

            try:
                # Attempt detail retrieval
                detail = self.source.fetch_announcement_details(src_id)
                new_content = ""
                if isinstance(detail, dict):
                    new_content = str(
                        detail.get("full_content")
                        or detail.get("NoticeContent")
                        or detail.get("Body")
                        or detail.get("Description")
                        or ""
                    ).strip()
                elif isinstance(detail, str):
                    new_content = detail.strip()

                if new_content and len(new_content) > len(curr_content):
                    # Richer content obtained! Reconstruct RawAnnouncement and update
                    attach_names = json.loads(r["attachment_names"]) if r["attachment_names"] else []
                    if isinstance(detail, dict) and detail.get("attachment_names"):
                        attach_names = detail.get("attachment_names")

                    ann = RawAnnouncement(
                        announcement_id=ann_id,
                        title=r["title"],
                        publication_date=r["publication_date"],
                        reference_number=r["reference_number"],
                        full_content=new_content,
                        attachment_present=bool(attach_names or r["attachment_present"] or (isinstance(detail, dict) and detail.get("attachment_present"))),
                        attachment_names=attach_names,
                        content_hash=hashlib.sha256(new_content.encode("utf-8")).hexdigest(),
                        source=r["source"] or "ums",
                        source_url=r["source_url"],
                        is_detail_complete=True,
                        detail_fetch_error=None,
                    )

                    self._persist_announcement(ann)
                    self._process_ai_pipeline(ann)
                    repaired += 1
                    repair_details.append({
                        "announcement_id": ann_id,
                        "status": "REPAIRED",
                        "prev_length": len(curr_content),
                        "new_length": len(new_content),
                    })
                else:
                    skipped += 1
                    repair_details.append({
                        "announcement_id": ann_id,
                        "status": "SKIPPED",
                        "reason": "Existing content already equal or longer than source detail.",
                    })

            except Exception as exc:
                failed += 1
                logger.warning("Backfill failed for %s: %s", ann_id, exc)
                # Record error in DB without deleting content
                conn_err = get_db_connection()
                c_err = conn_err.cursor()
                c_err.execute(
                    "UPDATE live_announcements SET detail_fetch_error = ? WHERE announcement_id = ?",
                    (f"Backfill error: {str(exc)}", ann_id),
                )
                conn_err.commit()
                conn_err.close()
                repair_details.append({
                    "announcement_id": ann_id,
                    "status": "FAILED",
                    "error": str(exc),
                })

        return {
            "scanned_count": scanned,
            "repaired_count": repaired,
            "enriched_count": repaired,
            "skipped_count": skipped,
            "failed_count": failed,
            "error_count": failed,
            "repair_details": repair_details,
            "message": f"Backfill completed: {repaired} repaired, {skipped} already adequate, {failed} failed.",
        }

    def _process_ai_pipeline(self, ann: RawAnnouncement) -> None:
        """Run extraction and vector embedding for a new or updated announcement."""
        metadata = None
        # 1. Extraction: check cache first, then run extraction with heuristic fallback
        cached = self.extraction_service.get_cached_metadata(ann.content_hash or "")
        if cached:
            metadata = cached
        else:
            try:
                metadata = self.extraction_service.extract_metadata(ann)
            except Exception as exc:
                logger.warning(
                    "Gemini API extraction failed for %s (%s). Using heuristic fallback.",
                    ann.announcement_id,
                    exc,
                )
                metadata = self.extraction_service.fallback_heuristic_extraction(ann)

        # 2. Vector indexing: embed and upsert into ChromaDB
        if settings.AUTO_EMBED_NEW_NOTICES:
            try:
                doc_text = self.vector_store.prepare_document_text(ann, metadata)
                vector = self.embedding_service.embed_text(doc_text)
                chroma_meta = {
                    "announcement_id": ann.announcement_id,
                    "title": ann.title,
                    "publication_date": ann.publication_date,
                    "reference_number": ann.reference_number or "N/A",
                    "category": metadata.category if metadata else "GENERAL",
                    "urgency": metadata.urgency.value if metadata else "LOW",
                    "attachment_present": ann.attachment_present,
                    "source": ann.source or "ums",
                }
                # Upsert into ChromaDB
                self.vector_store.collection.upsert(
                    ids=[ann.announcement_id],
                    embeddings=[vector],
                    documents=[doc_text],
                    metadatas=[chroma_meta],
                )
                logger.info("Upserted %s into ChromaDB vector index.", ann.announcement_id)
                return True
            except Exception as exc:
                logger.warning("Failed to embed announcement %s into ChromaDB: %s", ann.announcement_id, exc)
                return False
        return False
