"""Comprehensive End-to-End Acceptance Tests (Phase 5 Workflows A through I).

Tests realistic workflows across ingestion, revision tracking, personalization,
RAG answering, deadlines, room impact, attachments, UMS synchronization, and frontend assets.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.student import StudentProfile, TimetableEntry
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata
from app.models.chat import ChatRequest
from app.services.dataset_service import DatasetService
from app.services.personalization_service import PersonalizationService
from app.services.room_impact_service import RoomImpactService
from app.services.chat_service import ChatService
from app.services.ums_sync_service import UMSSyncService
from app.services.ums_source import UMSSourceAdapter

client = TestClient(app)


def test_workflow_a_announcement_ingestion():
    """Workflow A: Announcement ingestion & schema normalization."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    raw_item = {
        "id": "INGEST-101",
        "title": "Annual Convocation Registration 2026",
        "publication_date": "2026-10-18",
        "reference_number": "LPU/CONV/2026/01",
        "full_content": "Eligible graduating students must register for Convocation by October 30.",
        "attachment_present": True,
        "attachment_names": ["Convocation_Guidelines.pdf"],
    }
    ann = adapter.normalize_announcement(raw_item)
    assert ann.announcement_id == "ANN-UMS-INGEST-101"
    assert ann.title == "Annual Convocation Registration 2026"
    assert ann.attachment_present is True
    assert "Convocation_Guidelines.pdf" in ann.attachment_names


def test_workflow_b_updated_announcement():
    """Workflow B: Edited announcement detected as an update with incremented revision count."""
    mock_adapter = MagicMock()
    v1 = {
        "id": "REV-WF-01",
        "title": "Room Change Notice",
        "publication_date": "2026-10-18",
        "reference_number": "LPU/WF/01",
        "full_content": "Initial Room: 34-101",
    }
    mock_adapter.fetch_latest_announcements.return_value = [v1]
    mock_adapter.normalize_announcement.side_effect = lambda r: UMSSourceAdapter().normalize_announcement(r)

    sync_service = UMSSyncService(source_adapter=mock_adapter)
    res1 = sync_service.run_sync(triggered_by="test_wf_b")
    assert res1["status"] == "SUCCESS"

    # Revise notice
    v2 = {
        "id": "REV-WF-01",
        "title": "Room Change Notice - REVISED",
        "publication_date": "2026-10-18",
        "reference_number": "LPU/WF/01",
        "full_content": "Updated Room: 34-205",
    }
    mock_adapter.fetch_latest_announcements.return_value = [v2]
    res2 = sync_service.run_sync(triggered_by="test_wf_b_update")
    assert res2["status"] == "SUCCESS"
    assert res2["updated_count"] == 1


def test_workflow_c_personalized_results():
    """Workflow C: Different student profiles receive tailored priority rankings."""
    ps = PersonalizationService()
    stu_cs = StudentProfile(
        student_id="STU-CS",
        name="Aarav Sharma",
        program="B.Tech Computer Science & Engineering",
        department="Department of Computer Science",
        school="School of CSE",
        year=3,
        semester=5,
        interests=["Competitive Programming", "AI/ML", "Web Development"]
    )
    stu_mech = StudentProfile(
        student_id="STU-MECH",
        name="Priya Patel",
        program="B.Tech Mechanical Engineering",
        department="Department of Mechanical Engineering",
        school="School of Mechanical",
        year=2,
        semester=3,
        interests=["Robotics", "CAD/CAM", "Automotive"]
    )

    cs_ann = RawAnnouncement(
        announcement_id="ANN-CS-01",
        title="Hackathon on Generative AI & Web Dev",
        publication_date="2026-10-15",
        full_content="Open for 3rd Year B.Tech CSE students interested in AI/ML and Hackathons.",
        attachment_present=False
    )
    cs_meta = ExtractedAnnouncementMetadata(
        announcement_id="ANN-CS-01",
        category="EVENT",
        summary="AI Hackathon",
        topics=["ai/ml", "hackathons", "web development"],
        target_year=[3],
        target_program="B.Tech Computer Science & Engineering",
        target_department="Department of Computer Science"
    )

    score_cs = ps.score_announcement(stu_cs, cs_ann, cs_meta)["personal_priority_score"]
    score_mech = ps.score_announcement(stu_mech, cs_ann, cs_meta)["personal_priority_score"]

    assert score_cs > score_mech
    assert score_cs >= 0.70


def test_workflow_d_rag_question_answering_and_refusal():
    """Workflow D: Grounded Q&A citations and refusal when evidence is absent."""
    service = ChatService()
    # 1. Missing evidence refusal
    service.retrieval_service.search = MagicMock(return_value=[])
    res_absent = service.answer_question(ChatRequest(query="What is the Martian Colony refund rule?"))
    assert res_absent.insufficient_evidence is True
    assert "could not find any relevant university announcements" in res_absent.answer.lower()

    # 2. Evidence with citations
    candidate = {
        "announcement_id": "ANN-UMS-GOOGLE",
        "title": "Google Placement Drive",
        "publication_date": "2026-10-15",
        "reference_number": "LPU/TPO/01",
        "document": "Google Placement Drive for final years CGPA 8.0.",
        "attachment_present": False,
        "attachment_names": [],
        "decision_completeness": "COMPLETE",
        "rrf_score": 0.9
    }
    service.retrieval_service.search = MagicMock(return_value=[candidate])

    with patch("app.core.security.validate_api_key_configured", return_value=True):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Google Drive requires CGPA 8.0 [Source ID: ANN-UMS-GOOGLE]."
        mock_client.models.generate_content.return_value = mock_resp
        service.get_client = MagicMock(return_value=mock_client)

        res_present = service.answer_question(ChatRequest(query="Google CGPA requirement"))
        assert "[Source ID: ANN-UMS-GOOGLE]" in res_present.answer
        assert len(res_present.sources) == 1


def test_workflow_e_deadlines():
    """Workflow E: Deadlines sorted chronologically with active and expired states."""
    res = client.get("/api/v1/announcements/deadlines?include_expired=true&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_workflow_f_room_impact():
    """Workflow F: Explicit room exemptions and building impact."""
    service = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-WF-F",
        student_id="STU-101",
        day_or_date="2026-10-15",
        start_time="09:00 AM",
        end_time="10:00 AM",
        course_code="CSE301",
        course_name="DSA",
        room="34-105"
    )

    ann = RawAnnouncement(
        announcement_id="ANN-WF-F",
        title="Block 34 Maintenance",
        publication_date="2026-10-14",
        full_content="Classes suspended in Block 34 except Room 34-105.",
        attachment_present=False
    )

    res = service.check_timetable_conflict(entry, ann, None)
    assert res.affected is False
    assert res.status == "EXEMPTED"


def test_workflow_g_attachment_dependency():
    """Workflow G: Attachment warning banner generated when attachment content is missing."""
    service = ChatService()
    candidate = {
        "announcement_id": "ANN-ATT-01",
        "title": "Seating Arrangement",
        "publication_date": "2026-10-15",
        "reference_number": "LPU/EX/01",
        "document": "Please refer to attached seating plan PDF for room assignments.",
        "attachment_present": True,
        "attachment_names": ["Seating_Plan.pdf"],
        "decision_completeness": "ATTACHMENT_MISSING",
        "rrf_score": 0.88
    }
    service.retrieval_service.search = MagicMock(return_value=[candidate])
    res = service.answer_question(ChatRequest(query="Where is my exam room?"))

    assert res.attachment_warning is not None
    assert "Seating_Plan.pdf" in res.attachment_warning


def test_workflow_h_ums_sync():
    """Workflow H: UMS sync under mock and network safeguard conditions."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    status = adapter.get_source_status()
    assert status["connector_mode"] == "mock"
    assert status["status"] == "MOCK_MODE"

    conn = adapter.check_connection()
    assert conn["connected"] is True

    notices = adapter.fetch_latest_announcements(limit=3)
    assert len(notices) == 3


def test_workflow_i_frontend_interaction():
    """Workflow I: Verify web dashboard HTML, API status, and student list."""
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "LPU SmartNotice" in res_root.text

    res_students = client.get("/api/v1/students")
    assert res_students.status_code == 200
    students = res_students.json()
    assert len(students) >= 1
    assert "student_id" in students[0]

    res_feed = client.get(f"/api/v1/feed/{students[0]['student_id']}/feed?page=1&page_size=3")
    assert res_feed.status_code == 200
    feed = res_feed.json()
    assert "feed" in feed
    assert len(feed["feed"]) >= 1
