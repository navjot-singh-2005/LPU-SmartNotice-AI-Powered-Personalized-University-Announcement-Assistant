"""Unit tests for Grounded RAG Chatbot Service and citation verification."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.chat import ChatRequest, ChatMessage
from app.models.announcement import RawAnnouncement
from app.services.chat_service import ChatService

client = TestClient(app)


def test_empty_retrieval_insufficient_evidence():
    """Verify that when no announcements match, the chatbot refuses to fabricate an answer."""
    service = ChatService()
    service.retrieval_service.search = MagicMock(return_value=[])

    req = ChatRequest(query="What is the Martian Colony scholarship guideline for 2099?")
    res = service.answer_question(req)

    assert res.insufficient_evidence is True
    assert "could not find any relevant university announcements" in res.answer.lower()
    assert len(res.sources) == 0


def test_conversational_greeting_without_citations():
    """Verify that a basic greeting like 'Hello' returns a polite assistant message without citations."""
    service = ChatService()
    req = ChatRequest(query="Hello")
    res = service.answer_question(req)

    assert res.insufficient_evidence is False
    assert len(res.sources) == 0
    assert "hello" in res.answer.lower() or "lpu smartnotice" in res.answer.lower()


def test_attachment_warning_propagation():
    """Verify that notices with attachments flag an attachment warning."""
    service = ChatService()
    mock_candidate = {
        "announcement_id": "ANN-TEST-001",
        "title": "Mid-Term Exam Seating Plan",
        "publication_date": "2026-10-15",
        "reference_number": "LPU/EXAM/2026/01",
        "document": "Exam will be held in Block 34. Check attached seating plan.",
        "attachment_present": True,
        "attachment_names": ["Seating_Plan_Oct2026.pdf"],
        "attachment_content_available": False,
        "decision_completeness": "ATTACHMENT_MISSING",
        "rrf_score": 0.85,
    }
    service.retrieval_service.search = MagicMock(return_value=[mock_candidate])

    req = ChatRequest(query="Where is my exam seat?")
    res = service.answer_question(req)

    assert len(res.sources) == 1
    assert res.sources[0].announcement_id == "ANN-TEST-001"
    assert res.attachment_warning is not None
    assert "Seating_Plan_Oct2026.pdf" in res.attachment_warning
    assert "unavailable" in res.attachment_warning.lower()


@patch("app.core.security.validate_api_key_configured", return_value=True)
def test_grounded_answer_with_citations(mock_key):
    """Verify that when Gemini client responds, sources and bracketed citations are returned."""
    service = ChatService()
    mock_candidate = {
        "announcement_id": "ANN-20261015-TEST",
        "title": "Placement Drive Google Cloud",
        "publication_date": "2026-10-15",
        "reference_number": "LPU/TPO/2026/10",
        "document": "Google Cloud drive open for final year CSE students with CGPA >= 8.0.",
        "attachment_present": False,
        "attachment_names": [],
        "attachment_content_available": False,
        "decision_completeness": "COMPLETE",
        "rrf_score": 0.95,
    }
    service.retrieval_service.search = MagicMock(return_value=[mock_candidate])

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Google Cloud placement drive requires a CGPA of 8.0 or above [Source ID: ANN-20261015-TEST]."
    mock_client.models.generate_content.return_value = mock_response
    service.get_client = MagicMock(return_value=mock_client)

    req = ChatRequest(query="What is the CGPA eligibility for Google Cloud drive?")
    res = service.answer_question(req)

    assert res.insufficient_evidence is False
    assert "[Source ID: ANN-20261015-TEST]" in res.answer
    assert len(res.sources) == 1
    assert res.sources[0].announcement_id == "ANN-20261015-TEST"


@patch("app.core.security.validate_api_key_configured", return_value=True)
def test_multi_turn_history_in_prompt(mock_key):
    """Verify that conversation history is formatted and included in Gemini prompt."""
    service = ChatService()
    mock_candidate = {
        "announcement_id": "ANN-HIST-01",
        "title": "Internship at Microsoft",
        "publication_date": "2026-10-18",
        "reference_number": "LPU/TPO/02",
        "document": "Microsoft Internship drive details.",
        "attachment_present": False,
        "attachment_names": [],
        "attachment_content_available": False,
        "decision_completeness": "COMPLETE",
        "rrf_score": 0.90,
    }
    service.retrieval_service.search = MagicMock(return_value=[mock_candidate])

    mock_client = MagicMock()
    captured_prompt = {}

    def capture_generate(model, contents, config):
        captured_prompt["prompt"] = contents
        resp = MagicMock()
        resp.text = "The deadline is October 28 [Source ID: ANN-HIST-01]."
        return resp

    mock_client.models.generate_content.side_effect = capture_generate
    service.get_client = MagicMock(return_value=mock_client)

    history = [
        ChatMessage(role="user", content="Tell me about Microsoft drive"),
        ChatMessage(role="assistant", content="Microsoft drive is for CSE 2027 batch.")
    ]
    req = ChatRequest(query="What is the application deadline?", history=history)
    res = service.answer_question(req)

    assert "Previous Conversation Context:" in captured_prompt["prompt"]
    assert "Tell me about Microsoft drive" in captured_prompt["prompt"]
    assert "[Source ID: ANN-HIST-01]" in res.answer


def test_empty_query_rejected_by_api():
    """Verify that an empty or whitespace-only query is rejected with HTTP 400."""
    res1 = client.post("/api/v1/chat", json={"query": ""})
    assert res1.status_code == 400

    res2 = client.post("/api/v1/chat", json={"query": "   "})
    assert res2.status_code == 400


@patch("app.core.security.validate_api_key_configured", return_value=True)
def test_gemini_api_error_fallback(mock_key):
    """Verify that an unexpected Gemini exception produces an honest fallback without crashing."""
    service = ChatService()
    mock_candidate = {
        "announcement_id": "ANN-ERR-01",
        "title": "Convocation 2026",
        "publication_date": "2026-10-10",
        "reference_number": "LPU/CONV/01",
        "document": "Convocation registration is open.",
        "attachment_present": False,
        "attachment_names": [],
        "attachment_content_available": False,
        "decision_completeness": "COMPLETE",
        "rrf_score": 0.88,
    }
    service.retrieval_service.search = MagicMock(return_value=[mock_candidate])

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded: 429 RESOURCE_EXHAUSTED")
    service.get_client = MagicMock(return_value=mock_client)

    req = ChatRequest(query="When is Convocation?")
    res = service.answer_question(req)

    assert res.insufficient_evidence is False
    assert len(res.sources) == 1
    assert "Convocation 2026" in res.answer
    assert "high demand" in res.answer.lower() or "quota" in res.answer.lower() or "error" in res.answer.lower()
