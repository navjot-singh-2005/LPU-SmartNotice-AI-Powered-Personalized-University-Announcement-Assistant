from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from app.services.dataset_service import DatasetService
from app.services.personalization_service import PersonalizationService
from app.services.room_impact_service import RoomImpactService
from app.services.extraction_service import ExtractionService
from app.core.database import get_db_connection
from app.models.student import StudentProfile, ClassImpactResult

router = APIRouter(tags=["Personalization & Timetable Impact"])

dataset_service = DatasetService()
personalization_service = PersonalizationService()
room_impact_service = RoomImpactService()
extraction_service = ExtractionService()

def fetch_student_profile(student_id: str) -> StudentProfile:
    """Fetch student profile from SQLite DB."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM student_profiles WHERE student_id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Student profile '{student_id}' not found.")

    import json
    interests = json.loads(row["interests"]) if row["interests"] else []
    return StudentProfile(
        student_id=row["student_id"],
        name=row["name"],
        program=row["program"],
        department=row["department"],
        school=row["school"],
        year=row["year"],
        semester=row["semester"],
        section=row["section"],
        interests=interests,
        career_goal=row["career_goal"]
    )

@router.get("/students/{student_id}/feed")
@router.get("/feed/{student_id}/feed")
def get_personalized_feed(
    student_id: str,
    category: Optional[str] = None,
    applicability: Optional[str] = None,
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50)
):
    """Retrieve personalized, ranked announcement feed for a student."""
    student = fetch_student_profile(student_id)
    announcements, _ = dataset_service.load_dataset()

    # Build extracted metadata map for sample
    extracted_map = {}
    for ann in announcements[:200]: # Optimize for fast feed rendering
        cached = extraction_service.get_cached_metadata(ann.content_hash or "")
        if not cached:
            cached = extraction_service.fallback_heuristic_extraction(ann)
        extracted_map[ann.announcement_id] = cached

    feed_result = personalization_service.personalize_feed(
        student=student,
        announcements=announcements,
        extracted_map=extracted_map,
        category_filter=category,
        applicability_filter=applicability,
        min_score=min_score,
        page=page,
        page_size=page_size
    )
    return feed_result

@router.get("/students/{student_id}/affected-classes")
@router.get("/feed/{student_id}/affected-classes")
def get_affected_classes(student_id: str):
    """Evaluate student's timetable against announcements for room & time impact."""
    student = fetch_student_profile(student_id)
    announcements, _ = dataset_service.load_dataset()

    # Get student's timetable to build search terms for smart filtering
    timetable = room_impact_service.get_student_timetable(student.student_id)

    # Build search terms from timetable: rooms, blocks, course codes
    search_terms = set()
    for entry in timetable:
        room_clean = entry.room.strip().lower()
        search_terms.add(room_clean)
        # Extract block number from room (e.g. "34" from "34-105")
        import re as _re
        block_m = _re.search(r"(\d{1,2})-\d{3}", room_clean)
        if block_m:
            search_terms.add(f"block {block_m.group(1)}")
        if entry.course_code:
            search_terms.add(entry.course_code.strip().lower())
        if entry.course_name and len(entry.course_name) >= 4:
            search_terms.add(entry.course_name.strip().lower())

    # Filter candidate announcements: only those mentioning student's rooms/courses/blocks
    # Also include impact-keyword-bearing announcements (broad cancellations, holidays)
    broad_keywords = {"all rooms", "entire block", "classes suspended", "holiday", "non-teaching",
                      "power cut", "sanitization", "fumigation", "fire drill"}
    candidate_announcements = []
    for ann in announcements:
        ann_text = f"{ann.title} {ann.full_content}".lower()
        if any(term in ann_text for term in search_terms):
            candidate_announcements.append(ann)
        elif any(kw in ann_text for kw in broad_keywords):
            candidate_announcements.append(ann)

    # Build metadata map for candidates only
    metadata_map = {}
    for ann in candidate_announcements:
        cached = extraction_service.get_cached_metadata(ann.content_hash or "")
        if not cached:
            cached = extraction_service.fallback_heuristic_extraction(ann)
        metadata_map[ann.announcement_id] = cached

    impact_results = room_impact_service.evaluate_student_timetable(
        student_id=student.student_id,
        announcements=candidate_announcements,
        metadata_map=metadata_map
    )

    red_count = sum(1 for imp in impact_results if imp.indicator_color == "RED")
    amber_count = sum(1 for imp in impact_results if imp.indicator_color == "AMBER" or imp.status in ("EXEMPTED", "ATTACHMENT_DEPENDENT"))
    green_count = sum(1 for imp in impact_results if imp.indicator_color == "GREEN")
    exempted_count = sum(1 for imp in impact_results if imp.status == "EXEMPTED")

    return {
        "student_id": student.student_id,
        "student_name": student.name,
        "timetable_entries_checked": len(impact_results),
        "red_count": red_count,
        "amber_count": amber_count,
        "green_count": green_count,
        "exempted_count": exempted_count,
        "impacts": [imp.model_dump() for imp in impact_results]
    }

