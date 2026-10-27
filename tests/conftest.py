import os
import pytest
from app.core.database import init_db
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata, ActionType, UrgencyLevel, GlobalImportance, DecisionCompleteness
from app.models.student import StudentProfile, TimetableEntry

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()


@pytest.fixture
def sample_raw_announcement():
    return RawAnnouncement(
        announcement_id="ANN-TEST-001",
        title="Mid-Term Examination Schedule for B.Tech CSE Year 3",
        publication_date="2026-10-01",
        reference_number="LPU/EXAM/2026/101",
        full_content="All 3rd Year B.Tech CSE students are hereby informed that Mid-Term examinations will start on 15th October 2026 in Block 34, Rooms 34-101 to 34-110. Regular classes in Block 34 are suspended. Please refer to attached seating plan PDF for details. Contact john.doe@lpu.co.in or 9876543210 for queries.",
        attachment_present=True,
        attachment_names=["Seating_Plan_Oct2026.pdf"],
        content_hash="test_content_hash_001"
    )

@pytest.fixture
def sample_extracted_metadata():
    return ExtractedAnnouncementMetadata(
        announcement_id="ANN-TEST-001",
        category="EXAMINATION",
        summary="Mid-Term examinations for 3rd Year B.Tech CSE starting Oct 15 in Block 34.",
        topics=["examination", "seating plan", "b.tech cse"],
        target_year=[3],
        target_program="B.Tech Computer Science & Engineering",
        target_department="Department of Computer Science",
        event_date="2026-10-15",
        building="Block 34",
        room_range="34-101 to 34-110",
        affected_rooms=["34-101", "34-102", "34-103", "34-104", "34-105", "34-106", "34-107", "34-108", "34-109", "34-110"],
        impact_type="VENUE_CHANGE",
        action_required=True,
        action_type=ActionType.EXAM,
        urgency=UrgencyLevel.HIGH,
        global_importance=GlobalImportance.MEDIUM,
        confidence=0.95,
        attachment_present=True,
        attachment_names=["Seating_Plan_Oct2026.pdf"],
        attachment_content_available=False,
        attachment_dependent=True,
        requires_attachment_verification=True,
        decision_completeness=DecisionCompleteness.ATTACHMENT_MISSING
    )

@pytest.fixture
def sample_student_profile():
    return StudentProfile(
        student_id="STU-101",
        name="Aarav Sharma",
        program="B.Tech Computer Science & Engineering",
        department="Department of Computer Science",
        school="School of Computer Science and Engineering",
        year=3,
        semester=5,
        section="K21AB",
        interests=["Web Development", "AI/ML", "Placements"],
        career_goal="Software Development Engineer"
    )
