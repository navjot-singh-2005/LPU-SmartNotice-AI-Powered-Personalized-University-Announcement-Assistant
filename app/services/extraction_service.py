import os
import json
import time
import sqlite3
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging_config import logger
from app.core.database import get_db_connection
from app.core.security import validate_api_key_configured
from app.models.announcement import (
    RawAnnouncement,
    ExtractedAnnouncementMetadata,
    ActionType,
    UrgencyLevel,
    GlobalImportance,
    DecisionCompleteness,
)
from app.services.pii_redaction_service import PIIRedactionService

SCHEMA_VERSION = "v1.0"

class ExtractionService:
    """Uses Gemini API to extract structured announcement metadata with caching and error handling."""

    def __init__(self):
        self.pii_service = PIIRedactionService()

    def get_client(self) -> genai.Client:
        key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        if not key or key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not configured in .env file.")
        return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=12000))

    def get_cached_metadata(self, content_hash: str) -> Optional[ExtractedAnnouncementMetadata]:
        """Fetch cached extraction metadata from SQLite if present."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT raw_json FROM extracted_metadata WHERE content_hash = ? AND schema_version = ?",
            (content_hash, SCHEMA_VERSION)
        )
        row = cursor.fetchone()
        conn.close()

        if row and row["raw_json"]:
            try:
                data = json.loads(row["raw_json"])
                return ExtractedAnnouncementMetadata(**data)
            except Exception as e:
                logger.warning("Failed to deserialize cached metadata for hash %s: %s", content_hash, e)
        return None

    def save_cached_metadata(
        self,
        announcement_id: str,
        content_hash: str,
        metadata: ExtractedAnnouncementMetadata,
        processing_time_ms: int,
        status: str = "SUCCESS"
    ) -> None:
        """Save extracted metadata into SQLite database."""
        conn = get_db_connection()
        cursor = conn.cursor()

        raw_json = metadata.model_dump_json()

        cursor.execute("""
        INSERT INTO extracted_metadata (
            announcement_id, content_hash, category, sub_category, summary, topics,
            target_year, target_semester, target_program, target_department, target_school, target_section,
            eligibility, exclusions, event_date, start_time, end_time, deadline,
            location, building, room, room_range, affected_rooms, exempted_rooms,
            impact_type, action_required, action_type, registration_required, registration_link, required_documents,
            urgency, global_importance, confidence, attachment_present, attachment_names,
            attachment_content_available, attachment_dependent, requires_attachment_verification,
            decision_completeness, model_name, schema_version, processing_time_ms, status, raw_json
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?, ?
        ) ON CONFLICT(announcement_id) DO UPDATE SET
            category=excluded.category,
            summary=excluded.summary,
            confidence=excluded.confidence,
            decision_completeness=excluded.decision_completeness,
            raw_json=excluded.raw_json,
            updated_at=CURRENT_TIMESTAMP
        """, (
            announcement_id, content_hash, metadata.category, metadata.sub_category, metadata.summary, json.dumps(metadata.topics),
            json.dumps(metadata.target_year), json.dumps(metadata.target_semester), metadata.target_program, metadata.target_department, metadata.target_school, metadata.target_section,
            metadata.eligibility, metadata.exclusions, metadata.event_date, metadata.start_time, metadata.end_time, metadata.deadline,
            metadata.location, metadata.building, metadata.room, metadata.room_range, json.dumps(metadata.affected_rooms), json.dumps(metadata.exempted_rooms),
            metadata.impact_type, metadata.action_required, metadata.action_type.value, metadata.registration_required, metadata.registration_link, json.dumps(metadata.required_documents),
            metadata.urgency.value, metadata.global_importance.value, metadata.confidence, metadata.attachment_present, json.dumps(metadata.attachment_names),
            metadata.attachment_content_available, metadata.attachment_dependent, metadata.requires_attachment_verification,
            metadata.decision_completeness.value, settings.GEMINI_GENERATION_MODEL, SCHEMA_VERSION, processing_time_ms, status, raw_json
        ))
        conn.commit()
        conn.close()

    def extract_metadata(
        self,
        announcement: RawAnnouncement,
        use_cache: bool = True
    ) -> ExtractedAnnouncementMetadata:
        """Extract structured metadata from an announcement using Gemini API with caching."""
        content_hash = announcement.content_hash or "no_hash"

        if use_cache:
            cached = self.get_cached_metadata(content_hash)
            if cached:
                logger.debug("Cache hit for announcement ID %s", announcement.announcement_id)
                # Keep ID matching current announcement
                cached.announcement_id = announcement.announcement_id
                return cached

        if not validate_api_key_configured():
            # Return heuristic baseline fallback if API key is unconfigured
            return self.fallback_heuristic_extraction(announcement)

        redacted_content, _ = self.pii_service.redact_pii(announcement.full_content)

        prompt = f"""
Analyze the following Lovely Professional University (LPU) announcement and extract structured metadata adhering strictly to the JSON schema.

CRITICAL RULES:
1. Extract FACTS explicitly stated in the text. Do NOT invent missing details.
2. If a field (e.g. deadline, room, program) is not mentioned, return null or an empty list.
3. Keep category from one of: ACADEMIC, PLACEMENT, EVENT, EXAMINATION, ADMINISTRATIVE, HOSTEL, GENERAL, SPORTS, RESEARCH.
4. Keep action_type from: REGISTRATION, SUBMIT_DOCUMENT, ATTEND_EVENT, CHANGE_ROOM, NO_CLASS, EXAM, PAYMENT, APPLICATION, OTHER, NONE, UNKNOWN.
5. If an attachment (PDF/doc) is referenced in the text or metadata, mark attachment_present=true. Notice that actual attachment files are NOT provided here, so attachment_content_available must be false.
6. If the announcement states key info is inside the attached file (e.g., "see attached list for room seating / eligible students"), set attachment_dependent=true and decision_completeness="ATTACHMENT_MISSING".

Announcement Details:
- Title: {announcement.title}
- Date: {announcement.publication_date}
- Ref Number: {announcement.reference_number or 'N/A'}
- Has Attachment: {announcement.attachment_present}
- Attachment Names: {', '.join(announcement.attachment_names) if announcement.attachment_names else 'None'}
- Text Content:
{redacted_content}
"""

        start_time = time.time()

        try:
            client = self.get_client()
            response = client.models.generate_content(
                model=settings.GEMINI_GENERATION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedAnnouncementMetadata,
                    temperature=0.1,
                )
            )

            processing_ms = int((time.time() - start_time) * 1000)

            if not response.text:
                raise ValueError("Empty response text from Gemini API")

            data = json.loads(response.text)
            data["announcement_id"] = announcement.announcement_id

            # Enforce attachment completeness rules explicitly
            data["attachment_present"] = announcement.attachment_present or bool(data.get("attachment_present"))
            data["attachment_names"] = announcement.attachment_names or data.get("attachment_names", [])
            data["attachment_content_available"] = False

            if data["attachment_present"] and data.get("attachment_dependent"):
                data["decision_completeness"] = DecisionCompleteness.ATTACHMENT_MISSING.value
                data["requires_attachment_verification"] = True
            elif not data.get("decision_completeness"):
                data["decision_completeness"] = DecisionCompleteness.COMPLETE.value

            metadata = ExtractedAnnouncementMetadata(**data)

            # Determine review status if low confidence
            status = "SUCCESS" if metadata.confidence >= 0.6 else "REVIEW"

            self.save_cached_metadata(
                announcement.announcement_id, content_hash, metadata, processing_ms, status=status
            )
            return metadata

        except Exception as e:
            logger.error("Gemini extraction failed for ID %s: %s. Using heuristic fallback.", announcement.announcement_id, e)
            return self.fallback_heuristic_extraction(announcement)

    def fallback_heuristic_extraction(self, ann: RawAnnouncement) -> ExtractedAnnouncementMetadata:
        """Heuristic rule-based fallback extraction when LLM API is unavailable or fails."""
        text_lower = f"{ann.title} {ann.full_content}".lower()

        category = "GENERAL"
        if "exam" in text_lower or "seating" in text_lower:
            category = "EXAMINATION"
        elif "placement" in text_lower or "drive" in text_lower or "job" in text_lower:
            category = "PLACEMENT"
        elif "class" in text_lower or "lecture" in text_lower or "course" in text_lower:
            category = "ACADEMIC"
        elif "event" in text_lower or "fest" in text_lower or "workshop" in text_lower:
            category = "EVENT"

        urgency = UrgencyLevel.LOW
        if "urgent" in text_lower or "immediately" in text_lower or "notice!" in text_lower:
            urgency = UrgencyLevel.HIGH

        completeness = DecisionCompleteness.COMPLETE
        attachment_dep = False
        if ann.attachment_present and ("attached" in text_lower or "refer attach" in text_lower or "enclosed" in text_lower):
            completeness = DecisionCompleteness.ATTACHMENT_MISSING
            attachment_dep = True

        metadata = ExtractedAnnouncementMetadata(
            announcement_id=ann.announcement_id,
            category=category,
            summary=ann.title[:150],
            topics=[category.lower()],
            action_required=("register" in text_lower or "submit" in text_lower or "mandatory" in text_lower),
            urgency=urgency,
            global_importance=GlobalImportance.MEDIUM if urgency in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL) else GlobalImportance.LOW,
            confidence=0.7,
            attachment_present=ann.attachment_present,
            attachment_names=ann.attachment_names,
            attachment_content_available=False,
            attachment_dependent=attachment_dep,
            requires_attachment_verification=ann.attachment_present,
            decision_completeness=completeness
        )
        return metadata
