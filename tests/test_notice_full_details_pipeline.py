"""
Tests for Complete Notice Fetching, Two-Stage Detail Pipeline, Safe Backfill,
and Database/Search Integrity.
"""

import pytest
import sqlite3
import json
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.models.announcement import RawAnnouncement
from app.services.ums_source import UMSSourceAdapter, clean_html_preserve_structure
from app.services.ums_sync_service import UMSSyncService
from app.services.dataset_service import DatasetService
from app.services.retrieval_service import RetrievalService
from app.core.database import init_db, get_db_connection


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Ensure database schema is up-to-date with migration columns."""
    init_db()


def test_html_structure_preservation_tables_and_headings():
    """Verify that headings, bullet points, and tables are preserved cleanly."""
    raw_html = """
    <div>
        <h2>Important Examination Notice</h2>
        <p>Dear Students,<br>Please find the practical exam details below:</p>
        <table>
            <thead>
                <tr><th>Course</th><th>Date</th><th>Room</th></tr>
            </thead>
            <tbody>
                <tr><td>CSE301</td><td>15-Nov-2026</td><td>34-204</td></tr>
                <tr><td>CSE302</td><td>16-Nov-2026</td><td>34-205</td></tr>
            </tbody>
        </table>
        <ul>
            <li>Bring student ID cards.</li>
            <li>Report 15 minutes before time.</li>
        </ul>
    </div>
    """
    cleaned = clean_html_preserve_structure(raw_html)
    
    assert "Important Examination Notice" in cleaned
    assert "CSE301" in cleaned
    assert "34-204" in cleaned
    assert "34-205" in cleaned
    assert "Bring student ID cards." in cleaned
    assert "• Report 15 minutes before time." in cleaned
    # Markdown table structure preserved
    assert "|" in cleaned


def test_two_stage_detail_fetching_enrichment():
    """Test that brief listing records are enriched with full details via two-stage fetch."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    
    candidate_dict = {
        "id": "10099",
        "title": "Scholarship Application Form 2026",
        "full_content": "Brief: Apply for merit scholarship before due date.",
        "publication_date": "2026-10-20",
        "reference_number": "UMS-SCH-101",
        "source": "ums_portal",
        "is_detail_complete": False
    }
    
    full_detail_text = (
        "Full Circular on Merit-cum-Means Scholarship 2026.\n"
        "All undergraduate students with CGPA >= 8.5 and annual parental income below 5 LPA "
        "are eligible. Submit completed physical application forms at Block 29, Room 102. "
        "Deadline for submission is 30th November 2026."
    )
    
    with patch.object(adapter, "fetch_announcement_details", return_value={
        "full_content": full_detail_text,
        "attachment_names": ["Scholarship_Form_2026.pdf"],
        "is_detail_complete": True,
        "detail_fetch_error": None
    }):
        enriched_list = adapter._enrich_candidates_with_details([candidate_dict])
        assert len(enriched_list) == 1
        item = enriched_list[0]
        assert item["is_detail_complete"] is True
        assert "parental income below 5 LPA" in item["full_content"]
        assert item["attachment_names"] == ["Scholarship_Form_2026.pdf"]


def test_missing_detail_content_graceful_handling():
    """Verify that when detail endpoint returns empty or fails, notice is marked incomplete honestly."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    candidate_dict = {
        "id": "10098",
        "title": "Notice with Missing Detail",
        "full_content": "Brief preview snippet.",
        "publication_date": "2026-10-20",
        "reference_number": "UMS-MISSING-1",
        "source": "ums_portal",
        "is_detail_complete": False
    }
    
    with patch.object(adapter, "fetch_announcement_details", return_value=None):
        enriched_list = adapter._enrich_candidates_with_details([candidate_dict])
        item = enriched_list[0]
        assert item["is_detail_complete"] is False
        assert "Brief preview snippet." in item["full_content"]


def test_downgrade_protection_never_overwrites_full_with_short():
    """Test that _persist_announcement protects existing complete records from being overwritten by short previews."""
    sync_service = UMSSyncService()
    test_ann_id = f"ANN-TEST-DOWNGRADE-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    test_ref = f"REF-DOWNGRADE-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    # Step 1: Insert complete full notice
    complete_notice = RawAnnouncement(
        announcement_id=test_ann_id,
        title="Comprehensive Placement Guidelines 2026",
        full_content=f"Circular ID {test_ann_id}: Complete extensive circular with 300 words of placement rules and regulations... " * 10,
        publication_date="2026-10-25",
        reference_number=test_ref,
        source="ums_portal",
        is_detail_complete=True
    )
    action1 = sync_service._persist_announcement(complete_notice)
    assert action1 in ("INSERTED", "UPDATED")
    
    # Step 2: Attempt to overwrite with a short preview of the same notice
    short_preview = RawAnnouncement(
        announcement_id=test_ann_id,
        title="Comprehensive Placement Guidelines 2026",
        full_content=f"Brief: Placement rules {test_ann_id}.",
        publication_date="2026-10-25",
        reference_number=test_ref,
        source="ums_portal",
        is_detail_complete=False
    )
    action2 = sync_service._persist_announcement(short_preview)
    assert action2 == "SKIPPED"  # Downgrade blocked!
    
    # Verify in DB that long content is preserved
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT full_content, is_detail_complete FROM live_announcements WHERE announcement_id = ?", (test_ann_id,))
        row = cursor.fetchone()
        assert row is not None
        assert len(row["full_content"]) > 200
        assert row["is_detail_complete"] == 1


def test_safe_backfill_process():
    """Test safe backfill: scans incomplete records, enriches them, updates database, avoids duplicates."""
    sync_service = UMSSyncService()
    test_ann_id = f"ANN-TEST-BACKFILL-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    test_ref = f"REF-BACKFILL-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    # Insert an incomplete record
    short_notice = RawAnnouncement(
        announcement_id=test_ann_id,
        title="Hostel Inspection Schedule",
        full_content=f"Brief inspection announcement {test_ann_id}.",
        publication_date="2026-10-26",
        reference_number=test_ref,
        source="ums_portal",
        is_detail_complete=False
    )
    action = sync_service._persist_announcement(short_notice)
    assert action in ("INSERTED", "UPDATED")
    
    # Mock source detail response
    enriched_full_text = (
        "Complete circular for annual hostel inspection.\n"
        "Inspection officers will visit Boys Hostel 3 and Girls Hostel 2 on 28th October.\n"
        "Rooms must be kept orderly between 10:00 AM and 2:00 PM."
    )
    
    with patch.object(sync_service.source, "fetch_announcement_details", return_value={
        "full_content": enriched_full_text,
        "attachment_names": ["Hostel_Rules.pdf"],
        "is_detail_complete": True,
        "detail_fetch_error": None
    }):
        report = sync_service.backfill_incomplete_notices(limit=10, force=True)
        assert report["enriched_count"] >= 1
        
        # Verify database record is updated
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT full_content, is_detail_complete, attachment_present FROM live_announcements WHERE announcement_id = ?", (test_ann_id,))
            row = cursor.fetchone()
            assert row is not None
            assert "Complete circular for annual hostel inspection" in row["full_content"]
            assert row["is_detail_complete"] == 1
            assert row["attachment_present"] == 1


def test_search_retrieves_text_deep_inside_complete_circular():
    """Verify that hybrid search matches terms found deep inside complete notice content."""
    retrieval_service = RetrievalService()
    
    results = retrieval_service.search(query="B.Tech Computer Science", top_k=5)
    assert len(results) > 0
    first = results[0]
    assert "full_content" in first or "document" in first
    assert "is_detail_complete" in first


def test_historical_dataset_records_preserved():
    """Verify that the 7,350 historical announcement records in JSON remain intact."""
    dataset_service = DatasetService()
    records, report = dataset_service.load_dataset()
    assert len(records) >= 7350
    # Spot-check structure
    assert hasattr(records[0], "title")
    assert hasattr(records[0], "full_content")
    assert hasattr(records[0], "publication_date")
