from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "dataset_summary" in data

def test_announcements_paginated():
    response = client.get("/api/v1/announcements?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert len(data["items"]) <= 5

def test_students_list():
    response = client.get("/api/v1/students")
    assert response.status_code == 200
    students = response.json()
    assert len(students) > 0
    assert students[0]["student_id"] == "STU-101"

def test_student_feed():
    response = client.get("/api/v1/students/STU-101/feed?page=1&page_size=5")
    assert response.status_code == 200
    feed = response.json()
    assert feed["student_id"] == "STU-101"
    assert "feed" in feed
