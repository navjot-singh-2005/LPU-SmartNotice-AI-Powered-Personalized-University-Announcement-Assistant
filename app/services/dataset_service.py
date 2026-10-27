import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.logging_config import logger
from app.models.announcement import RawAnnouncement

class DatasetService:
    """Service to load, validate, report on, and retrieve source announcements."""

    _cached_records: Optional[List[RawAnnouncement]] = None
    _cached_report: Optional[Dict[str, Any]] = None
    _cached_path: Optional[str] = None

    def __init__(self, dataset_path: Optional[str] = None):
        self.dataset_path = Path(dataset_path or settings.DATASET_PATH)

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the in-memory parsed dataset cache."""
        cls._cached_records = None
        cls._cached_report = None
        cls._cached_path = None

    def generate_deterministic_id(self, record: Dict[str, Any], index: int) -> str:
        """Generate a stable deterministic announcement ID based on reference number, date, title, and content prefix."""
        ref = str(record.get("reference_number") or "").strip()
        pub_date = str(record.get("publication_date") or "").strip()
        title = str(record.get("title") or "").strip()
        content = str(record.get("full_content") or "").strip()[:50]
        raw_key = f"{ref}|{pub_date}|{title}|{content}|idx_{index}"
        hash_str = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:12]
        return f"ANN-{pub_date[:10].replace('-', '')}-{hash_str}"

    def load_dataset(self, include_live: bool = True, force_reload: bool = False) -> Tuple[List[RawAnnouncement], Dict[str, Any]]:
        """Load and validate the raw JSON dataset with in-memory caching."""
        if not self.dataset_path.exists():
            logger.warning("Dataset file not found at %s. Returning synthetic test dataset.", self.dataset_path)
            synthetic, report = self.get_synthetic_dataset()
            return synthetic, report

        # 1. Check in-memory cache for historical dataset
        if (
            not force_reload
            and DatasetService._cached_records is not None
            and DatasetService._cached_path == str(self.dataset_path)
        ):
            valid_records = list(DatasetService._cached_records)
            report = dict(DatasetService._cached_report or {})
        else:
            try:
                with self.dataset_path.open("r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception as e:
                logger.error("Failed to parse dataset JSON: %s", e)
                raise ValueError(f"Invalid JSON file in dataset: {e}")

            if not isinstance(raw_data, list):
                raise ValueError("Expected JSON file to contain a list of announcement records.")

            valid_records = []
            malformed_count = 0
            missing_titles = 0
            missing_contents = 0
            with_attachments = 0
            dates: List[str] = []

            for idx, item in enumerate(raw_data):
                if not isinstance(item, dict):
                    malformed_count += 1
                    continue

                title = str(item.get("title") or "").strip()
                content = str(item.get("full_content") or "").strip()
                pub_date = str(item.get("publication_date") or "").strip()
                ref_num = item.get("reference_number")
                if ref_num is not None:
                    ref_num = str(ref_num).strip()

                if not title:
                    missing_titles += 1
                if not content:
                    missing_contents += 1

                attachment_present = bool(item.get("attachment_present", False))
                attachment_names = item.get("attachment_names") or []
                if not isinstance(attachment_names, list):
                    attachment_names = [str(attachment_names)]
                else:
                    attachment_names = [str(x) for x in attachment_names]

                if attachment_present:
                    with_attachments += 1

                if pub_date:
                    dates.append(pub_date)

                ann_id = self.generate_deterministic_id(item, idx)
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                ann = RawAnnouncement(
                    announcement_id=ann_id,
                    title=title or "Untitled Announcement",
                    publication_date=pub_date or "Unknown Date",
                    reference_number=ref_num,
                    full_content=content,
                    attachment_present=attachment_present,
                    attachment_names=attachment_names,
                    content_hash=content_hash
                )
                valid_records.append(ann)

            report = {
                "total_records": len(raw_data),
                "valid_records": len(valid_records),
                "malformed_records": malformed_count,
                "missing_titles": missing_titles,
                "missing_contents": missing_contents,
                "with_attachments": with_attachments,
                "without_attachments": len(valid_records) - with_attachments,
                "min_date": min(dates) if dates else "N/A",
                "max_date": max(dates) if dates else "N/A",
                "dataset_path": str(self.dataset_path)
            }

            # Cache the parsed historical dataset
            DatasetService._cached_records = list(valid_records)
            DatasetService._cached_report = dict(report)
            DatasetService._cached_path = str(self.dataset_path)



        if include_live:
            try:
                from app.services.ums_sync_service import UMSSyncService
                live_records = UMSSyncService().get_synced_announcements()
                if live_records:
                    valid_records = live_records + valid_records
                    report["total_records"] += len(live_records)
                    report["valid_records"] += len(live_records)
                    report["live_ums_records"] = len(live_records)
            except Exception as e:
                logger.debug("Could not load live announcements from SQLite: %s", e)

        logger.info("Loaded dataset successfully: %d valid records, %d with attachments.", len(valid_records), report.get("with_attachments", 0))
        return valid_records, report

    def get_synthetic_dataset(self) -> Tuple[List[RawAnnouncement], Dict[str, Any]]:
        """Fallback synthetic dataset if raw JSON is absent."""
        records = [
            RawAnnouncement(
                announcement_id="ANN-SYNTH-001",
                title="Mid-Term Examination Schedule & Room Allocations - Autumn 2026",
                publication_date="2026-10-01",
                reference_number="LPU/EXAM/2026/101",
                full_content="All 3rd Year B.Tech CSE students are hereby informed that Mid-Term examinations will start on 15th October 2026. Exam rooms allocated: Block 34, Rooms 34-101 to 34-110. Regular classes in Block 34 will remain suspended during exam hours (09:00 AM - 01:00 PM). Please refer to the attached seating plan PDF for roll number wise seating.",
                attachment_present=True,
                attachment_names=["Seating_Plan_Oct2026.pdf"],
                content_hash="synth_hash_001"
            ),
            RawAnnouncement(
                announcement_id="ANN-SYNTH-002",
                title="Placement Registration for Software Engineers - Google & Microsoft",
                publication_date="2026-10-03",
                reference_number="LPU/PLACEMENT/2026/045",
                full_content="Placement drive registration is open for final year (4th Year) CSE and IT students with CGPA >= 7.5. Eligible students must submit their resume and marksheets on the placement portal by 20th October 2026. Pre-placement talk will be held in Block 32 Auditorium on 18th October at 10:00 AM.",
                attachment_present=False,
                attachment_names=[],
                content_hash="synth_hash_002"
            )
        ]
        report = {
            "total_records": len(records),
            "valid_records": len(records),
            "malformed_records": 0,
            "missing_titles": 0,
            "missing_contents": 0,
            "with_attachments": 1,
            "without_attachments": 1,
            "min_date": "2026-10-01",
            "max_date": "2026-10-03",
            "dataset_path": "SYNTHETIC_DATASET"
        }
        return records, report
