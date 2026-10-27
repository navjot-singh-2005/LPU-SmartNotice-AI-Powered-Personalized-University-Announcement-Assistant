"""Unit and integration tests for the /announcements/deadlines API endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_deadlines_endpoint_success():
    """Verify that /api/v1/announcements/deadlines returns paginated deadlines."""
    res = client.get("/api/v1/announcements/deadlines?page=1&page_size=10&include_expired=true")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "items" in data
    assert "page" in data
    assert data["page"] == 1

    if data["items"]:
        first = data["items"][0]
        assert "announcement_id" in first
        assert "deadline" in first
        assert "iso_deadline" in first
        assert "is_expired" in first


def test_deadlines_sorting_chronological():
    """Verify that returned deadlines are chronologically ordered."""
    res = client.get("/api/v1/announcements/deadlines?page=1&page_size=20&include_expired=true")
    assert res.status_code == 200
    data = res.json()
    items = data["items"]

    if len(items) >= 2:
        iso_dates = [i["iso_deadline"] for i in items]
        assert iso_dates == sorted(iso_dates)


def test_deadlines_active_filtering():
    """Verify that include_expired=false excludes expired deadlines."""
    res_all = client.get("/api/v1/announcements/deadlines?include_expired=true")
    res_active = client.get("/api/v1/announcements/deadlines?include_expired=false")

    assert res_all.status_code == 200
    assert res_active.status_code == 200

    active_items = res_active.json()["items"]
    for item in active_items:
        assert item["is_expired"] is False
