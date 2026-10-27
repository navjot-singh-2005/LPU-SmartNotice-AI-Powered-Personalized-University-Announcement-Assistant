import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.core.logging_config import logger

def get_db_connection() -> sqlite3.Connection:
    """Get SQLite database connection with row factory enabled and concurrency timeout."""
    db_path = Path(settings.SQLITE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Initialize SQLite database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table for AI Extracted Announcement Metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS extracted_metadata (
        announcement_id TEXT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        category TEXT,
        sub_category TEXT,
        summary TEXT,
        topics TEXT, -- JSON array string
        target_year TEXT, -- e.g. "1,2,3,4" or JSON list
        target_semester TEXT,
        target_program TEXT,
        target_department TEXT,
        target_school TEXT,
        target_section TEXT,
        eligibility TEXT,
        exclusions TEXT,
        event_date TEXT,
        start_time TEXT,
        end_time TEXT,
        deadline TEXT,
        location TEXT,
        building TEXT,
        room TEXT,
        room_range TEXT,
        affected_rooms TEXT,
        exempted_rooms TEXT,
        impact_type TEXT,
        action_required BOOLEAN,
        action_type TEXT,
        registration_required BOOLEAN,
        registration_link TEXT,
        required_documents TEXT,
        urgency TEXT, -- HIGH, MEDIUM, LOW, CRITICAL
        global_importance TEXT, -- HIGH, MEDIUM, LOW
        confidence REAL,
        attachment_present BOOLEAN,
        attachment_names TEXT, -- JSON array string
        attachment_content_available BOOLEAN,
        attachment_dependent BOOLEAN,
        requires_attachment_verification BOOLEAN,
        decision_completeness TEXT, -- COMPLETE, PARTIAL, ATTACHMENT_MISSING, UNKNOWN
        model_name TEXT,
        schema_version TEXT,
        processing_time_ms INTEGER,
        status TEXT, -- SUCCESS, REVIEW, FAILED
        raw_json TEXT, -- JSON representation of extracted metadata
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Index on extracted_metadata content_hash for caching
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_extracted_hash ON extracted_metadata(content_hash);
    """)

    # Table for Student Profiles (Synthetic Demo)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_profiles (
        student_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        program TEXT NOT NULL,
        department TEXT NOT NULL,
        school TEXT NOT NULL,
        year INTEGER NOT NULL,
        semester INTEGER NOT NULL,
        section TEXT,
        interests TEXT, -- JSON array string
        career_goal TEXT
    );
    """)

    # Table for Student Timetable Schedules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_timetable (
        entry_id TEXT PRIMARY KEY,
        student_id TEXT NOT NULL,
        day_or_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        course_code TEXT NOT NULL,
        course_name TEXT NOT NULL,
        room TEXT NOT NULL,
        building TEXT DEFAULT 'Block 34',
        faculty TEXT,
        section TEXT,
        effective_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES student_profiles(student_id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_timetable_student ON student_timetable(student_id);
    """)

    # Table for User Feedback
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS student_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        announcement_id TEXT NOT NULL,
        is_relevant BOOLEAN NOT NULL,
        feedback_type TEXT, -- RELEVANCE, ACCURACY, TIMELINESS
        comments TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table for Indexing Run Metadata
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS index_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table for Live / Synced Announcements
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS live_announcements (
        announcement_id TEXT PRIMARY KEY,
        source_id TEXT,
        title TEXT NOT NULL,
        publication_date TEXT NOT NULL,
        reference_number TEXT,
        full_content TEXT NOT NULL,
        attachment_present BOOLEAN DEFAULT 0,
        attachment_names TEXT, -- JSON array string
        content_hash TEXT NOT NULL,
        source TEXT DEFAULT 'ums',
        source_url TEXT,
        revision_count INTEGER DEFAULT 1,
        is_detail_complete BOOLEAN DEFAULT 1,
        detail_fetch_error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_live_hash ON live_announcements(content_hash);
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_live_ref ON live_announcements(reference_number);
    """)

    # Table for UMS Sync Execution Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ums_sync_history (
        sync_id TEXT PRIMARY KEY,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        status TEXT NOT NULL, -- SUCCESS, FAILED, RUNNING, UP_TO_DATE, EMPTY_SOURCE, AUTH_REQUIRED
        fetched_count INTEGER DEFAULT 0,
        candidate_count INTEGER DEFAULT 0,
        inserted_count INTEGER DEFAULT 0,
        updated_count INTEGER DEFAULT 0,
        skipped_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        indexed_count INTEGER DEFAULT 0,
        message TEXT,
        error_message TEXT,
        triggered_by TEXT DEFAULT 'manual'
    );
    """)

    # Safe migration for new columns in live_announcements
    cursor.execute("PRAGMA table_info(live_announcements)")
    live_cols = {row["name"] for row in cursor.fetchall()}
    if "is_detail_complete" not in live_cols:
        cursor.execute("ALTER TABLE live_announcements ADD COLUMN is_detail_complete BOOLEAN DEFAULT 1")
    if "detail_fetch_error" not in live_cols:
        cursor.execute("ALTER TABLE live_announcements ADD COLUMN detail_fetch_error TEXT")

    # Safe migration for new columns in ums_sync_history if existing DB was created with older schema
    cursor.execute("PRAGMA table_info(ums_sync_history)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    if "candidate_count" not in existing_cols:
        cursor.execute("ALTER TABLE ums_sync_history ADD COLUMN candidate_count INTEGER DEFAULT 0")
    if "indexed_count" not in existing_cols:
        cursor.execute("ALTER TABLE ums_sync_history ADD COLUMN indexed_count INTEGER DEFAULT 0")
    if "message" not in existing_cols:
        cursor.execute("ALTER TABLE ums_sync_history ADD COLUMN message TEXT")

    # Safe migration for new columns in student_profiles
    cursor.execute("PRAGMA table_info(student_profiles)")
    student_cols = {row["name"] for row in cursor.fetchall()}
    if "email" not in student_cols:
        cursor.execute("ALTER TABLE student_profiles ADD COLUMN email TEXT")

    conn.commit()

    # Populate default demo students if empty
    cursor.execute("SELECT COUNT(*) as count FROM student_profiles")
    if cursor.fetchone()["count"] == 0:
        demo_students = [
            (
                "STU-101",
                "Aarav Sharma",
                "B.Tech Computer Science & Engineering",
                "Department of Computer Science",
                "School of Computer Science and Engineering",
                3,
                5,
                "K21AB",
                '["Competitive Programming", "Web Development", "AI/ML", "Placements", "Hackathons"]',
                "Software Development Engineer"
            ),
            (
                "STU-102",
                "Priya Patel",
                "B.Tech Mechanical Engineering",
                "Department of Mechanical Engineering",
                "School of Mechanical Engineering",
                2,
                3,
                "M22CD",
                '["Robotics", "CAD/CAM", "Automotive", "Internships", "Cultural Events"]',
                "Robotics Engineer"
            ),
            (
                "STU-103",
                "Rohan Verma",
                "MBA Business Analytics",
                "Department of Management",
                "Mittal School of Business",
                1,
                1,
                "B23EF",
                '["Finance", "Data Analytics", "Case Competitions", "Guest Lectures", "Exams"]',
                "Data Analyst / Consultant"
            ),
            (
                "STU-104",
                "Ananya Reddy",
                "B.Sc Agriculture",
                "Department of Agriculture",
                "School of Agriculture",
                4,
                7,
                "A20GH",
                '["Agritech", "Research Grants", "Field Studies", "Convocations", "Sports"]',
                "Agricultural Specialist"
            )
        ]
        cursor.executemany("""
        INSERT INTO student_profiles (
            student_id, name, program, department, school, year, semester, section, interests, career_goal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, demo_students)
        conn.commit()

    # Populate default demo timetable if empty
    cursor.execute("SELECT COUNT(*) as count FROM student_timetable")
    if cursor.fetchone()["count"] == 0:
        demo_timetable = [
            ("TT-101", "STU-101", "Monday", "09:00 AM", "10:00 AM", "CSE301", "Data Structures & Algorithms", "34-105", "Block 34", "Dr. Sharma", "K21AB", "2026-10-15"),
            ("TT-102", "STU-101", "Monday", "11:00 AM", "12:00 PM", "INT219", "Front End Web Development", "34-108", "Block 34", "Prof. Gupta", "K21AB", "2026-10-15"),
            ("TT-103", "STU-101", "Tuesday", "02:00 PM", "03:00 PM", "CSE316", "Operating Systems", "34-204", "Block 34", "Dr. Verma", "K21AB", "2026-10-16"),
            ("TT-104", "STU-101", "Wednesday", "10:00 AM", "11:00 AM", "MTH401", "Discrete Mathematics", "33-301", "Block 33", "Dr. Rao", "K21AB", "2026-10-17")
        ]
        cursor.executemany("""
        INSERT INTO student_timetable (
            entry_id, student_id, day_or_date, start_time, end_time, course_code, course_name, room, building, faculty, section, effective_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, demo_timetable)
        conn.commit()

    conn.close()
    logger.info("Database initialized successfully at %s", settings.SQLITE_PATH)

if __name__ == "__main__":
    init_db()
