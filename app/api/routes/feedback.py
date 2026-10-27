from fastapi import APIRouter
from app.models.chat import FeedbackRequest, FeedbackResponse
from app.core.database import get_db_connection

router = APIRouter(prefix="/feedback", tags=["User Feedback"])

@router.post("", response_model=FeedbackResponse)
def submit_feedback(feedback: FeedbackRequest):
    """Submit relevance or accuracy feedback for an announcement recommendation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO student_feedback (student_id, announcement_id, is_relevant, feedback_type, comments)
        VALUES (?, ?, ?, ?, ?)
    """, (
        feedback.student_id,
        feedback.announcement_id,
        feedback.is_relevant,
        feedback.feedback_type or "RELEVANCE",
        feedback.comments
    ))
    conn.commit()
    conn.close()

    return FeedbackResponse(
        status="success",
        message="Thank you for your feedback! Your input helps improve LPU SmartNotice recommendation accuracy."
    )
