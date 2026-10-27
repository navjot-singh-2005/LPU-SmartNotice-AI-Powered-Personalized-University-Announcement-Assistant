import pytest
from app.models.announcement import RawAnnouncement
from app.services.deduplication_service import DeduplicationService

def test_exact_duplicate_detection():
    service = DeduplicationService()
    ann1 = RawAnnouncement(
        announcement_id="ANN-1",
        title="Same Title",
        publication_date="2026-10-01",
        full_content="Identical content body for notice test."
    )
    ann2 = RawAnnouncement(
        announcement_id="ANN-2",
        title="Same Title",
        publication_date="2026-10-01",
        full_content="Identical content body for notice test."
    )

    unique, report = service.process_deduplication([ann1, ann2])
    assert len(unique) == 1
    assert report["exact_duplicates_removed"] == 1

def test_revision_preservation():
    service = DeduplicationService()
    ann1 = RawAnnouncement(
        announcement_id="ANN-1",
        title="Timetable Notice",
        publication_date="2026-10-01",
        reference_number="LPU/REF/100",
        full_content="Initial version of timetable schedule."
    )
    ann2 = RawAnnouncement(
        announcement_id="ANN-2",
        title="Timetable Notice (Revised)",
        publication_date="2026-10-02",
        reference_number="LPU/REF/100",
        full_content="Updated version of timetable schedule with new rooms."
    )

    unique, report = service.process_deduplication([ann1, ann2])
    assert len(unique) == 2
    assert report["revisions_detected"] == 1
