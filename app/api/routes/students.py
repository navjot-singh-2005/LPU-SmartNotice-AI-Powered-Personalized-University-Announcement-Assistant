import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from app.core.database import get_db_connection
from app.models.student import (
    StudentProfile,
    StudentCreate,
    StudentUpdate,
    TimetableEntry,
    TimetableEntryInput
)
from app.services.room_impact_service import parse_time_to_minutes, times_overlap

router = APIRouter(prefix="/students", tags=["Student Profiles"])

def _fetch_timetable_for_student(cursor, student_id: str) -> List[TimetableEntry]:
    """Retrieve all timetable entries for a student from student_timetable table."""
    cursor.execute("""
        SELECT * FROM student_timetable
        WHERE student_id = ?
        ORDER BY day_or_date ASC, start_time ASC
    """, (student_id,))
    rows = cursor.fetchall()
    entries = []
    for r in rows:
        keys = r.keys()
        entries.append(TimetableEntry(
            entry_id=r["entry_id"],
            student_id=r["student_id"],
            day_or_date=r["day_or_date"],
            start_time=r["start_time"],
            end_time=r["end_time"],
            course_code=r["course_code"],
            course_name=r["course_name"],
            room=r["room"],
            building=r["building"] if "building" in keys else "Block 34",
            faculty=r["faculty"] if "faculty" in keys else None,
            section=r["section"] if "section" in keys else None,
            effective_date=r["effective_date"] if "effective_date" in keys else None
        ))
    return entries

def _row_to_student(row, cursor=None) -> StudentProfile:
    """Helper to convert a sqlite row to a StudentProfile model."""
    keys = row.keys()
    interests = json.loads(row["interests"]) if row["interests"] else []
    email = row["email"] if "email" in keys else None
    timetable = []
    if cursor is not None:
        timetable = _fetch_timetable_for_student(cursor, row["student_id"])

    return StudentProfile(
        student_id=row["student_id"],
        name=row["name"],
        email=email,
        program=row["program"],
        department=row["department"],
        school=row["school"],
        year=row["year"],
        semester=row["semester"],
        section=row["section"],
        interests=interests,
        career_goal=row["career_goal"],
        timetable=timetable
    )

def _validate_and_check_timetable(entries: List[TimetableEntryInput], student_id: str):
    """Validate timetable fields, time sequence, and internal time overlaps."""
    for i, e in enumerate(entries):
        if not e.day_or_date or not e.day_or_date.strip():
            raise HTTPException(status_code=400, detail=f"Timetable row #{i+1}: Day/Date cannot be blank.")
        if not e.start_time or not e.start_time.strip():
            raise HTTPException(status_code=400, detail=f"Timetable row #{i+1}: Start time cannot be blank.")
        if not e.end_time or not e.end_time.strip():
            raise HTTPException(status_code=400, detail=f"Timetable row #{i+1}: End time cannot be blank.")
        if not e.course_code or not e.course_code.strip():
            raise HTTPException(status_code=400, detail=f"Timetable row #{i+1}: Course code cannot be blank.")
        if not e.course_name or not e.course_name.strip():
            raise HTTPException(status_code=400, detail=f"Timetable row #{i+1}: Course name cannot be blank.")
        if not e.room or not e.room.strip():
            raise HTTPException(status_code=400, detail=f"Timetable row #{i+1}: Room cannot be blank.")

        s_min = parse_time_to_minutes(e.start_time)
        e_min = parse_time_to_minutes(e.end_time)
        if s_min is None or e_min is None:
            raise HTTPException(
                status_code=400,
                detail=f"Timetable row #{i+1} ({e.course_code}): Invalid time format for '{e.start_time}' or '{e.end_time}'. Please use 12-hour (e.g. '09:00 AM') or 24-hour ('09:00') format."
            )
        if s_min >= e_min:
            raise HTTPException(
                status_code=400,
                detail=f"Timetable row #{i+1} ({e.course_code}): Start time ({e.start_time}) must be earlier than end time ({e.end_time})."
            )
    # Note: Overlapping classes are allowed to be saved so that student schedule conflicts
    # are persistently stored and evaluated as confirmed RED conflicts in the Timetable Impact view.

@router.get("", response_model=List[StudentProfile])
def list_demo_students():
    """List all student profiles in the database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM student_profiles ORDER BY student_id ASC")
        rows = cursor.fetchall()
        return [_row_to_student(r, cursor) for r in rows]
    finally:
        conn.close()

@router.get("/{student_id}", response_model=StudentProfile)
def get_student(student_id: str):
    """Retrieve details of a single student by student_id."""
    clean_id = student_id.strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM student_profiles WHERE student_id = ?", (clean_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID '{clean_id}' not found."
            )
        return _row_to_student(row, cursor)
    finally:
        conn.close()

@router.post("", response_model=StudentProfile, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate):
    """Create a new student profile with timetable support and validation."""
    clean_id = payload.student_id.strip()

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT student_id FROM student_profiles WHERE LOWER(student_id) = LOWER(?)", (clean_id,))
        existing = cursor.fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Student with ID '{clean_id}' already exists."
            )

        if payload.timetable:
            _validate_and_check_timetable(payload.timetable, clean_id)

        interests_json = json.dumps(payload.interests or [])
        cursor.execute("""
            INSERT INTO student_profiles (
                student_id, name, email, program, department, school, year, semester, section, interests, career_goal
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clean_id,
            payload.name.strip(),
            payload.email.strip() if payload.email else None,
            payload.program.strip(),
            payload.department.strip(),
            payload.school.strip(),
            payload.year,
            payload.semester,
            payload.section.strip() if payload.section else None,
            interests_json,
            payload.career_goal.strip() if payload.career_goal else None
        ))

        if payload.timetable:
            for idx, entry in enumerate(payload.timetable):
                eid = entry.entry_id or f"TT-{clean_id}-{idx+1}-{uuid.uuid4().hex[:4]}"
                cursor.execute("""
                    INSERT INTO student_timetable (
                        entry_id, student_id, day_or_date, start_time, end_time, course_code, course_name, room, building, faculty, section, effective_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    eid,
                    clean_id,
                    entry.day_or_date.strip(),
                    entry.start_time.strip(),
                    entry.end_time.strip(),
                    entry.course_code.strip(),
                    entry.course_name.strip(),
                    entry.room.strip(),
                    (entry.building or "Block 34").strip(),
                    entry.faculty.strip() if entry.faculty else None,
                    entry.section.strip() if entry.section else None,
                    entry.effective_date.strip() if entry.effective_date else None
                ))

        conn.commit()

        cursor.execute("SELECT * FROM student_profiles WHERE student_id = ?", (clean_id,))
        created_row = cursor.fetchone()
        return _row_to_student(created_row, cursor)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create student: {str(e)}"
        )
    finally:
        conn.close()

@router.put("/{student_id}", response_model=StudentProfile)
@router.patch("/{student_id}", response_model=StudentProfile)
def update_student(student_id: str, payload: StudentUpdate):
    """Update details of an existing student profile, including timetable."""
    clean_id = student_id.strip()

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM student_profiles WHERE student_id = ?", (clean_id,))
        current_row = cursor.fetchone()
        if not current_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID '{clean_id}' not found."
            )

        keys = current_row.keys()
        current_email = current_row["email"] if "email" in keys else None
        current_interests = json.loads(current_row["interests"]) if current_row["interests"] else []

        new_name = payload.name.strip() if payload.name is not None else current_row["name"]
        new_email = payload.email.strip() if payload.email is not None else current_email
        new_program = payload.program.strip() if payload.program is not None else current_row["program"]
        new_dept = payload.department.strip() if payload.department is not None else current_row["department"]
        new_school = payload.school.strip() if payload.school is not None else current_row["school"]
        new_year = payload.year if payload.year is not None else current_row["year"]
        new_sem = payload.semester if payload.semester is not None else current_row["semester"]
        new_sec = payload.section.strip() if payload.section is not None else current_row["section"]
        new_career = payload.career_goal.strip() if payload.career_goal is not None else current_row["career_goal"]
        new_interests = payload.interests if payload.interests is not None else current_interests

        interests_json = json.dumps(new_interests)

        if payload.timetable is not None:
            _validate_and_check_timetable(payload.timetable, clean_id)

        cursor.execute("""
            UPDATE student_profiles
            SET name = ?,
                email = ?,
                program = ?,
                department = ?,
                school = ?,
                year = ?,
                semester = ?,
                section = ?,
                interests = ?,
                career_goal = ?
            WHERE student_id = ?
        """, (
            new_name,
            new_email,
            new_program,
            new_dept,
            new_school,
            new_year,
            new_sem,
            new_sec,
            interests_json,
            new_career,
            clean_id
        ))

        if payload.timetable is not None:
            cursor.execute("DELETE FROM student_timetable WHERE student_id = ?", (clean_id,))
            for idx, entry in enumerate(payload.timetable):
                eid = entry.entry_id or f"TT-{clean_id}-{idx+1}-{uuid.uuid4().hex[:4]}"
                cursor.execute("""
                    INSERT INTO student_timetable (
                        entry_id, student_id, day_or_date, start_time, end_time, course_code, course_name, room, building, faculty, section, effective_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    eid,
                    clean_id,
                    entry.day_or_date.strip(),
                    entry.start_time.strip(),
                    entry.end_time.strip(),
                    entry.course_code.strip(),
                    entry.course_name.strip(),
                    entry.room.strip(),
                    (entry.building or "Block 34").strip(),
                    entry.faculty.strip() if entry.faculty else None,
                    entry.section.strip() if entry.section else None,
                    entry.effective_date.strip() if entry.effective_date else None
                ))

        conn.commit()

        cursor.execute("SELECT * FROM student_profiles WHERE student_id = ?", (clean_id,))
        updated_row = cursor.fetchone()
        return _row_to_student(updated_row, cursor)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update student: {str(e)}"
        )
    finally:
        conn.close()

@router.get("/{student_id}/timetable", response_model=List[TimetableEntry])
def get_student_timetable(student_id: str):
    """Retrieve all timetable entries for a specific student."""
    clean_id = student_id.strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT student_id FROM student_profiles WHERE student_id = ?", (clean_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID '{clean_id}' not found."
            )
        return _fetch_timetable_for_student(cursor, clean_id)
    finally:
        conn.close()

@router.put("/{student_id}/timetable", response_model=List[TimetableEntry])
def update_student_timetable(student_id: str, entries: List[TimetableEntryInput]):
    """Update or replace student timetable entries."""
    clean_id = student_id.strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT student_id FROM student_profiles WHERE student_id = ?", (clean_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID '{clean_id}' not found."
            )
        _validate_and_check_timetable(entries, clean_id)
        cursor.execute("DELETE FROM student_timetable WHERE student_id = ?", (clean_id,))
        for idx, entry in enumerate(entries):
            eid = entry.entry_id or f"TT-{clean_id}-{idx+1}-{uuid.uuid4().hex[:4]}"
            cursor.execute("""
                INSERT INTO student_timetable (
                    entry_id, student_id, day_or_date, start_time, end_time, course_code, course_name, room, building, faculty, section, effective_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                eid,
                clean_id,
                entry.day_or_date.strip(),
                entry.start_time.strip(),
                entry.end_time.strip(),
                entry.course_code.strip(),
                entry.course_name.strip(),
                entry.room.strip(),
                (entry.building or "Block 34").strip(),
                entry.faculty.strip() if entry.faculty else None,
                entry.section.strip() if entry.section else None,
                entry.effective_date.strip() if entry.effective_date else None
            ))
        conn.commit()
        return _fetch_timetable_for_student(cursor, clean_id)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update timetable: {str(e)}"
        )
    finally:
        conn.close()
