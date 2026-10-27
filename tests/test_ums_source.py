"""Unit tests for UMSSourceAdapter (mocked, no real credentials or network calls)."""

import pytest
import httpx
from unittest.mock import patch, MagicMock

from app.services.ums_source import UMSSourceAdapter


def test_mock_mode_status_and_fetch():
    """Verify mock connector operates safely without credentials."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    status = adapter.get_source_status()
    assert status["connector_mode"] == "mock"
    assert status["status"] == "MOCK_MODE"

    conn = adapter.check_connection()
    assert conn["connected"] is True
    assert conn["status"] == "MOCK_ACTIVE"

    records = adapter.fetch_latest_announcements(limit=3)
    assert len(records) == 3
    assert "title" in records[0]

    detail = adapter.fetch_announcement_details("10091")
    assert detail["title"].startswith("Urgent")


def test_normalization_and_attachment_preservation():
    """Verify canonical mapping, attachment flags, and deterministic IDs."""
    adapter = UMSSourceAdapter(connector_mode="mock")

    raw = {
        "id": "7788",
        "NoticeTitle": "Placement Drive for Software Developers",
        "Body": "Drive starts tomorrow. Attachment: 1 Eligibility_Criteria.pdf",
        "Date": "2026-10-18",
        "RefNo": "LPU/TPO/2026/999",
        "Attachments": ["Eligibility_Criteria.pdf"],
    }

    ann = adapter.normalize_announcement(raw)
    assert ann.announcement_id == "ANN-UMS-7788"
    assert ann.title == "Placement Drive for Software Developers"
    assert ann.publication_date == "2026-10-18"
    assert ann.reference_number == "LPU/TPO/2026/999"
    assert ann.attachment_present is True
    assert "Eligibility_Criteria.pdf" in ann.attachment_names
    assert ann.source == "ums"
    assert ann.content_hash is not None


def test_normalization_malformed_and_missing_fields():
    """Verify normalization gracefully handles empty/malformed dictionaries."""
    adapter = UMSSourceAdapter(connector_mode="mock")

    ann = adapter.normalize_announcement({})
    assert ann.title == "Untitled UMS Announcement"
    assert ann.full_content == ""
    assert ann.announcement_id.startswith("ANN-UMS-")
    assert ann.attachment_present is False

    with pytest.raises(ValueError):
        adapter.normalize_announcement("not_a_dict")  # type: ignore


def test_live_check_connection_no_credentials():
    """Verify live check without credentials reports AUTH_REQUIRED safely."""
    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="")
    conn = adapter.check_connection()
    assert conn["connected"] is False
    assert conn["status"] == "AUTH_REQUIRED"


@patch("httpx.Client.get")
def test_live_check_connection_expired_redirect(mock_get):
    """Verify redirect to login page is flagged as AUTH_EXPIRED."""
    mock_resp = MagicMock()
    mock_resp.status_code = 302
    mock_resp.headers = {"location": "https://ums.lpu.in/lpuums/Login.aspx"}
    mock_get.return_value = mock_resp

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="ASP.NET_SessionId=dummy")
    conn = adapter.check_connection()
    assert conn["connected"] is False
    assert conn["status"] == "AUTH_EXPIRED"


@patch("httpx.Client.get")
def test_live_check_connection_forbidden(mock_get):
    """Verify 401/403 triggers AUTH_FORBIDDEN."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="ASP.NET_SessionId=dummy")
    conn = adapter.check_connection()
    assert conn["connected"] is False
    assert conn["status"] == "AUTH_FORBIDDEN"


@patch("httpx.Client.get")
def test_live_check_connection_rate_limit(mock_get):
    """Verify 429 returns RATE_LIMITED."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_get.return_value = mock_resp

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="ASP.NET_SessionId=dummy")
    conn = adapter.check_connection()
    assert conn["connected"] is False
    assert conn["status"] == "RATE_LIMITED"


@patch("httpx.Client.get")
def test_live_check_connection_timeout(mock_get):
    """Verify timeout is caught gracefully."""
    mock_get.side_effect = httpx.TimeoutException("Connection timed out")

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="ASP.NET_SessionId=dummy")
    conn = adapter.check_connection()
    assert conn["connected"] is False
    assert conn["status"] == "TIMEOUT"


@patch("httpx.Client.get")
def test_live_check_connection_network_error(mock_get):
    """Verify network connection error is caught gracefully."""
    mock_get.side_effect = httpx.RequestError("Host unreachable")

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="ASP.NET_SessionId=dummy")
    conn = adapter.check_connection()
    assert conn["connected"] is False
    assert conn["status"] == "CONNECTION_ERROR"


@patch("httpx.Client.post")
def test_live_fetch_aspnet_page_method(mock_post):
    """Verify parsing of ASP.NET WebMethod wrapper {'d': [...] } response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.content = b'{"d": [{"id": "9900"}]}'
    mock_resp.json.return_value = {
        "d": [
            {
                "id": "9900",
                "title": "Live ASP.NET Announcement",
                "full_content": "Notice content here",
                "publication_date": "2026-10-16",
            }
        ]
    }
    mock_post.return_value = mock_resp

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="valid_session")
    items = adapter.fetch_latest_announcements(limit=10)
    assert len(items) == 1
    assert items[0]["id"] == "9900"


@patch("httpx.Client.post")
def test_live_fetch_aspnet_stringified_json(mock_post):
    """Verify parsing of ASP.NET WebMethod wrapper {'d': 'stringified_json'}."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.content = b'{"d": "[{\\"id\\": \\"9901\\"}]"}'
    mock_resp.json.return_value = {
        "d": '[{"id": "9901", "title": "Stringified JSON Notice", "full_content": "Body text", "publication_date": "2026-10-17"}]'
    }
    mock_post.return_value = mock_resp

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="valid_session")
    items = adapter.fetch_latest_announcements(limit=10)
    assert len(items) == 1
    assert items[0]["id"] == "9901"
    assert items[0]["title"] == "Stringified JSON Notice"


@patch("httpx.Client.post")
def test_live_fetch_aspnet_table_dataset(mock_post):
    """Verify parsing of ASP.NET DataSet wrapper {'d': {'Table': [...]}}."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.content = b'{"d": {"Table": [{"id": "9902"}]}}'
    mock_resp.json.return_value = {
        "d": {
            "Table": [
                {
                    "NoticeId": "9902",
                    "NoticeTitle": "DataTable Notice",
                    "NoticeContent": "Content from ASP.NET DataTable",
                    "NoticeDate": "2026-10-18",
                }
            ]
        }
    }
    mock_post.return_value = mock_resp

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="valid_session")
    items = adapter.fetch_latest_announcements(limit=10)
    assert len(items) == 1
    assert items[0]["NoticeId"] == "9902"


@patch("httpx.Client.post")
def test_live_fetch_redirect_handling(mock_post):
    """Verify HTTP 302 redirect is safely detected as session expiration and handled without crashing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 302
    mock_resp.headers = {"location": "https://ums.lpu.in/lpuums/Login.aspx", "content-type": "text/html"}
    mock_resp.content = b'Object moved'
    mock_post.return_value = mock_resp

    adapter = UMSSourceAdapter(connector_mode="live", session_cookie="expired_session")
    # Should catch permission error and fallback to public feeds without crash
    with patch.object(adapter, "_fetch_from_lpu_feed", return_value=[]):
        with patch.object(adapter, "_fetch_from_lpude_notifications", return_value=[]):
            items = adapter.fetch_latest_announcements(limit=10)
            # Safe mock fallback when all live feeds return empty
            assert len(items) > 0


def test_html_parsing_containers_and_cards():
    """Verify HTML parser extracts notices from modern card and container div elements."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    html_content = """
    <div class="announcement-list">
        <div class="card announcement-box">
            <h3>Mid-Term Exam Seating Arrangement</h3>
            <p>Date: 20-Oct-2026 | Ref: LPU/EXAM/2026/401</p>
            <div class="content">Seating arrangement for all CSE students is available on UMS.</div>
            <a href="/downloads/Seating_Plan_2026.pdf">Download Seating Plan</a>
        </div>
    </div>
    """
    records = adapter.parse_html(html_content)
    assert len(records) == 1
    assert "Mid-Term Exam Seating Arrangement" in records[0]["title"]
    assert records[0]["attachment_present"] is True
    assert "Seating_Plan_2026.pdf" in records[0]["attachment_names"]


def test_html_multi_card_attachment_isolation():
    """Verify that multiple cards on a page do not contaminate each other's attachment lists."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    html_content = """
    <div class="card announcement-box">
        <h3>Card With PDF Attachment</h3>
        <p>Text for first card.</p>
        <a href="/docs/guide.pdf">Download Guide</a>
    </div>
    <div class="card announcement-box">
        <h3>Card Without Any Attachment</h3>
        <p>Text for second card without any attachments or download links.</p>
    </div>
    """
    records = adapter.parse_html(html_content)
    assert len(records) == 2
    assert records[0]["attachment_present"] is True
    assert "guide.pdf" in records[0]["attachment_names"]
    # Card 2 must NOT have inherited guide.pdf
    assert records[1]["attachment_present"] is False
    assert records[1]["attachment_names"] == []


def test_normalization_date_standardization():
    """Verify DD-Mon-YYYY and DD/MM/YYYY dates are standardized to YYYY-MM-DD."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    raw1 = {
        "title": "Date Test Notice 1",
        "full_content": "Notice content",
        "Date": "16-Oct-2026",
    }
    ann1 = adapter.normalize_announcement(raw1)
    assert ann1.publication_date == "2026-10-16"

    raw2 = {
        "title": "Date Test Notice 2",
        "full_content": "Notice content",
        "Date": "25/12/2026",
    }
    ann2 = adapter.normalize_announcement(raw2)
    assert ann2.publication_date == "2026-12-25"


def test_parse_raw_text_inline_attachment():
    """Verify inline attachment filenames ending in .pdf/.zip are detected without explicit header."""
    adapter = UMSSourceAdapter(connector_mode="mock")
    text = """
    Title: Practical Datesheet Autumn 2026
    Ref: LPU/PRAC/099
    Date: 2026-10-25
    Please download timetable_autumn_2026.pdf from the portal.
    """
    records = adapter.parse_raw_text(text)
    assert len(records) == 1
    assert records[0]["attachment_present"] is True
    assert "timetable_autumn_2026.pdf" in records[0]["attachment_names"]


