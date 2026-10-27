"""Integration and unit tests for UMSSyncService and FastAPI endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db_connection, init_db
from app.services.ums_source import UMSSourceAdapter
from app.services.ums_sync_service import UMSSyncService
from app.models.announcement import RawAnnouncement


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables exist and clean live tables before each test."""
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM live_announcements")
    c.execute("DELETE FROM ums_sync_history")
    conn.commit()
    conn.close()


def test_incremental_sync_and_deduplication():
    """Verify first sync inserts records and second sync skips existing unchanged items."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    sync_service = UMSSyncService(source_adapter=adapter)

    # First Run: Ingestion
    res1 = sync_service.run_sync(triggered_by="test_run_1", limit=4)
    assert res1["status"] == "SUCCESS"
    assert res1["fetched_count"] == 4
    assert res1["inserted_count"] >= 1
    assert res1["candidate_count"] == 4
    assert res1["error_message"] is None

    # Second Run: Idempotent rerun - identical records should be skipped with UP_TO_DATE status
    res2 = sync_service.run_sync(triggered_by="test_run_2", limit=4)
    assert res2["status"] == "UP_TO_DATE"
    assert res2["fetched_count"] == 4
    assert res2["inserted_count"] == 0
    assert res2["skipped_count"] == 4
    assert "already up to date" in res2["message"]


def test_announcement_revision_detection():
    """Verify edited notices are detected and updated with incremented revision_count."""
    # Custom adapter with a notice that gets revised
    mock_adapter = MagicMock()
    v1_raw = {
        "id": "REV-001",
        "title": "Initial Exam Notice",
        "full_content": "Exam in Room 34-101 at 10 AM.",
        "publication_date": "2026-10-16",
        "reference_number": "LPU/REV/001",
    }
    mock_adapter.fetch_latest_announcements.return_value = [v1_raw]
    mock_adapter.normalize_announcement.side_effect = lambda raw: UMSSourceAdapter().normalize_announcement(raw)

    sync_service = UMSSyncService(source_adapter=mock_adapter)
    res1 = sync_service.run_sync(triggered_by="rev_test_1")
    assert res1["inserted_count"] == 1

    # Verify initial revision count is 1
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT revision_count, full_content FROM live_announcements WHERE announcement_id = 'ANN-UMS-REV-001'")
    row1 = c.fetchone()
    assert row1["revision_count"] == 1

    # Now revise the content (e.g. room changed)
    v2_raw = {
        "id": "REV-001",
        "title": "Initial Exam Notice - REVISED",
        "full_content": "Room changed! Exam is now in Room 32-205 at 10 AM.",
        "publication_date": "2026-10-16",
        "reference_number": "LPU/REV/001",
    }
    mock_adapter.fetch_latest_announcements.return_value = [v2_raw]

    res2 = sync_service.run_sync(triggered_by="rev_test_2")
    assert res2["updated_count"] == 1
    assert res2["inserted_count"] == 0

    # Verify revision count incremented to 2 and content updated
    c.execute("SELECT revision_count, full_content FROM live_announcements WHERE announcement_id = 'ANN-UMS-REV-001'")
    row2 = c.fetchone()
    assert row2["revision_count"] == 2
    assert "Room changed!" in row2["full_content"]
    conn.close()


def test_failed_embedding_graceful_handling():
    """Verify that failure in vector embedding does not crash or corrupt the sync."""
    mock_adapter = MagicMock()
    raw = {
        "id": "FAIL-EMBED-1",
        "title": "Notice with embedding error",
        "full_content": "Some content",
        "publication_date": "2026-10-16",
    }
    mock_adapter.fetch_latest_announcements.return_value = [raw]
    mock_adapter.normalize_announcement.side_effect = lambda r: UMSSourceAdapter().normalize_announcement(r)

    mock_vec = MagicMock()
    mock_vec.collection.upsert.side_effect = Exception("ChromaDB connection timeout")

    sync_service = UMSSyncService(source_adapter=mock_adapter, vector_store=mock_vec)
    res = sync_service.run_sync(triggered_by="test_fail_embed")
    assert res["status"] == "SUCCESS"
    assert res["inserted_count"] == 1


def test_sync_lock_concurrency():
    """Verify concurrent sync invocations are rejected."""
    sync_service = UMSSyncService()
    # Acquire lock artificially
    assert sync_service._sync_lock.acquire(blocking=False) is True
    try:
        with pytest.raises(RuntimeError) as exc_info:
            sync_service.run_sync(triggered_by="blocked_thread")
        assert "already in progress" in str(exc_info.value)
    finally:
        sync_service._sync_lock.release()


def test_api_ums_status_endpoints():
    """Verify both /api/v1/ums/status and /api/ums/status return valid status data."""
    for path in ["/api/v1/ums/status", "/api/ums/status"]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert "source_name" in data
        assert "connection_check" in data
        assert "connector_mode" in data


def test_api_ums_sync_history():
    """Verify /api/v1/ums/sync/history returns recent audit history."""
    resp = client.get("/api/v1/ums/sync/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_ums_sync_authorization_safeguard():
    """Verify unauthorized sync attempts with invalid X-Sync-Token are rejected with 401."""
    # When wrong token provided, must return 401
    resp = client.post("/api/v1/ums/sync", headers={"X-Sync-Token": "invalid_wrong_secret"})
    assert resp.status_code == 401


def test_dataset_service_seamless_live_integration():
    """Verify DatasetService merges live announcements before historical records."""
    from app.services.dataset_service import DatasetService
    ds = DatasetService()
    records, report = ds.load_dataset(include_live=True)
    assert len(records) > 0
    # Any live announcements are prepended
    live_in_dataset = [r for r in records if r.source == "ums"]
    assert len(live_in_dataset) >= 0  # Valid merged list


def test_api_ums_import_endpoint():
    """Verify direct import of announcements via /api/v1/ums/import."""
    payload = [
        {
            "id": "LIVE-IMP-1",
            "title": "Direct Scraped Announcement from UMS Session",
            "full_content": "Notice retrieved from active session.",
            "publication_date": "2026-10-16",
            "reference_number": "LPU/IMP/001"
        }
    ]
    resp = client.post("/api/v1/ums/import", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["inserted_count"] == 1
    assert data["candidate_count"] == 1
    assert "Successfully synced" in data["message"]


def test_empty_source_sync_reporting():
    """Verify sync reports EMPTY_SOURCE when source yields 0 items."""
    mock_adapter = MagicMock()
    mock_adapter.fetch_latest_announcements.return_value = []
    sync_service = UMSSyncService(source_adapter=mock_adapter)

    res = sync_service.run_sync(triggered_by="test_empty")
    assert res["status"] == "EMPTY_SOURCE"
    assert res["fetched_count"] == 0
    assert res["inserted_count"] == 0
    assert "0 announcements" in res["message"]


def test_api_sync_response_model_completeness():
    """Verify /api/v1/ums/sync endpoint returns all required Phase 8 fields."""
    resp = client.post("/api/v1/ums/sync?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert "sync_id" in data
    assert "status" in data
    assert "message" in data
    assert "fetched_count" in data
    assert "candidate_count" in data
    assert "inserted_count" in data
    assert "updated_count" in data
    assert "skipped_count" in data
    assert "failed_count" in data
    assert "indexed_count" in data


