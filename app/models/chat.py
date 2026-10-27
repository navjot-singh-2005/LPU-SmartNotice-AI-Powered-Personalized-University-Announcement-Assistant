from typing import List, Optional
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    query: str
    student_id: Optional[str] = None
    history: List[ChatMessage] = Field(default_factory=list)
    top_k: int = 5

class AnnouncementSourceReference(BaseModel):
    announcement_id: str
    title: str
    reference_number: Optional[str] = None
    publication_date: str
    similarity_score: float
    attachment_present: bool
    attachment_names: List[str] = Field(default_factory=list)
    attachment_content_available: bool = False
    decision_completeness: str = "COMPLETE"
    source: Optional[str] = "historical"
    source_url: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[AnnouncementSourceReference] = Field(default_factory=list)
    attachment_warning: Optional[str] = None
    insufficient_evidence: bool = False
    processing_time_ms: int = 0

class FeedbackRequest(BaseModel):
    student_id: str
    announcement_id: str
    is_relevant: bool
    feedback_type: Optional[str] = "RELEVANCE"
    comments: Optional[str] = None

class FeedbackResponse(BaseModel):
    status: str
    message: str
