import json
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from app.models.student import StudentProfile
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata
from app.core.logging_config import logger

# Configurable Scoring Weights
WEIGHT_YEAR = 0.25
WEIGHT_DEPT = 0.20
WEIGHT_INTEREST = 0.25
WEIGHT_URGENCY = 0.15
WEIGHT_GLOBAL = 0.15

class PersonalizationService:
    """Ranks and personalizes university announcements for an individual student."""

    def calculate_interest_similarity(self, student_interests: List[str], announcement_text: str, topics: List[str]) -> float:
        """Calculate word-overlap similarity between student interest keywords and announcement content."""
        if not student_interests:
            return 0.5

        text_lower = (announcement_text + " " + " ".join(topics)).lower()
        matched_count = 0

        for interest in student_interests:
            words = interest.lower().split()
            if any(w in text_lower for w in words if len(w) > 2):
                matched_count += 1

        score = matched_count / len(student_interests)
        return min(1.0, score * 1.5) # Scale slightly

    def score_announcement(
        self,
        student: StudentProfile,
        announcement: RawAnnouncement,
        metadata: Optional[ExtractedAnnouncementMetadata] = None
    ) -> Dict[str, Any]:
        """Compute personal relevance score (0.0 to 1.0) and detailed score breakdowns for a student."""

        # 1. Target Year Match
        year_score = 1.0
        if metadata and metadata.target_year:
            if student.year in metadata.target_year:
                year_score = 1.0
            else:
                year_score = 0.1 # Penalty for explicit target year mismatch

        # 2. Program / Dept / School Match
        dept_score = 1.0
        if metadata:
            matches = []
            if metadata.target_program:
                matches.append(student.program.lower() in metadata.target_program.lower() or metadata.target_program.lower() in student.program.lower())
            if metadata.target_department:
                matches.append(student.department.lower() in metadata.target_department.lower() or metadata.target_department.lower() in student.department.lower())
            if metadata.target_school:
                matches.append(student.school.lower() in metadata.target_school.lower() or metadata.target_school.lower() in student.school.lower())

            if matches:
                dept_score = 1.0 if any(matches) else 0.2

        # 3. Interest Similarity
        topics = metadata.topics if metadata else []
        interest_score = self.calculate_interest_similarity(
            student.interests,
            f"{announcement.title} {announcement.full_content}",
            topics
        )

        # 4. Urgency & Global Importance
        urgency_val = metadata.urgency.value if metadata and hasattr(metadata.urgency, "value") else (str(metadata.urgency) if metadata and metadata.urgency else "LOW")
        global_val = metadata.global_importance.value if metadata and hasattr(metadata.global_importance, "value") else (str(metadata.global_importance) if metadata and metadata.global_importance else "LOW")

        urgency_score = 1.0 if urgency_val.upper() in ("CRITICAL", "HIGH") else (0.6 if urgency_val.upper() == "MEDIUM" else 0.3)
        global_score = 1.0 if global_val.upper() == "HIGH" else (0.6 if global_val.upper() == "MEDIUM" else 0.3)

        # 5. Check Explicit Group Exclusions
        is_excluded = False
        if metadata and metadata.exclusions:
            ex_lower = metadata.exclusions.lower()
            if (
                f"year {student.year}" in ex_lower
                or f"{student.year}st year" in ex_lower
                or f"{student.year}nd year" in ex_lower
                or f"{student.year}rd year" in ex_lower
                or f"{student.year}th year" in ex_lower
                or student.program.lower() in ex_lower
                or student.department.lower() in ex_lower
            ):
                is_excluded = True
                year_score = min(year_score, 0.05)
                dept_score = min(dept_score, 0.05)

        # 6. Base Personal Priority Formula
        raw_score = (
            (WEIGHT_YEAR * year_score) +
            (WEIGHT_DEPT * dept_score) +
            (WEIGHT_INTEREST * interest_score) +
            (WEIGHT_URGENCY * urgency_score) +
            (WEIGHT_GLOBAL * global_score)
        )
        if is_excluded:
            raw_score = min(raw_score, 0.15)

        # 7. Global Safety / Mandatory Notice Override Rule
        is_override = False
        if not is_excluded and (global_val.upper() == "HIGH" or urgency_val.upper() == "CRITICAL"):
            is_override = True
            raw_score = max(raw_score, 0.85) # Ensure urgent/global notices are not suppressed

        # 8. Determine Applicability Tier
        # Categories: DEFINITELY_APPLICABLE, POTENTIALLY_RELEVANT, GENERAL_NOTICE, NOT_APPLICABLE, UNCERTAIN
        is_attachment_missing = False
        if metadata and hasattr(metadata, "decision_completeness"):
            comp_val = getattr(metadata.decision_completeness, "value", str(metadata.decision_completeness))
            if comp_val == "ATTACHMENT_MISSING":
                is_attachment_missing = True

        if is_excluded or year_score <= 0.1 or dept_score <= 0.2:
            applicability_tier = "NOT_APPLICABLE"
        elif is_attachment_missing:
            applicability_tier = "UNCERTAIN"
        elif metadata and (
            (metadata.target_year and student.year in metadata.target_year)
            or (metadata.target_program and (student.program.lower() in metadata.target_program.lower() or metadata.target_program.lower() in student.program.lower()))
            or (metadata.target_department and (student.department.lower() in metadata.target_department.lower() or metadata.target_department.lower() in student.department.lower()))
        ):
            applicability_tier = "DEFINITELY_APPLICABLE"
        elif not metadata or (not metadata.target_year and not metadata.target_program and not metadata.target_department) or global_val.upper() == "HIGH":
            if interest_score > 0.4:
                applicability_tier = "POTENTIALLY_RELEVANT"
            else:
                applicability_tier = "GENERAL_NOTICE"
        elif interest_score > 0.35 or raw_score >= 0.5:
            applicability_tier = "POTENTIALLY_RELEVANT"
        else:
            applicability_tier = "GENERAL_NOTICE"

        # 9. Generate Explanation
        reasons = []
        if is_excluded:
            reasons.append(f"Explicit exclusion criteria applies to your profile ({metadata.exclusions})")
        if year_score == 1.0 and metadata and metadata.target_year:
            reasons.append(f"Targeted for Year {student.year} students")
        if dept_score == 1.0 and metadata and (metadata.target_department or metadata.target_program):
            reasons.append(f"Relevant to {student.program}")
        if interest_score > 0.4:
            reasons.append(f"Matches your interests ({', '.join(student.interests[:2])})")
        if is_override:
            reasons.append("University-wide urgent / mandatory notice override")
        if not reasons:
            reasons.append("General university announcement")

        explanation = " • ".join(reasons)

        return {
            "personal_priority_score": round(raw_score, 4),
            "year_match_score": year_score,
            "dept_match_score": dept_score,
            "interest_match_score": round(interest_score, 4),
            "urgency_score": urgency_score,
            "global_score": global_score,
            "is_override": is_override,
            "applicability_tier": applicability_tier,
            "explanation": explanation
        }

    def parse_date_to_iso(self, date_str: str) -> str:
        """Parse various date formats into standardized sortable ISO format YYYY-MM-DD."""
        if not date_str:
            return "1970-01-01"
        s = str(date_str).strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            return s[:10]
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            month, day, year = m.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        m2 = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})", s)
        if m2:
            day, month, year = m2.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        for fmt in ("%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%b %d, %Y"):
            try:
                return datetime.strptime(s[:11], fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return s

    def extract_deadline_info(
        self,
        announcement: RawAnnouncement,
        metadata: Optional[ExtractedAnnouncementMetadata] = None,
        reference_date_str: str = "2026-10-26"
    ) -> Dict[str, Any]:
        """Extract deadline date, evaluate if expired, and compute days remaining."""
        raw_deadline = None
        if metadata:
            raw_deadline = getattr(metadata, "deadline", None) or getattr(metadata, "deadline_date", None) or getattr(metadata, "registration_deadline", None)

        if not raw_deadline:
            # Check announcement text for explicit deadline phrases
            content = f"{announcement.title} {announcement.full_content}"
            match = re.search(r"(?:deadline|last date|register by|apply before|due date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})", content, re.IGNORECASE)
            if match:
                raw_deadline = match.group(1)

        if not raw_deadline:
            return {
                "deadline_date": None,
                "is_expired": False,
                "days_remaining": None
            }

        iso_deadline = self.parse_date_to_iso(raw_deadline)
        if iso_deadline == "1970-01-01":
            return {
                "deadline_date": None,
                "is_expired": False,
                "days_remaining": None
            }

        try:
            deadline_dt = datetime.strptime(iso_deadline, "%Y-%m-%d").date()
            ref_dt = datetime.strptime(reference_date_str, "%Y-%m-%d").date()
            diff_days = (deadline_dt - ref_dt).days
            return {
                "deadline_date": iso_deadline,
                "is_expired": diff_days < 0,
                "days_remaining": diff_days
            }
        except Exception:
            return {
                "deadline_date": iso_deadline,
                "is_expired": False,
                "days_remaining": None
            }

    def personalize_feed(
        self,
        student: StudentProfile,
        announcements: List[RawAnnouncement],
        extracted_map: Optional[Dict[str, ExtractedAnnouncementMetadata]] = None,
        category_filter: Optional[str] = None,
        applicability_filter: Optional[str] = None,
        min_score: float = 0.0,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Generate a personalized, ranked announcement feed for a student."""
        extracted_map = extracted_map or {}
        scored_items = []
        tier_counts = {
            "DEFINITELY_APPLICABLE": 0,
            "POTENTIALLY_RELEVANT": 0,
            "GENERAL_NOTICE": 0,
            "NOT_APPLICABLE": 0,
            "UNCERTAIN": 0,
            "UPCOMING_DEADLINES": 0,
            "URGENT": 0
        }

        for ann in announcements:
            meta = extracted_map.get(ann.announcement_id)
            is_live = bool(ann.source and ann.source.startswith("ums"))

            if category_filter:
                cf = category_filter.strip().upper()
                if cf in ("UMS_LIVE", "LIVE"):
                    if not is_live:
                        continue
                elif meta and meta.category.upper() != cf:
                    continue

            scores = self.score_announcement(student, ann, meta)
            base_score = scores["personal_priority_score"]
            tier = scores.get("applicability_tier", "GENERAL_NOTICE")

            # Track tier counts
            if tier in tier_counts:
                tier_counts[tier] += 1

            urgency_level = (meta.urgency.value if meta and hasattr(meta.urgency, "value") else (str(meta.urgency) if meta and meta.urgency else "LOW")).upper()
            if urgency_level in ("HIGH", "CRITICAL"):
                tier_counts["URGENT"] += 1

            deadline_info = self.extract_deadline_info(ann, meta)
            if deadline_info["deadline_date"] and not deadline_info["is_expired"]:
                tier_counts["UPCOMING_DEADLINES"] += 1

            # Filter by Applicability Tier if specified
            if applicability_filter:
                af = applicability_filter.strip().upper()
                if af in ("APPLICABLE", "DEFINITELY_APPLICABLE"):
                    if tier != "DEFINITELY_APPLICABLE":
                        continue
                elif af in ("RELEVANT", "POTENTIALLY_RELEVANT"):
                    if tier not in ("DEFINITELY_APPLICABLE", "POTENTIALLY_RELEVANT"):
                        continue
                elif af == "GENERAL":
                    if tier != "GENERAL_NOTICE":
                        continue
                elif af == "URGENT":
                    if urgency_level not in ("HIGH", "CRITICAL"):
                        continue
                elif af in ("DEADLINES", "UPCOMING_DEADLINES"):
                    if not deadline_info["deadline_date"] or deadline_info["is_expired"]:
                        continue
                elif af == "UNCERTAIN":
                    if tier != "UNCERTAIN":
                        continue
                elif af == "NOT_APPLICABLE":
                    if tier != "NOT_APPLICABLE":
                        continue

            if base_score < min_score:
                continue

            # Prioritize real-time live notices with a recency prominence boost
            effective_score = min(1.0, round(base_score + 0.20, 4)) if is_live else base_score
            iso_date = self.parse_date_to_iso(ann.publication_date)

            explanation = scores["explanation"]
            if is_live:
                explanation = "⚡ Real-Time Official Notice • " + explanation

            scored_items.append({
                "announcement_id": ann.announcement_id,
                "title": ann.title,
                "publication_date": ann.publication_date,
                "iso_date": iso_date,
                "reference_number": ann.reference_number,
                "full_content": ann.full_content,
                "attachment_present": ann.attachment_present,
                "attachment_names": ann.attachment_names,
                "attachment_content_available": False,
                "decision_completeness": meta.decision_completeness.value if meta else ("ATTACHMENT_MISSING" if ann.attachment_present else "COMPLETE"),
                "category": meta.category if meta else "GENERAL",
                "urgency": urgency_level,
                "personal_priority_score": effective_score,
                "applicability_tier": tier,
                "deadline_date": deadline_info["deadline_date"],
                "is_deadline_expired": deadline_info["is_expired"],
                "days_remaining": deadline_info["days_remaining"],
                "explanation": explanation,
                "score_breakdown": scores,
                "source": ann.source or "historical",
                "source_url": ann.source_url,
                "is_live": is_live,
                "is_detail_complete": getattr(ann, "is_detail_complete", True),
                "detail_fetch_error": getattr(ann, "detail_fetch_error", None),
            })

        # Sort primarily by:
        # 1. Live notice status (real-time live notices first)
        # 2. For live notices: ISO publication date descending (newest announcements appear first)
        # 3. Personal priority score descending
        # 4. ISO publication date descending (for historical notices)
        scored_items.sort(
            key=lambda x: (
                1 if x.get("is_live") else 0,
                x.get("iso_date", "") if x.get("is_live") else "",
                x["personal_priority_score"],
                x.get("iso_date", "")
            ),
            reverse=True
        )

        total_items = len(scored_items)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = scored_items[start_idx:end_idx]

        return {
            "student_id": student.student_id,
            "student_name": student.name,
            "program": student.program,
            "year": student.year,
            "total_items": total_items,
            "total": total_items,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_items + page_size - 1) // page_size if total_items > 0 else 1,
            "tier_counts": tier_counts,
            "feed": paginated_items
        }
