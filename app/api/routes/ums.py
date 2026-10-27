"""FastAPI routes for UMS Source Connector and Synchronization Management."""

import secrets
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging_config import logger
from app.models.announcement import RawAnnouncement
from app.services.ums_source import UMSSourceAdapter
from app.services.ums_sync_service import UMSSyncService

router = APIRouter(prefix="/ums", tags=["UMS Portal Integration & Sync"])

source_adapter = UMSSourceAdapter()
sync_service = UMSSyncService(source_adapter=source_adapter)


class SyncResponse(BaseModel):
    sync_id: str
    started_at: str
    completed_at: Optional[str] = None
    status: str
    message: str = ""
    fetched_count: int
    candidate_count: int = 0
    inserted_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    indexed_count: int = 0
    error_message: Optional[str] = None


class UMSStatusResponse(BaseModel):
    source_name: str
    base_url: str
    connector_mode: str
    status: str
    has_session_credentials: bool
    connection_check: Dict[str, Any]
    last_sync: Optional[Dict[str, Any]] = None
    message: str


def verify_admin_authorization(x_sync_token: Optional[str] = Header(None)) -> bool:
    """Safeguard for administrative sync trigger operations."""
    expected_token = settings.SYNC_ADMIN_KEY

    # In development mode with default token, allow request with audit warning
    if expected_token == "smartnotice-admin-key" and not x_sync_token:
        logger.warning("UMS sync triggered using default development configuration without X-Sync-Token header.")
        return True

    if not x_sync_token or not secrets.compare_digest(x_sync_token, expected_token):
        logger.warning("Unauthorized attempt to trigger UMS sync.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid 'X-Sync-Token' header is required to initiate synchronization.",
        )
    return True


@router.get("/status", response_model=UMSStatusResponse)
def get_ums_status():
    """Report UMS connector configuration, connectivity check, and last sync status."""
    source_status = source_adapter.get_source_status()
    conn_check = source_adapter.check_connection()
    last_sync = sync_service.get_latest_sync_status()

    return {
        "source_name": source_status["source_name"],
        "base_url": source_status["base_url"],
        "connector_mode": source_status["connector_mode"],
        "status": source_status["status"],
        "has_session_credentials": source_status["has_session_credentials"],
        "connection_check": conn_check,
        "last_sync": last_sync,
        "message": source_status["message"],
    }


@router.post("/sync", response_model=SyncResponse)
def trigger_ums_sync(
    limit: int = Query(25, ge=1, le=100, description="Max announcements to fetch"),
    x_sync_token: Optional[str] = Header(None, description="Admin secret token for sync"),
):
    """Trigger an incremental synchronization from LPU UMS.

    Protected with X-Sync-Token admin safeguard.
    Prevents concurrent sync conflicts.
    """
    verify_admin_authorization(x_sync_token)

    if sync_service.is_sync_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A synchronization process is currently in progress. Please wait until it finishes.",
        )

    try:
        result = sync_service.run_sync(triggered_by="api_manual", limit=limit)
        return result
    except PermissionError as pe:
        logger.warning("Permission error during manual sync: %s", pe)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{pe} (Note: Direct backend requests are blocked by Cloudflare Bot Protection. Use '1-Click Browser Sync' or 'Paste Notices' in the portal setup modal)."
        )
    except RuntimeError as re:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(re))
    except Exception as exc:
        logger.exception("Error executing manual sync: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute synchronization: {exc}",
        )


@router.get("/sync/history")
def get_sync_history(limit: int = Query(10, ge=1, le=50)):
    """Retrieve audit history of recent synchronization runs."""
    return sync_service.get_sync_history(limit=limit)


@router.get("/announcements", response_model=List[RawAnnouncement])
def get_synced_announcements():
    """Retrieve live announcements ingested from UMS."""
    return sync_service.get_synced_announcements()


@router.post("/import", response_model=SyncResponse)
def import_live_announcements(
    payload: Any = Body(...),
    x_sync_token: Optional[str] = Header(None),
):
    """Import announcements directly from client session export, raw text, HTML, or update session cookie."""
    verify_admin_authorization(x_sync_token)

    raw_list: List[Dict[str, Any]] = []

    if isinstance(payload, str):
        # Direct string pasted
        raw_list = source_adapter.parse_raw_text(payload)
    elif isinstance(payload, list):
        raw_list = payload
    elif isinstance(payload, dict):
        if "mode" in payload and payload["mode"]:
            source_adapter.connector_mode = str(payload["mode"]).lower()
            logger.info("Updated connector mode to: %s", source_adapter.connector_mode)

        if "cookie" in payload and payload["cookie"]:
            source_adapter.session_cookie = str(payload["cookie"]).strip()
            source_adapter.connector_mode = "live"
            logger.info("Updated UMS session cookie dynamically from import payload.")

        if "raw_text" in payload and payload["raw_text"]:
            raw_list = source_adapter.parse_raw_text(str(payload["raw_text"]))
        elif "text" in payload and payload["text"]:
            raw_list = source_adapter.parse_raw_text(str(payload["text"]))
        elif "html" in payload and payload["html"]:
            raw_list = source_adapter.parse_html(str(payload["html"]))
        else:
            raw_list = payload.get("announcements") or payload.get("data") or payload.get("items") or []
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid payload. Expected JSON list, string, or object with 'announcements', 'raw_text', or 'cookie'."
        )

    if not raw_list and isinstance(payload, dict) and "cookie" in payload:
        # If only cookie was updated, attempt live fetch with the new cookie
        try:
            return sync_service.run_sync(triggered_by="cookie_update", limit=25)
        except PermissionError as pe:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{pe} Direct backend calls are blocked by Cloudflare Bot Protection. Use the 1-Click Browser Sync or Paste Announcements tab instead."
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Sync using cookie failed: {exc}")

    if not raw_list:
        raise HTTPException(
            status_code=400,
            detail="No announcement records could be extracted from payload. Please check format or paste announcement text."
        )

    try:
        return sync_service.ingest_announcements(raw_list, triggered_by="direct_import")
    except RuntimeError as re:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(re))
    except Exception as exc:
        logger.exception("Error importing announcements: %s", exc)
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}")


@router.post("/backfill")
def backfill_incomplete_announcements(
    limit: int = Query(50, ge=1, le=200, description="Max notices to repair"),
    force: bool = Query(False, description="Attempt backfill for all notices, not just flagged ones"),
    x_sync_token: Optional[str] = Header(None),
):
    """Safely backfill incomplete announcement records with full details from source."""
    verify_admin_authorization(x_sync_token)
    return sync_service.backfill_incomplete_notices(limit=limit, force=force)


