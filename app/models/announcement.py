from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class ActionType(str, Enum):
    REGISTRATION = "REGISTRATION"
    SUBMIT_DOCUMENT = "SUBMIT_DOCUMENT"
    ATTEND_EVENT = "ATTEND_EVENT"
    CHANGE_ROOM = "CHANGE_ROOM"
    NO_CLASS = "NO_CLASS"
    EXAM = "EXAM"
    PAYMENT = "PAYMENT"
    APPLICATION = "APPLICATION"
    OTHER = "OTHER"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"

class UrgencyLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class GlobalImportance(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class DecisionCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    ATTACHMENT_MISSING = "ATTACHMENT_MISSING"
    UNKNOWN = "UNKNOWN"

class RawAnnouncement(BaseModel):
    """Represents a raw announcement record from the dataset."""
    announcement_id: str
    title: str
    publication_date: str
    reference_number: Optional[str] = None
    full_content: str
    attachment_present: bool = False
    attachment_names: List[str] = Field(default_factory=list)
    content_hash: Optional[str] = None
    source: Optional[str] = "historical"
    source_url: Optional[str] = None
    is_detail_complete: bool = True
    detail_fetch_error: Optional[str] = None

class ExtractedAnnouncementMetadata(BaseModel):
    """Pydantic schema for Gemini structured output and DB storage."""
    announcement_id: str
    category: str = Field(description="Category e.g. ACADEMIC, PLACEMENT, EVENT, EXAMINATION, HOSTEL, GENERAL")
    sub_category: Optional[str] = Field(default=None, description="Sub-category if applicable")
    summary: str = Field(description="Concise 1-2 sentence factual summary")
    topics: List[str] = Field(default_factory=list, description="Extracted keywords or topics")

    target_year: List[int] = Field(default_factory=list, description="Target academic years e.g. [1, 2], empty for all")
    target_semester: List[int] = Field(default_factory=list, description="Target semesters e.g. [3, 4], empty for all")
    target_program: Optional[str] = Field(default=None, description="Target degree program e.g. B.Tech CSE")
    target_department: Optional[str] = Field(default=None, description="Target department e.g. Department of Computer Science")
    target_school: Optional[str] = Field(default=None, description="Target school e.g. School of Computer Science")
    target_section: Optional[str] = Field(default=None, description="Target section e.g. K21AB")

    eligibility: Optional[str] = Field(default=None, description="Explicit eligibility conditions or criteria")
    exclusions: Optional[str] = Field(default=None, description="Explicitly excluded groups or criteria")

    event_date: Optional[str] = Field(default=None, description="Event date in YYYY-MM-DD or readable string")
    start_time: Optional[str] = Field(default=None, description="Start time e.g. 10:00 AM")
    end_time: Optional[str] = Field(default=None, description="End time e.g. 01:00 PM")
    deadline: Optional[str] = Field(default=None, description="Important deadline date/time")

    location: Optional[str] = Field(default=None, description="Venue or general location")
    building: Optional[str] = Field(default=None, description="Building name or block e.g. Block 34")
    room: Optional[str] = Field(default=None, description="Specific room number e.g. 34-105")
    room_range: Optional[str] = Field(default=None, description="Range of rooms e.g. 34-101 to 34-110")
    affected_rooms: List[str] = Field(default_factory=list, description="List of affected rooms")
    exempted_rooms: List[str] = Field(default_factory=list, description="List of exempted rooms")

    impact_type: Optional[str] = Field(default=None, description="Type of impact e.g. VENUE_CHANGE, CLASS_CANCELLED, TIMETABLE_SHIFT")
    action_required: bool = Field(default=False, description="Whether action is required from students")
    action_type: ActionType = Field(default=ActionType.NONE, description="Primary action type")
    registration_required: bool = Field(default=False, description="Is registration explicitly required")
    registration_link: Optional[str] = Field(default=None, description="Registration URL if provided")
    required_documents: List[str] = Field(default_factory=list, description="Required documents")

    urgency: UrgencyLevel = Field(default=UrgencyLevel.LOW, description="Urgency of notice")
    global_importance: GlobalImportance = Field(default=GlobalImportance.LOW, description="Broad university-wide importance")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score")

    attachment_present: bool = Field(default=False, description="Is an attachment referenced in source record")
    attachment_names: List[str] = Field(default_factory=list, description="List of attachment filenames")
    attachment_content_available: bool = Field(default=False, description="Is attachment content actually downloaded/parsed")
    attachment_dependent: bool = Field(default=False, description="Does crucial decision information rely on unparsed attachment")
    requires_attachment_verification: bool = Field(default=False, description="Requires verifying attached document")
    decision_completeness: DecisionCompleteness = Field(default=DecisionCompleteness.COMPLETE, description="Completeness of evidence")

class AnnouncementDetail(BaseModel):
    """Unified full announcement details for API responses."""
    announcement_id: str
    title: str
    publication_date: str
    reference_number: Optional[str] = None
    full_content: str
    attachment_present: bool = False
    attachment_names: List[str] = Field(default_factory=list)
    source: Optional[str] = "historical"
    source_url: Optional[str] = None
    is_detail_complete: bool = True
    detail_fetch_error: Optional[str] = None
    metadata: Optional[ExtractedAnnouncementMetadata] = None

