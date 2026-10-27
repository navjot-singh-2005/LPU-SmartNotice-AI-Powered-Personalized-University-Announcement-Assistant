from app.services.room_impact_service import RoomImpactService
from app.models.student import TimetableEntry

def test_room_string_normalization():
    service = RoomImpactService()
    assert service.normalize_room_string("Block 34, Room 105") == ["34-105"]
    assert service.normalize_room_string("34-105") == ["34-105"]

def test_room_range_expansion():
    service = RoomImpactService()
    rooms = service.parse_room_range("Rooms 34-101 to 34-105")
    assert rooms == ["34-101", "34-102", "34-103", "34-104", "34-105"]

def test_timetable_conflict_confirmed_match(sample_raw_announcement, sample_extracted_metadata):
    service = RoomImpactService()
    entry = TimetableEntry(
        entry_id="TT-1",
        student_id="STU-101",
        day_or_date="2026-10-15",
        start_time="09:00 AM",
        end_time="10:00 AM",
        course_code="CSE301",
        course_name="Data Structures",
        room="34-105"
    )

    res = service.check_timetable_conflict(entry, sample_raw_announcement, sample_extracted_metadata)

    assert res.affected is True
    assert res.status == "CONFIRMED_MATCH"
    assert "34-105" in res.explanation
