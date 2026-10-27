import re
import hashlib
from typing import List, Dict, Any, Tuple
from app.models.announcement import RawAnnouncement
from app.core.logging_config import logger

class DeduplicationService:
    """Detect exact duplicates vs legitimate revisions in university announcements."""

    def normalize_text(self, text: str) -> str:
        """Normalize text by stripping whitespace, converting to lower case, and removing non-alphanumeric chars."""
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\s]", "", text)
        return text

    def compute_content_hash(self, text: str) -> str:
        """Compute SHA-256 hash of normalized text."""
        norm = self.normalize_text(text)
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    def process_deduplication(
        self, announcements: List[RawAnnouncement]
    ) -> Tuple[List[RawAnnouncement], Dict[str, Any]]:
        """Identify exact duplicates and revisions among announcements."""
        seen_exact_hashes: Dict[str, RawAnnouncement] = {}
        seen_ref_numbers: Dict[str, List[RawAnnouncement]] = {}

        unique_announcements: List[RawAnnouncement] = []
        exact_duplicate_count = 0
        revision_count = 0

        for ann in announcements:
            norm_hash = self.compute_content_hash(ann.full_content)

            # 1. Exact Duplicate Check
            if norm_hash in seen_exact_hashes:
                exact_duplicate_count += 1
                logger.debug("Exact duplicate detected for ID %s (matches %s)", ann.announcement_id, seen_exact_hashes[norm_hash].announcement_id)
                continue

            seen_exact_hashes[norm_hash] = ann

            # 2. Revision Check (by reference number if available)
            if ann.reference_number:
                ref_key = ann.reference_number.strip().upper()
                if ref_key in seen_ref_numbers:
                    revision_count += 1
                    logger.debug("Legitimate revision/update detected for Ref #%s (ID: %s)", ref_key, ann.announcement_id)
                    seen_ref_numbers[ref_key].append(ann)
                else:
                    seen_ref_numbers[ref_key] = [ann]

            unique_announcements.append(ann)

        report = {
            "input_total": len(announcements),
            "unique_total": len(unique_announcements),
            "exact_duplicates_removed": exact_duplicate_count,
            "revisions_detected": revision_count,
        }

        logger.info(
            "Deduplication complete: %d input -> %d unique (removed %d exact duplicates, preserved %d revisions)",
            len(announcements), len(unique_announcements), exact_duplicate_count, revision_count
        )
        return unique_announcements, report
