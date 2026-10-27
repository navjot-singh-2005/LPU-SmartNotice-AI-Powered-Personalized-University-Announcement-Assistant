import os
import re
import time
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging_config import logger
from app.core.security import validate_api_key_configured
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    AnnouncementSourceReference,
    ChatMessage
)
from app.services.retrieval_service import RetrievalService
from app.models.announcement import RawAnnouncement


def is_conversational_greeting(query: str) -> bool:
    """Check if query is a simple greeting or chitchat without specific announcement requests."""
    q = query.strip().lower()
    topic_keywords = {
        "exam", "examination", "schedule", "placement", "drive", "interview",
        "company", "room", "class", "block", "timetable", "date", "fee", "fees",
        "scholarship", "hostel", "holiday", "attendance", "result", "grade",
        "cgpa", "eligibility", "convocation", "registration", "deadline", "event",
        "who", "what", "where", "when", "why", "how", "course"
    }
    words = set(re.findall(r"\w+", q))
    # If any specific topic is mentioned (except question words alone), it's not just a greeting
    if words.intersection(topic_keywords - {"who", "what", "where", "when", "why", "how"}):
        return False

    greeting_patterns = [
        r"^(hi|hello|hey|heya|howdy|greetings|hola)\b",
        r"^good\s+(morning|afternoon|evening|day)\b",
        r"^who\s+are\s+you\b",
        r"^what\s+(is\s+your\s+name|can\s+you\s+do)\b",
        r"^help(\s+me)?\b",
    ]
    for pattern in greeting_patterns:
        if re.search(pattern, q):
            return True
    return False


class ChatService:
    """Grounded RAG Chatbot Service with attachment-awareness, history, and citation verification."""

    def __init__(self):
        self.retrieval_service = RetrievalService()

    def get_client(self) -> genai.Client:
        key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        if not key or key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not configured in .env file.")
        return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=25000))

    def answer_question(
        self,
        request: ChatRequest,
        raw_announcements: Optional[List[RawAnnouncement]] = None
    ) -> ChatResponse:
        """Process natural language question using grounded RAG pipeline."""
        start_time = time.time()
        query = request.query.strip()

        # Check for polite greeting / chitchat first
        if is_conversational_greeting(query):
            greeting_answer = (
                "Hello! I am your LPU SmartNotice AI Assistant. "
                "I can answer questions grounded in official Lovely Professional University announcements, "
                "such as examination schedules, placement drives, scholarship notices, room changes, "
                "and important deadlines. How can I assist you today?"
            )
            return ChatResponse(
                answer=greeting_answer,
                sources=[],
                attachment_warning=None,
                insufficient_evidence=False,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

        # 1. Retrieve Announcement Evidence safely
        try:
            candidates = self.retrieval_service.search(
                query=query,
                top_k=request.top_k,
                raw_announcements=raw_announcements
            )
        except Exception as ret_err:
            logger.error("Announcement retrieval failed: %s", ret_err)
            candidates = []

        sources: List[AnnouncementSourceReference] = []
        attachment_warnings: List[str] = []
        evidence_text_blocks: List[str] = []

        if not candidates:
            answer = "I could not find any relevant university announcements in the database to answer your question."
            return ChatResponse(
                answer=answer,
                sources=[],
                attachment_warning=None,
                insufficient_evidence=True,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

        for cand in candidates:
            raw_att = cand.get("attachment_names", [])
            if isinstance(raw_att, list):
                att_names = [str(x) for x in raw_att if str(x).strip()]
            else:
                att_names = [x.strip() for x in str(raw_att).split(",") if x.strip()]

            sources.append(
                AnnouncementSourceReference(
                    announcement_id=cand["announcement_id"],
                    title=cand["title"],
                    reference_number=cand.get("reference_number"),
                    publication_date=cand["publication_date"],
                    similarity_score=cand.get("rrf_score", 0.0),
                    attachment_present=cand["attachment_present"],
                    attachment_names=att_names,
                    attachment_content_available=False,
                    decision_completeness=cand["decision_completeness"],
                    source=cand.get("source", "historical"),
                    source_url=cand.get("source_url")
                )
            )

            if cand["attachment_present"]:
                names_str = ", ".join(att_names) if att_names else "attached file"
                attachment_warnings.append(
                    f"Notice '{cand['title']}' references attachment ({names_str}), but attachment file contents are unavailable."
                )

            evidence_text_blocks.append(
                f"[Source ID: {cand['announcement_id']}]\n"
                f"Title: {cand['title']}\n"
                f"Date: {cand['publication_date']}\n"
                f"Reference #: {cand.get('reference_number') or 'N/A'}\n"
                f"Has Attachment: {cand['attachment_present']} ({', '.join(att_names) if att_names else 'None'})\n"
                f"Content: {cand['document']}\n"
            )

        combined_evidence = "\n---\n".join(evidence_text_blocks)

        # Build Multi-Turn History Context
        history_context = ""
        if request.history:
            recent_turns = request.history[-6:]
            formatted_turns = []
            for msg in recent_turns:
                role_label = "Student" if msg.role == "user" else "Assistant"
                turn_content = msg.content.strip()
                if len(turn_content) > 300:
                    turn_content = turn_content[:300] + "..."
                formatted_turns.append(f"{role_label}: {turn_content}")
            history_context = "Previous Conversation Context:\n" + "\n".join(formatted_turns) + "\n\n"

        student_context = f"\nActive Student Context: Student ID {request.student_id}\n" if request.student_id else ""

        # 2. Build Grounded Prompt for Gemini API
        prompt = f"""You are LPU SmartNotice AI Assistant. Your task is to answer the student's question strictly and faithfully based ONLY on the retrieved university announcement evidence provided below.

STRICT GROUNDING RULES:
1. Base your answer ONLY on the provided retrieved announcement evidence.
2. Every LPU-specific statement or fact in your answer MUST cite its Source ID in brackets, e.g. [Source ID: ANN-...].
3. If the retrieved evidence does NOT contain sufficient information to answer the question, state clearly: "Based on available announcements, I do not have enough information to answer." Do NOT invent policies, dates, room numbers, or guidelines.
4. ATTACHMENT NOTICE: If an announcement mentions an attachment (e.g. PDF/seating plan), explicitly inform the student that the attachment is referenced but its internal contents are unavailable in the system.
5. If the student asks a follow-up question, use the conversation history to understand context, but still ground all factual claims in the retrieved announcement evidence.
{student_context}
{history_context}Retrieved Announcement Evidence:
{combined_evidence}

Student Question:
{query}
"""

        if not validate_api_key_configured():
            # Return grounded fallback answer if API key missing
            fallback_text = f"Based on retrieved evidence ({len(sources)} sources):\n"
            for src in sources:
                fallback_text += f"• [{src.announcement_id}] {src.title} ({src.publication_date})\n"
            fallback_text += "\n(Note: Full AI generation disabled because GEMINI_API_KEY is not configured.)"
            return ChatResponse(
                answer=fallback_text,
                sources=sources,
                attachment_warning="; ".join(attachment_warnings) if attachment_warnings else None,
                insufficient_evidence=False,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

        try:
            client = self.get_client()
            response = client.models.generate_content(
                model=settings.GEMINI_GENERATION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                )
            )
            answer_text = response.text or "No response generated."
            processing_ms = int((time.time() - start_time) * 1000)

            return ChatResponse(
                answer=answer_text,
                sources=sources,
                attachment_warning="; ".join(attachment_warnings) if attachment_warnings else None,
                insufficient_evidence=False,
                processing_time_ms=processing_ms
            )

        except Exception as e:
            logger.error("Chat generation failed: %s", e)
            error_str = str(e)
            if "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                user_msg = "The AI service is currently experiencing high demand (quota limit reached). Here are the relevant announcements found in the database:"
            elif "timed out" in error_str.lower() or "timeout" in error_str.lower():
                user_msg = "The AI response timed out. Here are the relevant announcements retrieved for your query:"
            else:
                user_msg = "I encountered an error generating the natural language response. Here are the relevant announcements retrieved for your query:"

            fallback_text = f"{user_msg}\n\n"
            for src in sources:
                fallback_text += f"• [{src.announcement_id}] {src.title} ({src.publication_date})\n"

            return ChatResponse(
                answer=fallback_text,
                sources=sources,
                attachment_warning="; ".join(attachment_warnings) if attachment_warnings else None,
                insufficient_evidence=False,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
