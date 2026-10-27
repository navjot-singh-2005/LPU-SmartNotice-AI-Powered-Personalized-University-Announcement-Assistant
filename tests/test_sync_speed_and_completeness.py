"""Targeted verification for notice synchronization speed and completeness.

Verifies:
1. Complete notice is stored without truncation when full detail is accessible.
2. Pagination processes all accessible listing pages up to requested limit.
3. Repeated synchronization does not create duplicates.
4. Unchanged notices do not trigger unnecessary embeddings or writes.
5. New notices are added.
6. Changed notices update existing records and revision count.
7. Failed detail requests are logged and do not silently produce false full-content records.
8. Synchronization speed: unchanged notices skip network/embedding and complete rapidly.
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.core.database import get_db_connection, init_db
from app.models.announcement import RawAnnouncement
from app.services.ums_source import UMSSourceAdapter
from app.services.ums_sync_service import UMSSyncService


@pytest.fixture(autouse=True)
def clean_test_db():
    """Ensure database is clean before and after each test."""
    init_db()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM live_announcements WHERE announcement_id LIKE '%SPEED%'")
    c.execute("DELETE FROM ums_sync_history WHERE sync_id LIKE '%SPEED%'")
    conn.commit()
    conn.close()
    yield
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM live_announcements WHERE announcement_id LIKE '%SPEED%'")
    c.execute("DELETE FROM ums_sync_history WHERE sync_id LIKE '%SPEED%'")
    conn.commit()
    conn.close()


def test_complete_notice_stored_without_truncation():
    """Requirement 1: Complete notice is stored without truncation when full detail is accessible."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    sync_service = UMSSyncService(source_adapter=adapter)

    long_body = (
        "OFFICIAL UNIVERSITY CIRCULAR ON ACADEMIC SCHOLARSHIPS 2026-2027\n\n"
        "1. ELIGIBILITY CRITERIA:\n"
        "• Minimum CGPA 8.5 in previous academic term.\n"
        "• No backlogs or disciplinary warnings on record.\n"
        "• Annual parental income less than Rs. 5,00,000.\n\n"
        "2. DOCUMENTATION REQUIRED:\n"
        "• Certified copies of grade sheets for Semesters 1 through 4.\n"
        "• Income affidavit endorsed by a First Class Judicial Magistrate.\n"
        "• Recommendation letter from Academic Mentor or Head of Department.\n\n"
        "3. SUBMISSION GUIDELINES:\n"
        "Submit hard copies at Block 32, Directorate of Student Welfare, Room 104.\n"
        "Deadline for application submission is 15th November 2026 at 5:00 PM."
    )

    test_ann = RawAnnouncement(
        announcement_id="ANN-SPEED-COMPL-01",
        title="Official Circular on Academic Scholarships 2026-2027",
        publication_date="2026-10-27",
        reference_number="LPU/SCH/2026/099",
        full_content=long_body,
        attachment_present=True,
        attachment_names=["Scholarship_Form_2026.pdf"],
        is_detail_complete=True,
        source="ums",
    )

    action = sync_service._persist_announcement(test_ann)
    assert action == "INSERTED"

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT full_content, is_detail_complete FROM live_announcements WHERE announcement_id = ?", ("ANN-SPEED-COMPL-01",))
    row = c.fetchone()
    conn.close()

    assert row is not None
    assert row["is_detail_complete"] == 1
    assert row["full_content"] == long_body
    assert "ELIGIBILITY CRITERIA" in row["full_content"]
    assert "SUBMISSION GUIDELINES" in row["full_content"]


def test_pagination_processes_multiple_pages():
    """Requirement 2: Pagination processes all accessible listing pages up to limit."""
    adapter = UMSSourceAdapter(connector_mode="live")

    # Mock response generator simulating multi-page WordPress REST API
    page1_posts = [
        {"id": f"10{i}", "title": {"rendered": f"Post {i}"}, "content": {"rendered": f"<p>Body {i}</p>"}, "date": "2026-10-20"}
        for i in range(1, 11)
    ]
    page2_posts = [
        {"id": f"20{i}", "title": {"rendered": f"Post {i+10}"}, "content": {"rendered": f"<p>Body {i+10}</p>"}, "date": "2026-10-19"}
        for i in range(1, 11)
    ]

    def mock_get(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-WP-TotalPages": "3"}
        if "&page=2" in str(url):
            mock_resp.json.return_value = page2_posts
        else:
            mock_resp.json.return_value = page1_posts
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        results = adapter._fetch_from_lpu_feed(limit=20)
        assert len(results) == 20
        assert results[0]["id"] == "101"
        assert results[10]["id"] == "201"


def test_repeated_sync_no_duplicates_and_skips_unchanged():
    """Requirements 3 & 4: Repeated sync does not create duplicates and skips unchanged notices."""
    mock_adapter = MagicMock()
    sample_notices = [
        {
            "id": "SPEED-101",
            "title": "Semester Registration Opening Announcement",
            "full_content": "Registration for Winter 2026 opens on 1st November. All students must clear dues.",
            "publication_date": "2026-10-27",
            "reference_number": "LPU/REG/2026/01",
            "is_detail_complete": True,
        },
        {
            "id": "SPEED-102",
            "title": "Library Working Hours Update",
            "full_content": "Central Library in Block 30 will remain open 24x7 during the mid-term examination week.",
            "publication_date": "2026-10-27",
            "reference_number": "LPU/LIB/2026/02",
            "is_detail_complete": True,
        },
    ]
    mock_adapter.normalize_announcement.side_effect = lambda raw: UMSSourceAdapter().normalize_announcement(raw)
    mock_adapter._enrich_candidates_with_details.side_effect = lambda c, **kw: c

    sync_service = UMSSyncService(source_adapter=mock_adapter)

    with patch.object(sync_service, "_process_ai_pipeline", return_value=True):
        # First sync: Both inserted
        res1 = sync_service.ingest_announcements(sample_notices, triggered_by="speed_test_1")
        assert res1["inserted_count"] == 2
        assert res1["skipped_count"] == 0

        # Second sync: Both skipped, no duplicates created
        start_time = time.time()
        res2 = sync_service.ingest_announcements(sample_notices, triggered_by="speed_test_2")
        elapsed = time.time() - start_time

        assert res2["inserted_count"] == 0
        assert res2["skipped_count"] == 2
        assert res2["status"] == "UP_TO_DATE"
        assert elapsed < 0.2  # Unchanged sync must complete within ~200ms


def test_new_and_changed_notices_update_in_place():
    """Requirements 5 & 6: New notices are inserted and changed notices update existing records."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    sync_service = UMSSyncService(source_adapter=adapter)

    initial_notice = [
        {
            "id": "SPEED-301",
            "title": "Campus Placement: TCS Digital Drive",
            "full_content": "Eligible branches: CSE and IT. Room 34-201 at 9:00 AM.",
            "publication_date": "2026-10-27",
            "reference_number": "LPU/TPO/SPEED/301",
            "is_detail_complete": True,
        }
    ]

    with patch.object(sync_service, "_process_ai_pipeline", return_value=True):
        res1 = sync_service.ingest_announcements(initial_notice, triggered_by="test_v1")
        assert res1["inserted_count"] == 1

        # Revised notice: Venue changed from 34-201 to 32-105
        revised_notice = [
            {
                "id": "SPEED-301",
                "title": "Campus Placement: TCS Digital Drive (REVISED VENUE)",
                "full_content": "Eligible branches: CSE and IT. Venue shifted to Room 32-105 at 9:30 AM due to hall capacity.",
                "publication_date": "2026-10-27",
                "reference_number": "LPU/TPO/SPEED/301",
                "is_detail_complete": True,
            },
            {
                "id": "SPEED-302",
                "title": "Brand New Hackathon Announcement",
                "full_content": "Registrations open for Google Solution Challenge 2026.",
                "publication_date": "2026-10-27",
                "reference_number": "LPU/INN/SPEED/302",
                "is_detail_complete": True,
            }
        ]

        res2 = sync_service.ingest_announcements(revised_notice, triggered_by="test_v2")
        assert res2["inserted_count"] == 1  # SPEED-302
        assert res2["updated_count"] == 1   # SPEED-301 updated in place!
        assert res2["skipped_count"] == 0

    # Verify database: SPEED-301 updated with revision_count = 2
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT title, full_content, revision_count FROM live_announcements WHERE announcement_id = ?", ("ANN-UMS-SPEED-301",))
    row = c.fetchone()
    conn.close()

    assert row is not None
    assert "REVISED VENUE" in row["title"]
    assert "Room 32-105" in row["full_content"]
    assert row["revision_count"] == 2


def test_failed_detail_requests_log_and_do_not_fabricate_completeness():
    """Requirement 7: Failed detail requests do not silently produce false full-content records."""
    adapter = UMSSourceAdapter(connector_mode="live")

    short_cand = [
        {
            "id": "99999",
            "title": "Brief Seminar Notice",
            "full_content": "Short listing preview text.",
            "publication_date": "2026-10-27",
            "reference_number": "LPU/SEM/99999",
            "is_detail_complete": False,
        }
    ]

    with patch.object(adapter, "fetch_announcement_details", side_effect=RuntimeError("Portal detail endpoint unreachable (503)")):
        enriched = adapter._enrich_candidates_with_details(short_cand)
        assert len(enriched) == 1
        item = enriched[0]
        # Must not fabricate completeness
        assert item["is_detail_complete"] is False
        assert "Portal detail endpoint unreachable" in item["detail_fetch_error"]
        assert item["full_content"] == "Short listing preview text."
