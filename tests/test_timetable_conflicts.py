import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db_connection
from app.services.room_impact_service import RoomImpactService, parse_time_to_minutes, times_overlap, extract_replacement_room
from app.models.student import TimetableEntry, TimetableEntryInput
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_test_timetable_data():
    """Clean up test students and their timetable rows before and after tests."""
    test_ids = ["STU-TT-1", "STU-TT-2", "STU-TT-NO-CLASSES", "STU-TT-OVERLAP"]
    conn = get_db_connection()
    c = conn.cursor()
    for tid in test_ids:
        c.execute("DELETE FROM student_timetable WHERE student_id = ?", (tid,))
        c.execute("DELETE FROM student_profiles WHERE student_id = ?", (tid,))
    conn.commit()
    conn.close()
    yield
    conn = get_db_connection()
    c = conn.cursor()
    for tid in test_ids:
        c.execute("DELETE FROM student_timetable WHERE student_id = ?", (tid,))
        c.execute("DELETE FROM student_profiles WHERE student_id = ?", (tid,))
    conn.commit()
    conn.close()

def test_scenario_1_create_student_with_multiple_timetable_entries():
    """1. Create a student with multiple timetable entries."""
    payload = {
        "student_id": "STU-TT-1",
        "name": "Priya Sharma",
        "email": "priya.sharma@lpu.in",
        "program": "B.Tech Computer Science & Engineering",
        "department": "Department of CSE",
        "school": "School of Computer Science and Engineering",
        "year": 3,
        "semester": 5,
        "section": "K22AB",
        "interests": ["Machine Learning", "Data Engineering"],
        "career_goal": "AI Engineer",
        "timetable": [
            {
                "day_or_date": "Monday",
                "start_time": "09:00 AM",
                "end_time": "10:00 AM",
                "course_code": "CSE310",
                "course_name": "Machine Learning",
                "room": "34-105",
                "building": "Block 34",
                "faculty": "Dr. Raman",
                "section": "K22AB"
            },
            {
                "day_or_date": "Tuesday",
                "start_time": "11:00 AM",
                "end_time": "12:00 PM",
                "course_code": "CSE316",
                "course_name": "Operating Systems",
                "room": "34-204",
                "building": "Block 34",
                "faculty": "Prof. Verma",
                "section": "K22AB"
            }
        ]
    }
    res = client.post("/api/v1/students", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["student_id"] == "STU-TT-1"
    assert len(data["timetable"]) == 2
    assert data["timetable"][0]["course_code"] == "CSE310"
    assert data["timetable"][1]["course_code"] == "CSE316"

def test_scenario_2_save_student_without_timetable_entries():
    """2. Save a student without timetable entries if existing requirements allow it."""
    payload = {
        "student_id": "STU-TT-NO-CLASSES",
        "name": "Deepak Kumar",
        "program": "B.Sc Physics",
        "department": "Department of Physics",
        "school": "School of Chemical Engineering and Physical Sciences",
        "year": 1,
        "semester": 1,
        "timetable": []
    }
    res = client.post("/api/v1/students", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["student_id"] == "STU-TT-NO-CLASSES"
    assert len(data["timetable"]) == 0

def test_scenario_3_edit_student_without_changing_another_student():
    """3. Edit student details without changing another student's data."""
    # Create student 1
    client.post("/api/v1/students", json={
        "student_id": "STU-TT-1",
        "name": "Student One",
        "program": "B.Tech CSE",
        "department": "CSE",
        "school": "SCSE",
        "year": 2,
        "semester": 3,
        "timetable": [{
            "day_or_date": "Monday",
            "start_time": "09:00 AM",
            "end_time": "10:00 AM",
            "course_code": "CSE201",
            "course_name": "Data Structures",
            "room": "34-101"
        }]
    })

    # Create student 2
    client.post("/api/v1/students", json={
        "student_id": "STU-TT-2",
        "name": "Student Two",
        "program": "B.Tech ECE",
        "department": "ECE",
        "school": "SECE",
        "year": 2,
        "semester": 3,
        "timetable": [{
            "day_or_date": "Friday",
            "start_time": "02:00 PM",
            "end_time": "03:00 PM",
            "course_code": "ECE205",
            "course_name": "Digital Circuits",
            "room": "34-305"
        }]
    })

    # Update student 1
    update_res = client.put("/api/v1/students/STU-TT-1", json={
        "name": "Student One Updated",
        "timetable": [{
            "day_or_date": "Wednesday",
            "start_time": "10:00 AM",
            "end_time": "11:00 AM",
            "course_code": "CSE205",
            "course_name": "Algorithms",
            "room": "34-102"
        }]
    })
    assert update_res.status_code == 200

    # Verify student 2 was NOT changed
    stu2_res = client.get("/api/v1/students/STU-TT-2")
    assert stu2_res.status_code == 200
    stu2_data = stu2_res.json()
    assert stu2_data["name"] == "Student Two"
    assert len(stu2_data["timetable"]) == 1
    assert stu2_data["timetable"][0]["course_code"] == "ECE205"

def test_scenario_4_add_edit_and_remove_timetable_entries():
    """4. Add, edit, and remove timetable entries via API."""
    client.post("/api/v1/students", json={
        "student_id": "STU-TT-1",
        "name": "Test Student",
        "program": "B.Tech CSE",
        "department": "CSE",
        "school": "SCSE",
        "year": 1,
        "semester": 1,
        "timetable": [
            {
                "day_or_date": "Monday",
                "start_time": "09:00 AM",
                "end_time": "10:00 AM",
                "course_code": "MTH101",
                "course_name": "Calculus",
                "room": "34-101"
            },
            {
                "day_or_date": "Monday",
                "start_time": "11:00 AM",
                "end_time": "12:00 PM",
                "course_code": "PHY101",
                "course_name": "Physics",
                "room": "34-102"
            }
        ]
    })

    # Update timetable: remove PHY101, edit MTH101 time, add CHE101
    put_tt = client.put("/api/v1/students/STU-TT-1/timetable", json=[
        {
            "day_or_date": "Monday",
            "start_time": "08:30 AM",
            "end_time": "09:30 AM",
            "course_code": "MTH101",
            "course_name": "Advanced Calculus",
            "room": "34-101"
        },
        {
            "day_or_date": "Thursday",
            "start_time": "02:00 PM",
            "end_time": "03:00 PM",
            "course_code": "CHE101",
            "course_name": "Chemistry",
            "room": "34-205"
        }
    ])
    assert put_tt.status_code == 200
    updated_entries = put_tt.json()
    assert len(updated_entries) == 2
    codes = [e["course_code"] for e in updated_entries]
    assert "MTH101" in codes
    assert "CHE101" in codes
    assert "PHY101" not in codes

def test_scenario_5_detect_overlapping_classes_and_display_red():
    """5. Overlapping classes are saved (not blocked) and detected as RED conflicts."""
    # 5a. Save overlapping classes on same day (10:00-11:00 and 10:30-11:30) — should succeed
    res = client.post("/api/v1/students", json={
        "student_id": "STU-TT-OVERLAP",
        "name": "Overlap Student",
        "program": "B.Tech CSE",
        "department": "CSE",
        "school": "SCSE",
        "year": 1,
        "semester": 1,
        "timetable": [
            {
                "day_or_date": "Wednesday",
                "start_time": "10:00 AM",
                "end_time": "11:00 AM",
                "course_code": "CSE101",
                "course_name": "Intro to C",
                "room": "34-101"
            },
            {
                "day_or_date": "Wednesday",
                "start_time": "10:30 AM",
                "end_time": "11:30 AM",
                "course_code": "CSE102",
                "course_name": "Intro to Python",
                "room": "34-102"
            }
        ]
    })
    # Overlapping entries are now saved successfully (not blocked)
    assert res.status_code == 201
    data = res.json()
    assert len(data["timetable"]) == 2

    # 5b. Verify RoomImpactService flags internal overlaps with indicator_color='RED'
    ris = RoomImpactService()
    entries = [
        TimetableEntry(
            entry_id="TT-1",
            student_id="STU-SAMPLE",
            day_or_date="Wednesday",
            start_time="10:00 AM",
            end_time="11:00 AM",
            course_code="CSE101",
            course_name="Intro to C",
            room="34-101"
        ),
        TimetableEntry(
            entry_id="TT-2",
            student_id="STU-SAMPLE",
            day_or_date="Wednesday",
            start_time="10:30 AM",
            end_time="11:30 AM",
            course_code="CSE102",
            course_name="Intro to Python",
            room="34-102"
        )
    ]
    internal_conflicts = ris.detect_internal_timetable_conflicts(entries)
    assert "TT-1" in internal_conflicts
    assert "TT-2" in internal_conflicts

    # 5c. Verify evaluate_student_timetable shows them as RED
    results = ris.evaluate_student_timetable("STU-TT-OVERLAP", announcements=[])
    red_results = [r for r in results if r.indicator_color == "RED"]
    assert len(red_results) == 2
    assert all(r.conflict_type == "INTERNAL_OVERLAP" for r in red_results)

def test_scenario_6_confirm_non_overlapping_classes_display_green():
    """6. Confirm non-overlapping classes can display GREEN after checks complete."""
    # Adjacent classes: 10:00-11:00 and 11:00-12:00 do not overlap
    assert times_overlap(600, 660, 660, 720) is False

    ris = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-CLEAR",
        student_id="STU-101",
        day_or_date="Monday",
        start_time="10:00 AM",
        end_time="11:00 AM",
        course_code="CSE301",
        course_name="Data Structures",
        room="34-105"
    )
    ann = RawAnnouncement(
        announcement_id="ANN-UNRELATED",
        title="Faculty Development Program in Block 55",
        publication_date="2026-10-25",
        full_content="All engineering faculty are invited to seminar hall Block 55."
    )
    res = ris.check_timetable_conflict(entry, ann)
    assert res.affected is False
    assert res.indicator_color == "GREEN"
    assert "verified clear" in res.explanation.lower() or "no conflict" in res.explanation.lower()

def test_scenario_7_detect_examination_notice_conflict():
    """7. Detect an examination notice that conflicts with a scheduled class."""
    ris = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-EXAM-TEST",
        student_id="STU-101",
        day_or_date="Monday",
        start_time="09:00 AM",
        end_time="11:00 AM",
        course_code="CSE301",
        course_name="Data Structures",
        room="34-105"
    )
    ann = RawAnnouncement(
        announcement_id="ANN-EXAM-1",
        title="Mid-Term Examination Seating Plan for CSE301 in Room 34-105",
        publication_date="2026-10-25",
        full_content="Final exam for CSE301 will take place in Room 34-105. All regular classes in Room 34-105 are suspended."
    )
    meta = ExtractedAnnouncementMetadata(
        announcement_id="ANN-EXAM-1",
        category="EXAMINATION",
        summary="Mid-term exam scheduled in 34-105",
        affected_rooms=["34-105"],
        impact_type="EXAM_DUTY"
    )
    res = ris.check_timetable_conflict(entry, ann, meta)
    assert res.affected is True
    assert res.indicator_color == "RED"
    assert res.announcement_id == "ANN-EXAM-1"

def test_scenario_8_detect_explicit_room_exemption():
    """8. Detect an explicit room exemption for the correct room and time."""
    ris = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-EXEMPT-TEST",
        student_id="STU-101",
        day_or_date="Monday",
        start_time="09:00 AM",
        end_time="10:00 AM",
        course_code="CSE301",
        course_name="Data Structures",
        room="34-105"
    )
    ann = RawAnnouncement(
        announcement_id="ANN-EXEMPT-1",
        title="Sanitization of Block 34 - Room 34-105 Exempted",
        publication_date="2026-10-25",
        full_content="General sanitization in Block 34. Except Room 34-105, which is exempted for practical lab."
    )
    meta = ExtractedAnnouncementMetadata(
        announcement_id="ANN-EXEMPT-1",
        category="ACADEMIC",
        summary="Sanitization of Block 34 with Room 34-105 exempted",
        affected_rooms=["34-101", "34-102"],
        exempted_rooms=["34-105"]
    )
    res = ris.check_timetable_conflict(entry, ann, meta)
    assert res.status == "EXEMPTED"
    assert "exempted" in res.explanation.lower()

def test_scenario_9_display_replacement_room():
    """9. Display a replacement room when the notice specifies one."""
    sample_notice = "Due to renovation work in Room 34-105, all lectures are relocated to Room 34-201."
    repl_room = extract_replacement_room(sample_notice)
    assert repl_room == "34-201"

    ris = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-RELOC-TEST",
        student_id="STU-101",
        day_or_date="Tuesday",
        start_time="09:00 AM",
        end_time="10:00 AM",
        course_code="CSE301",
        course_name="Data Structures",
        room="34-105"
    )
    ann = RawAnnouncement(
        announcement_id="ANN-RELOC-1",
        title="Class Relocation for Room 34-105",
        publication_date="2026-10-25",
        full_content=sample_notice
    )
    meta = ExtractedAnnouncementMetadata(
        announcement_id="ANN-RELOC-1",
        category="ACADEMIC",
        summary="Relocation of Room 34-105 to 34-201",
        affected_rooms=["34-105"],
        impact_type="VENUE_CHANGE"
    )
    res = ris.check_timetable_conflict(entry, ann, meta)
    assert res.indicator_color == "RED"
    assert res.replacement_room == "34-201"
    assert "34-201" in res.explanation

def test_scenario_10_display_amber_for_incomplete_or_ambiguous_notice():
    """10. Display AMBER for incomplete or ambiguous notice information."""
    ris = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-AMBER-TEST",
        student_id="STU-101",
        day_or_date="Wednesday",
        start_time="09:00 AM",
        end_time="10:00 AM",
        course_code="CSE301",
        course_name="Data Structures",
        room="34-105"
    )
    ann = RawAnnouncement(
        announcement_id="ANN-AMBER-1",
        title="Schedule changes for Block 34",
        publication_date="2026-10-25",
        full_content="Notice regarding changes in Block 34. Check attached excel sheet for individual room rosters."
    )
    meta = ExtractedAnnouncementMetadata(
        announcement_id="ANN-AMBER-1",
        category="ACADEMIC",
        summary="Schedule changes for Block 34 in attachment",
        affected_rooms=[],
        is_attachment_dependent=True
    )
    res = ris.check_timetable_conflict(entry, ann, meta)
    assert res.indicator_color == "AMBER"
    assert res.status == "ATTACHMENT_DEPENDENT"

def test_scenario_11_verify_unrelated_notices_do_not_create_false_conflicts():
    """11. Verify that unrelated notices do not create false conflicts."""
    ris = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-101",
        student_id="STU-101",
        day_or_date="Monday",
        start_time="09:00 AM",
        end_time="10:00 AM",
        course_code="CSE301",
        course_name="Data Structures",
        room="34-105"
    )
    ann = RawAnnouncement(
        announcement_id="ANN-SPORTS",
        title="Inter-Hostel Badminton Tournament in Uni-Center Block 13",
        publication_date="2026-10-25",
        full_content="Badminton matches will commence from 4 PM at Block 13 sports arena."
    )
    res = ris.check_timetable_conflict(entry, ann)
    assert res.indicator_color == "GREEN"
    assert res.affected is False

def test_scenario_12_timetable_entries_persist_in_db():
    """12. Verify that timetable entries persist in SQLite database."""
    client.post("/api/v1/students", json={
        "student_id": "STU-TT-1",
        "name": "Persistence Check",
        "program": "B.Tech CSE",
        "department": "CSE",
        "school": "SCSE",
        "year": 1,
        "semester": 1,
        "timetable": [
            {
                "day_or_date": "Monday",
                "start_time": "09:00 AM",
                "end_time": "10:00 AM",
                "course_code": "CSE101",
                "course_name": "Intro to Computing",
                "room": "34-105"
            }
        ]
    })

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM student_timetable WHERE student_id = 'STU-TT-1'")
    rows = c.fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0]["course_code"] == "CSE101"
    assert rows[0]["room"] == "34-105"

def test_scenario_13_recalculate_affected_statuses_on_relevant_notice():
    """13. Verify that adding or evaluating a relevant notice recalculates affected statuses."""
    ris = RoomImpactService()
    entries = [
        TimetableEntry(
            entry_id="TT-LIVE-TEST",
            student_id="STU-101",
            day_or_date="Monday",
            start_time="09:00 AM",
            end_time="10:00 AM",
            course_code="CSE301",
            course_name="Data Structures",
            room="34-105"
        )
    ]
    # Without notice
    res_before = ris.evaluate_student_timetable("STU-101", announcements=[])
    # STU-101 has 4 default classes all verified green
    assert all(r.indicator_color == "GREEN" for r in res_before)

    # Now add notice affecting Room 34-105
    ann = RawAnnouncement(
        announcement_id="ANN-NEW-ALERT",
        title="Emergency Closure of Room 34-105 for Electrical Repairs",
        publication_date="2026-10-28",
        full_content="Room 34-105 is suspended until further notice."
    )
    meta = ExtractedAnnouncementMetadata(
        announcement_id="ANN-NEW-ALERT",
        category="ACADEMIC",
        summary="Emergency closure of Room 34-105",
        affected_rooms=["34-105"],
        impact_type="SUSPENSION"
    )
    res_after = ris.evaluate_student_timetable("STU-101", announcements=[ann], metadata_map={"ANN-NEW-ALERT": meta})
    red_items = [r for r in res_after if r.indicator_color == "RED"]
    assert len(red_items) >= 1
    assert red_items[0].entry.room == "34-105"

def test_scenario_14_confirm_existing_features_continue_to_work():
    """14. Confirm all existing application features continue to work."""
    # Health check
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200

    # Students list
    res_students = client.get("/api/v1/students")
    assert res_students.status_code == 200

    # Personalized feed
    res_feed = client.get("/api/v1/feed/STU-101/feed")
    assert res_feed.status_code == 200
    assert "feed" in res_feed.json()

    # Affected classes feed endpoint
    res_aff = client.get("/api/v1/feed/STU-101/affected-classes")
    assert res_aff.status_code == 200
    data = res_aff.json()
    assert "impacts" in data
    assert "red_count" in data
    assert "green_count" in data
