# Data Quality and Preprocessing — LPU SmartNotice

## 1. Dataset Overview & Statistics
The input dataset `data/all_announcements_with_attachment_flag.json` was validated upon workspace initialization:
- **Total Announcement Records:** 7,350
- **Records with Valid Titles:** 7,350 (100%)
- **Records with Full Content:** 7,350 (100%)
- **Records Flagged with Attachments:** 3,108 (42.3%)
- **Records without Attachments:** 4,242 (57.7%)

## 2. Deterministic ID Generation
When a source announcement lacks a globally unique primary ID, the system generates a stable, deterministic ID:
```python
raw_key = f"{ref_number}|{publication_date}|{title}|{content_prefix}"
hash_str = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:12]
announcement_id = f"ANN-{pub_date[:10].replace('-', '')}-{hash_str}"
```
This ensures that re-running the dataset loader preserves exact announcement IDs across executions without relying on random UUIDs.

## 3. Deduplication Strategy
Distinguishes between exact duplicates and legitimate notice revisions:
1. **Exact Duplicates:** Identified when the normalized content SHA-256 hash matches a previously processed announcement. Exact duplicate copies are filtered out.
2. **Legitimate Revisions:** Identified when an announcement shares an identical reference number or title but contains updated publication dates or modified content. Revisions are preserved in full to maintain historical notice evolution.

## 4. Immutable Raw Data Layer
- The original source JSON file is treated as immutable read-only input and is never modified or overwritten.
- All processed outputs, extracted structured metadata, and embeddings are stored separately under the `storage/` directory.

---
*Return to [Root README](../README.md)*
