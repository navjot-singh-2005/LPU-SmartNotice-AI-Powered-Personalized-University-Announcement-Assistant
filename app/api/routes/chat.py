from fastapi import APIRouter, HTTPException
from app.core.logging_config import logger
from app.models.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/chat", tags=["Grounded RAG Chatbot"])

chat_service = ChatService()
dataset_service = DatasetService()

@router.post("", response_model=ChatResponse)
def ask_chatbot(request: ChatRequest):
    """Ask a question to the grounded AI announcement assistant."""
    query = request.query.strip() if request.query else ""
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if len(query) > 2000:
        request.query = query[:2000]

    try:
        announcements, _ = dataset_service.load_dataset()
        response = chat_service.answer_question(request, raw_announcements=announcements)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chat endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to process chat query: {str(exc)}")
