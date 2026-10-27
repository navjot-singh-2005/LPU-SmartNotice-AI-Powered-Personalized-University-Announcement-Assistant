from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from app.core.logging_config import logger
from app.services.dataset_service import DatasetService
from app.services.retrieval_service import RetrievalService
from app.services.extraction_service import ExtractionService
from app.models.announcement import AnnouncementDetail, RawAnnouncement

router = APIRouter(prefix="/announcements", tags=["Announcements"])

dataset_service = DatasetService()
retrieval_service = RetrievalService()
extraction_service = ExtractionService()

@router.get("", response_model=dict)
def get_announcements(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    attachment_only: bool = False
):
    """Retrieve paginated list of announcements with optional search filter."""
    announcements, _ = dataset_service.load_dataset()

    filtered = announcements
    if attachment_only:
        filtered = [a for a in filtered if a.attachment_present]

    if search:
        s_lower = search.lower()
        filtered = [
            a for a in filtered
            if s_lower in a.title.lower() or s_lower in a.full_content.lower() or (a.reference_number and s_lower in a.reference_number.lower())
        ]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        "items": [item.model_dump() for item in page_items]
    }

@router.get("/search")
def search_announcements(
    q: str = Query(..., min_length=2),
    top_k: int = Query(50, ge=1, le=100),
    category: Optional[str] = None,
    urgency: Optional[str] = None,
    attachment_only: bool = False,
    sort_by: str = Query("relevance", pattern="^(relevance|newest|oldest)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=50)
):
    """Perform hybrid search (semantic + lexical) over announcements with rich filters, sorting, and pagination."""
    import re
    from datetime import datetime

    def _parse_iso(d_str: str) -> str:
        if not d_str:
            return "1970-01-01"
        s = str(d_str).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            return s[:10]
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            month, day, year = m.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        m2 = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})", s)
        if m2:
            day, month, year = m2.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        for fmt in ("%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%b %d, %Y"):
            try:
                return datetime.strptime(s[:11], fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return s

    announcements, _ = dataset_service.load_dataset()
    results = retrieval_service.search(
        query=q,
        top_k=top_k,
        category_filter=category,
        raw_announcements=announcements
    )

    filtered = results
    if urgency:
        u_upper = urgency.strip().upper()
        filtered = [r for r in filtered if r.get("urgency", "").upper() == u_upper]

    if attachment_only:
        filtered = [r for r in filtered if r.get("attachment_present")]

    # Sorting
    if sort_by == "newest":
        filtered.sort(key=lambda r: _parse_iso(r.get("publication_date", "")), reverse=True)
    elif sort_by == "oldest":
        filtered.sort(key=lambda r: _parse_iso(r.get("publication_date", "")))
    # Default is "relevance" (already ranked by RRF score)

    total = len(filtered)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_results = filtered[start_idx:end_idx]

    return {
        "query": q,
        "count": len(page_results),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        "results": page_results
    }

@router.get("/deadlines")
def get_upcoming_deadlines(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    include_expired: bool = False
):
    """Retrieve announcements with extracted deadlines, sorted chronologically."""
    announcements, _ = dataset_service.load_dataset()
    from datetime import datetime
    today_iso = datetime.now().strftime("%Y-%m-%d")

    deadline_items = []
    for ann in announcements:
        meta = extraction_service.get_cached_metadata(ann.content_hash or "")
        deadline_val = meta.deadline if meta and meta.deadline else None

        if not deadline_val and ("deadline" in ann.full_content.lower() or "last date" in ann.full_content.lower()):
            import re
            m = re.search(r"(?:last date|deadline)[:\s]+(\d{1,2}[-/\.]\w{3,}[-/\.]\d{2,4}|\d{4}-\d{2}-\d{2})", ann.full_content, re.IGNORECASE)
            if m:
                deadline_val = m.group(1)

        if deadline_val:
            from app.services.personalization_service import PersonalizationService
            ps = PersonalizationService()
            iso_deadline = ps.parse_date_to_iso(deadline_val)
            is_expired = bool(iso_deadline < today_iso)
            if not include_expired and is_expired:
                continue

            deadline_items.append({
                "announcement_id": ann.announcement_id,
                "title": ann.title,
                "publication_date": ann.publication_date,
                "deadline": deadline_val,
                "iso_deadline": iso_deadline,
                "is_expired": is_expired,
                "category": meta.category if meta else "GENERAL",
                "urgency": meta.urgency.value if meta and hasattr(meta.urgency, "value") else "LOW",
                "source": ann.source or "historical",
                "source_url": ann.source_url
            })

    # Sort primarily by iso_deadline ascending (nearest deadline first)
    deadline_items.sort(key=lambda x: x["iso_deadline"])

    total = len(deadline_items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = deadline_items[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        "items": page_items
    }

@router.get("/{announcement_id}", response_model=AnnouncementDetail)
def get_announcement_by_id(announcement_id: str):
    """Retrieve detailed announcement by ID along with extracted structured metadata."""
    announcements, _ = dataset_service.load_dataset()
    target = next((a for a in announcements if a.announcement_id == announcement_id), None)

    if not target:
        raise HTTPException(status_code=404, detail=f"Announcement {announcement_id} not found.")

    # Fetch cached or fallback metadata
    meta = extraction_service.get_cached_metadata(target.content_hash or "")
    if not meta:
        meta = extraction_service.fallback_heuristic_extraction(target)

    return AnnouncementDetail(
        announcement_id=target.announcement_id,
        title=target.title,
        publication_date=target.publication_date,
        reference_number=target.reference_number,
        full_content=target.full_content,
        attachment_present=target.attachment_present,
        attachment_names=target.attachment_names,
        source=target.source or "historical",
        source_url=target.source_url,
        is_detail_complete=getattr(target, "is_detail_complete", True),
        detail_fetch_error=getattr(target, "detail_fetch_error", None),
        metadata=meta
    )

@router.post("/{announcement_id}/refresh-details", response_model=AnnouncementDetail)
def refresh_announcement_details(announcement_id: str):
    """Attempt on-demand retrieval of full announcement content from source."""
    from app.services.ums_source import UMSSourceAdapter
    from app.services.ums_sync_service import UMSSyncService
    sync_svc = UMSSyncService()

    # If live notice, run targeted repair
    clean_id = announcement_id.replace("ANN-UMS-", "")
    try:
        detail = sync_svc.source.fetch_announcement_details(clean_id)
        if detail and isinstance(detail, dict):
            new_content = str(
                detail.get("full_content")
                or detail.get("NoticeContent")
                or detail.get("Body")
                or detail.get("Description")
                or ""
            ).strip()
            if new_content:
                ann = RawAnnouncement(
                    announcement_id=announcement_id,
                    title=detail.get("title") or "UMS Announcement",
                    publication_date=detail.get("publication_date") or "2026-10-27",
                    reference_number=detail.get("reference_number"),
                    full_content=new_content,
                    attachment_present=bool(detail.get("attachment_present")),
                    attachment_names=detail.get("attachment_names") or [],
                    source="ums",
                    source_url=detail.get("source_url"),
                    is_detail_complete=True,
                    detail_fetch_error=None
                )
                sync_svc._persist_announcement(ann)
                sync_svc._process_ai_pipeline(ann)
                dataset_service.clear_cache()
    except Exception as exc:
        logger.warning("On-demand refresh failed for %s: %s", announcement_id, exc)

    return get_announcement_by_id(announcement_id)
