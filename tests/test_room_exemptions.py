"""Unit tests for room exemption and exclusion detection in RoomImpactService."""

import pytest
from app.models.student import TimetableEntry
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata
from app.services.room_impact_service import RoomImpactService


def test_metadata_room_exemption():
    """Verify that an explicitly exempted room yields affected=False and status=EXEMPTED."""
    service = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-EX-1",
        student_id="STU-101",
        day_or_date="2026-10-15",
        start_time="09:00 AM",
        end_time="10:00 AM",
        course_code="CSE301",
        course_name="Data Structures",
        room="34-105"
    )

    ann = RawAnnouncement(
        announcement_id="ANN-EX-001",
        title="Class Suspension in Block 34",
        publication_date="2026-10-14",
        full_content="Classes in Block 34 are suspended due to maintenance work, except room 34-105.",
        attachment_present=False
    )

    meta = ExtractedAnnouncementMetadata(
        announcement_id="ANN-EX-001",
        category="ACADEMIC",
        summary="Suspension in Block 34 except 34-105",
        affected_rooms=["34-101", "34-102", "34-103", "34-104"],
        exempted_rooms=["34-105"],
        building="Block 34"
    )

    result = service.check_timetable_conflict(entry, ann, meta)
    assert result.affected is False
    assert result.status == "EXEMPTED"
    assert "34-105" in result.explanation


def test_textual_regex_room_exemption():
    """Verify that regex captures textual room exemptions when metadata is missing."""
    service = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-EX-2",
        student_id="STU-101",
        day_or_date="2026-10-15",
        start_time="11:00 AM",
        end_time="12:00 PM",
        course_code="INT219",
        course_name="Web Dev",
        room="34-108"
    )

    ann = RawAnnouncement(
        announcement_id="ANN-EX-002",
        title="Mid-Term Exams in Block 34",
        publication_date="2026-10-14",
        full_content="Block 34 rooms 34-101 to 34-110 will be used for exams, except room 34-108 which will continue regular lab classes.",
        attachment_present=False
    )

    result = service.check_timetable_conflict(entry, ann, None)
    assert result.affected is False
    assert result.status == "EXEMPTED"
    assert "34-108" in result.explanation


def test_no_overlap_returns_no_match():
    """Verify that an announcement in Block 32 does not impact a class in Block 34."""
    service = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-EX-3",
        student_id="STU-101",
        day_or_date="2026-10-15",
        start_time="02:00 PM",
        end_time="03:00 PM",
        course_code="CSE401",
        course_name="Cloud Computing",
        room="34-301"
    )

    ann = RawAnnouncement(
        announcement_id="ANN-EX-003",
        title="Mittal School Event in Block 32",
        publication_date="2026-10-14",
        full_content="Auditorium in Block 32 Room 32-101 booked for cultural fest.",
        attachment_present=False
    )

    result = service.check_timetable_conflict(entry, ann, None)
    assert result.affected is False
    assert result.status == "NO_MATCH"
