"""Test suite for Five Sidebar Features Enhancements in LPU SmartNotice.

Covers:
- Feature 1: Personalized Feed (applicability tiers, deadline parsing, tier filtering)
- Feature 2: AI Assistant RAG (evidence grounding, citations, clear history)
- Feature 3: Search & Browse (hybrid query, filters by urgency & attachment, sorting)
- Feature 4: Room & Timetable Impact (impact types, exemptions, attachment dependency)
- Feature 5: System Dashboard (health diagnostics, cache reload)
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.student import StudentProfile, TimetableEntry
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata, UrgencyLevel, DecisionCompleteness
from app.services.personalization_service import PersonalizationService
from app.services.room_impact_service import RoomImpactService

client = TestClient(app)

@pytest.fixture
def sample_student_cse():
    return StudentProfile(
        student_id="STU-101",
        name="Aarav Sharma",
        program="B.Tech Computer Science and Engineering",
        department="Department of Computer Science",
        school="School of Computer Science and Engineering",
        year=4,
        semester=7,
        section="K21CS",
        interests=["Artificial Intelligence", "Cloud Computing", "Full Stack Development"],
        career_goal="Software Development Engineer"
    )

@pytest.fixture
def sample_student_me():
    return StudentProfile(
        student_id="STU-102",
        name="Rohan Verma",
        program="B.Tech Mechanical Engineering",
        department="Department of Mechanical Engineering",
        school="School of Mechanical Engineering",
        year=1,
        semester=1,
        section="K24ME",
        interests=["Robotics", "Automobile", "CAD Modeling"],
        career_goal="Robotics Engineer"
    )

# ==============================================================================
# FEATURE 1: PERSONALIZED FEED TESTS
# ==============================================================================

def test_personalization_applicability_tiers(sample_student_cse, sample_student_me):
    """Verify announcements are assigned correct applicability tiers."""
    svc = PersonalizationService()

    # 1. Definitely applicable to CSE Year 4
    ann_cse = RawAnnouncement(
        announcement_id="ANN-TEST-001",
        title="Placement Drive for 4th Year B.Tech CSE",
        full_content="Google is hiring final year CSE students.",
        publication_date="2026-10-20"
    )
    meta_cse = ExtractedAnnouncementMetadata(
        announcement_id="ANN-TEST-001",
        summary="Placement Drive for 4th Year B.Tech CSE",
        target_year=[4],
        target_program="B.Tech Computer Science and Engineering",
        target_department="Department of Computer Science",
        category="PLACEMENT",
        urgency=UrgencyLevel.HIGH
    )
    score_cse = svc.score_announcement(sample_student_cse, ann_cse, meta_cse)
    assert score_cse["applicability_tier"] == "DEFINITELY_APPLICABLE"

    # For ME 1st year student, it should be NOT_APPLICABLE
    score_me = svc.score_announcement(sample_student_me, ann_cse, meta_cse)
    assert score_me["applicability_tier"] == "NOT_APPLICABLE"

    # 2. General university notice
    ann_general = RawAnnouncement(
        announcement_id="ANN-TEST-002",
        title="University Annual Sports Day",
        full_content="All students are invited to join the sports meet.",
        publication_date="2026-10-21"
    )
    score_gen = svc.score_announcement(sample_student_cse, ann_general, None)
    assert score_gen["applicability_tier"] == "GENERAL_NOTICE"

    # 3. Uncertain notice with missing attachment
    meta_uncertain = ExtractedAnnouncementMetadata(
        announcement_id="ANN-TEST-002",
        summary="Annual Sports Day",
        category="EXAMINATION",
        decision_completeness=DecisionCompleteness.ATTACHMENT_MISSING,
        urgency=UrgencyLevel.MEDIUM
    )
    score_unc = svc.score_announcement(sample_student_cse, ann_general, meta_uncertain)
    assert score_unc["applicability_tier"] == "UNCERTAIN"


def test_deadline_extraction_and_expiration(sample_student_cse):
    """Verify deadline parsing, days remaining, and expiration detection."""
    svc = PersonalizationService()

    ann = RawAnnouncement(
        announcement_id="ANN-TEST-003",
        title="Scholarship Registration Deadline",
        full_content="Last date to apply for scholarship is 30/10/2026.",
        publication_date="2026-10-15"
    )
    meta = ExtractedAnnouncementMetadata(
        announcement_id="ANN-TEST-003",
        summary="Scholarship registration notice",
        deadline="2026-10-30",
        category="ACADEMIC"
    )

    # Reference date is 2026-10-26
    dln = svc.extract_deadline_info(ann, meta, reference_date_str="2026-10-26")
    assert dln["deadline_date"] == "2026-10-30"
    assert dln["is_expired"] is False
    assert dln["days_remaining"] == 4

    # Expired deadline
    meta_exp = ExtractedAnnouncementMetadata(
        announcement_id="ANN-TEST-003",
        summary="Expired scholarship notice",
        deadline="2026-10-10",
        category="ACADEMIC"
    )
    dln_exp = svc.extract_deadline_info(ann, meta_exp, reference_date_str="2026-10-26")
    assert dln_exp["is_expired"] is True
    assert dln_exp["days_remaining"] < 0


def test_feed_api_with_applicability_filter():
    """Verify GET /api/v1/feed/{id}/feed accepts applicability query param."""
    res = client.get("/api/v1/feed/STU-101/feed?applicability=APPLICABLE&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert "feed" in data
    assert "tier_counts" in data
    # All returned items must be DEFINITELY_APPLICABLE
    for item in data["feed"]:
        assert item["applicability_tier"] == "DEFINITELY_APPLICABLE"


# ==============================================================================
# FEATURE 2: AI ASSISTANT RAG TESTS
# ==============================================================================

def test_chat_grounding_and_sources():
    """Verify chat endpoint returns valid structure with sources array."""
    res = client.post("/api/v1/chat", json={"query": "Hello"})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "sources" in data
    assert len(data["sources"]) == 0 # Conversational greeting has 0 sources


# ==============================================================================
# FEATURE 3: SEARCH & BROWSE TESTS
# ==============================================================================

def test_search_with_urgency_and_sorting():
    """Verify search endpoint supports query, filters, sorting, and pagination."""
    res = client.get("/api/v1/announcements/search?q=examination&sort_by=newest&page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "examination"
    assert "total" in data
    assert "total_pages" in data
    assert len(data["results"]) <= 5


def test_search_attachment_only_filter():
    """Verify search with attachment_only=true returns only notices with attachments."""
    res = client.get("/api/v1/announcements/search?q=exam&attachment_only=true&page_size=5")
    assert res.status_code == 200
    data = res.json()
    for item in data["results"]:
        assert item["attachment_present"] is True


# ==============================================================================
# FEATURE 4: ROOM & TIMETABLE IMPACT TESTS
# ==============================================================================

def test_room_impact_types_and_attachment_dependency():
    """Verify impact types (SUSPENSION, VENUE_CHANGE, EXAM_DUTY) and attachment dependency."""
    svc = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-99",
        student_id="STU-101",
        day_or_date="2026-10-25",
        start_time="10:00 AM",
        end_time="11:00 AM",
        course_code="CSE401",
        course_name="Machine Learning",
        room="34-105",
        building="Block 34"
    )

    # 1. Suspension impact
    ann_susp = RawAnnouncement(
        announcement_id="ANN-S1",
        title="Class Suspension in Room 34-105",
        full_content="Classes suspended in room 34-105 due to power maintenance.",
        publication_date="2026-10-24"
    )
    res_susp = svc.check_timetable_conflict(entry, ann_susp)
    assert res_susp.affected is True
    assert res_susp.status == "CONFIRMED_MATCH"
    assert res_susp.impact_type == "SUSPENSION"

    # 2. Venue change impact
    ann_vc = RawAnnouncement(
        announcement_id="ANN-S2",
        title="Venue Change for CSE401",
        full_content="Room 34-105 relocated to new room 34-201 for today's session.",
        publication_date="2026-10-24"
    )
    res_vc = svc.check_timetable_conflict(entry, ann_vc)
    assert res_vc.affected is True
    assert res_vc.status == "CONFIRMED_MATCH"
    assert res_vc.impact_type == "VENUE_CHANGE"

    # 3. Attachment dependent impact
    ann_att = RawAnnouncement(
        announcement_id="ANN-S3",
        title="Block 34 Examination Seating Plan",
        full_content="Examinations scheduled in Block 34. Please refer to attached list for affected room schedules.",
        publication_date="2026-10-24",
        attachment_present=True
    )
    res_att = svc.check_timetable_conflict(entry, ann_att)
    assert res_att.affected is True
    assert res_att.status == "ATTACHMENT_DEPENDENT"
    assert res_att.impact_type == "EXAM_DUTY"


# ==============================================================================
# FEATURE 5: SYSTEM DASHBOARD TESTS
# ==============================================================================

def test_system_dashboard_health_and_subsystems():
    """Verify health endpoint includes subsystem status and SQLite counts."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("healthy", "degraded")
    assert "subsystems" in data
    assert data["subsystems"]["fastapi"] == "healthy"
    assert data["subsystems"]["sqlite"] == "healthy"
    assert "sqlite_stats" in data
    assert "live_announcements" in data["sqlite_stats"]


def test_cache_reload_endpoint():
    """Verify POST /api/v1/health/cache-refresh reloads cache successfully."""
    res = client.post("/api/v1/health/cache-refresh")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "reloaded" in data["message"].lower()
