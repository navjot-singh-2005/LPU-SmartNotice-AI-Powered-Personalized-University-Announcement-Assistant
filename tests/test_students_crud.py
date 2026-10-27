import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db_connection

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_test_students():
    """Ensure test students are cleaned up before and after tests."""
    test_ids = ["STU-TEST-999", "STU-TEST-888", "STU-DUP-1"]
    conn = get_db_connection()
    c = conn.cursor()
    for tid in test_ids:
        c.execute("DELETE FROM student_profiles WHERE student_id = ?", (tid,))
    conn.commit()
    conn.close()
    yield
    conn = get_db_connection()
    c = conn.cursor()
    for tid in test_ids:
        c.execute("DELETE FROM student_profiles WHERE student_id = ?", (tid,))
    conn.commit()
    conn.close()

def test_add_student_valid():
    """1. Add a new student with valid details."""
    payload = {
        "student_id": "STU-TEST-999",
        "name": "Arjun Singhania",
        "email": "arjun.singhania@lpu.in",
        "program": "B.Tech Information Technology",
        "department": "Department of IT",
        "school": "School of Computer Science and Engineering",
        "year": 2,
        "semester": 4,
        "section": "IT22A",
        "interests": ["Cloud Computing", "Cybersecurity", "DevOps"],
        "career_goal": "Cloud Solutions Architect"
    }
    response = client.post("/api/v1/students", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == "STU-TEST-999"
    assert data["name"] == "Arjun Singhania"
    assert data["email"] == "arjun.singhania@lpu.in"
    assert data["year"] == 2
    assert "Cloud Computing" in data["interests"]

    # 4. Verify the new student remains in DB
    get_res = client.get("/api/v1/students/STU-TEST-999")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Arjun Singhania"

def test_add_student_missing_required_fields():
    """2. Reject invalid or missing required values."""
    # Missing required name & program
    payload = {
        "student_id": "STU-TEST-999",
        "year": 2,
        "semester": 3
    }
    response = client.post("/api/v1/students", json=payload)
    assert response.status_code == 422

    # Empty string name
    payload2 = {
        "student_id": "STU-TEST-999",
        "name": "   ",
        "program": "B.Tech CSE",
        "department": "CSE",
        "school": "SCSE",
        "year": 1,
        "semester": 1
    }
    response2 = client.post("/api/v1/students", json=payload2)
    assert response2.status_code == 422

    # Invalid email format
    payload3 = {
        "student_id": "STU-TEST-999",
        "name": "Test Student",
        "email": "not-a-valid-email",
        "program": "B.Tech CSE",
        "department": "CSE",
        "school": "SCSE",
        "year": 1,
        "semester": 1
    }
    response3 = client.post("/api/v1/students", json=payload3)
    assert response3.status_code == 422

def test_add_student_duplicate_id_prevented():
    """3. Prevent duplicate student IDs or registration numbers."""
    payload = {
        "student_id": "STU-DUP-1",
        "name": "Original Student",
        "program": "B.Tech CSE",
        "department": "CSE",
        "school": "SCSE",
        "year": 1,
        "semester": 1
    }
    res1 = client.post("/api/v1/students", json=payload)
    assert res1.status_code == 201

    # Try creating student with duplicate ID
    dup_payload = {
        "student_id": "STU-DUP-1",
        "name": "Duplicate Student",
        "program": "B.Tech ECE",
        "department": "ECE",
        "school": "SECE",
        "year": 2,
        "semester": 3
    }
    res2 = client.post("/api/v1/students", json=dup_payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]

def test_get_existing_student_by_id():
    """5. Confirm existing values can be retrieved by ID."""
    res = client.get("/api/v1/students/STU-101")
    assert res.status_code == 200
    data = res.json()
    assert data["student_id"] == "STU-101"
    assert data["name"] == "Aarav Sharma"
    assert data["year"] == 3

def test_edit_student_details_and_persist():
    """6. Update the student's details and verify database record changes."""
    # First create a test student
    payload = {
        "student_id": "STU-TEST-888",
        "name": "Kavita Rao",
        "email": "kavita.initial@lpu.in",
        "program": "B.Design",
        "department": "Department of Design",
        "school": "School of Design",
        "year": 1,
        "semester": 2,
        "section": "D23A",
        "interests": ["UI/UX", "Graphic Design"],
        "career_goal": "Product Designer"
    }
    create_res = client.post("/api/v1/students", json=payload)
    assert create_res.status_code == 201

    # Update Kavita's details
    update_payload = {
        "name": "Kavita R. Rao",
        "email": "kavita.rao@lpu.in",
        "year": 2,
        "semester": 3,
        "section": "D23B",
        "interests": ["UI/UX", "Design Systems", "Figma"],
        "career_goal": "Lead Product Designer"
    }
    update_res = client.put("/api/v1/students/STU-TEST-888", json=update_payload)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["name"] == "Kavita R. Rao"
    assert updated["email"] == "kavita.rao@lpu.in"
    assert updated["year"] == 2
    assert updated["semester"] == 3
    assert updated["section"] == "D23B"
    assert "Design Systems" in updated["interests"]
    assert updated["career_goal"] == "Lead Product Designer"

    # Verify directly via GET
    get_res = client.get("/api/v1/students/STU-TEST-888")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Kavita R. Rao"

def test_edit_one_student_does_not_affect_another():
    """8. Confirm editing one student does not affect another student."""
    # Read STU-101 before
    s101_before = client.get("/api/v1/students/STU-101").json()

    # Create & edit another student
    payload = {
        "student_id": "STU-TEST-999",
        "name": "Isolation Test Student",
        "program": "B.Tech CSE",
        "department": "CSE",
        "school": "SCSE",
        "year": 1,
        "semester": 1
    }
    client.post("/api/v1/students", json=payload)
    client.put("/api/v1/students/STU-TEST-999", json={"name": "Modified Isolated Student", "year": 4})

    # Read STU-101 after
    s101_after = client.get("/api/v1/students/STU-101").json()
    assert s101_before["name"] == s101_after["name"]
    assert s101_before["year"] == s101_after["year"]
    assert s101_before["student_id"] == s101_after["student_id"]

def test_edit_non_existent_student_returns_404():
    """9. Verify 404 when student not found."""
    res = client.put("/api/v1/students/NON_EXISTENT_9999", json={"name": "Nobody"})
    assert res.status_code == 404
