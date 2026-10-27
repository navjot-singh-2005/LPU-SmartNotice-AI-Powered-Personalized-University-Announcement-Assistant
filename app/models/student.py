import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

class TimetableEntry(BaseModel):
    """Represents a scheduled class entry for a student."""
    entry_id: str
    student_id: str
    day_or_date: str  # e.g. "Monday" or "2026-10-15"
    start_time: str   # e.g. "09:00 AM"
    end_time: str     # e.g. "10:00 AM"
    course_code: str  # e.g. "CSE301"
    course_name: str  # e.g. "Data Structures & Algorithms"
    room: str         # e.g. "34-105"
    building: Optional[str] = "Block 34"
    faculty: Optional[str] = None
    section: Optional[str] = None
    effective_date: Optional[str] = None

class TimetableEntryInput(BaseModel):
    """Input payload when creating or updating timetable entries."""
    entry_id: Optional[str] = None
    day_or_date: str
    start_time: str
    end_time: str
    course_code: str
    course_name: str
    room: str
    building: Optional[str] = "Block 34"
    faculty: Optional[str] = None
    section: Optional[str] = None
    effective_date: Optional[str] = None

class StudentProfile(BaseModel):
    """Represents a student profile for personalization and feed ranking."""
    student_id: str
    name: str
    email: Optional[str] = None
    program: str
    department: str
    school: str
    year: int
    semester: int
    section: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    career_goal: Optional[str] = None
    timetable: Optional[List[TimetableEntry]] = Field(default_factory=list)

class StudentCreate(BaseModel):
    """Payload to create a new student profile."""
    student_id: str = Field(..., min_length=1, description="Unique Student ID / Reg No")
    name: str = Field(..., min_length=1, description="Student Full Name")
    email: Optional[str] = Field(default=None, description="Student Email Address")
    program: str = Field(..., min_length=1, description="Program / Degree")
    department: str = Field(..., min_length=1, description="Department")
    school: str = Field(..., min_length=1, description="School")
    year: int = Field(..., ge=1, le=10, description="Academic Year")
    semester: int = Field(..., ge=1, le=20, description="Semester")
    section: Optional[str] = Field(default=None, description="Section / Batch")
    interests: List[str] = Field(default_factory=list, description="Academic / Career Interests")
    career_goal: Optional[str] = Field(default=None, description="Career Goal")
    timetable: Optional[List[TimetableEntryInput]] = Field(default=None, description="Student Timetable Schedule")

    @field_validator("student_id", "name", "program", "department", "school")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or blank")
        return v.strip()

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() != "":
            clean = v.strip()
            if not EMAIL_REGEX.match(clean):
                raise ValueError("Invalid email format. Please provide a valid email address.")
            return clean
        return None

class StudentUpdate(BaseModel):
    """Payload to update an existing student profile."""
    name: Optional[str] = Field(default=None, min_length=1, description="Student Full Name")
    email: Optional[str] = Field(default=None, description="Student Email Address")
    program: Optional[str] = Field(default=None, min_length=1, description="Program / Degree")
    department: Optional[str] = Field(default=None, min_length=1, description="Department")
    school: Optional[str] = Field(default=None, min_length=1, description="School")
    year: Optional[int] = Field(default=None, ge=1, le=10, description="Academic Year")
    semester: Optional[int] = Field(default=None, ge=1, le=20, description="Semester")
    section: Optional[str] = Field(default=None, description="Section / Batch")
    interests: Optional[List[str]] = Field(default=None, description="Academic / Career Interests")
    career_goal: Optional[str] = Field(default=None, description="Career Goal")
    timetable: Optional[List["TimetableEntryInput"]] = Field(default=None, description="Student Timetable Schedule")

    @field_validator("name", "program", "department", "school")
    @classmethod
    def validate_non_empty_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("Field cannot be empty or blank")
            return v.strip()
        return None

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() != "":
            clean = v.strip()
            if not EMAIL_REGEX.match(clean):
                raise ValueError("Invalid email format. Please provide a valid email address.")
            return clean
        return None

class ClassImpactResult(BaseModel):
    """Represents the room impact and conflict analysis result for a student class."""
    entry: TimetableEntry
    affected: bool
    status: str # "RED_CONFLICT", "AMBER_VERIFY", "GREEN_CLEAR", "CONFIRMED_MATCH", "EXEMPTED", "POTENTIAL_IMPACT", "ATTACHMENT_DEPENDENT", "NO_MATCH", "UNCERTAIN_DATA"
    indicator_color: str = "GREEN" # "RED", "AMBER", "GREEN"
    conflict_type: str = "NONE" # "INTERNAL_OVERLAP", "EXAM_OVERLAP", "ROOM_CLOSURE", "ROOM_EXEMPTION", "VENUE_CHANGE", "CANCELLATION", "NONE"
    impact_type: Optional[str] = "NONE" # "SUSPENSION", "VENUE_CHANGE", "EXAM_DUTY", "RESCHEDULED", "GENERAL_ALERT", "NONE"
    announcement_id: Optional[str] = None
    announcement_title: Optional[str] = None
    evidence_text: Optional[str] = None
    replacement_room: Optional[str] = None
    conflicting_entry_id: Optional[str] = None
    conflicting_entry_title: Optional[str] = None
    explanation: str
