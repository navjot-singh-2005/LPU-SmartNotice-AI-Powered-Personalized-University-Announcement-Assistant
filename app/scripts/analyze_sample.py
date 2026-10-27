"""Analyze small sample script with dry-run support."""
import argparse
import json
from app.services.dataset_service import DatasetService
from app.services.extraction_service import ExtractionService
from app.core.database import init_db

def main():
    parser = argparse.ArgumentParser(description="Analyze a small sample of announcements using Gemini.")
    parser.add_argument("--limit", type=int, default=5, help="Number of records to sample")
    parser.add_argument("--dry-run", action="store_true", help="Simulate extraction without making Gemini API calls")
    args = parser.parse_args()

    init_db()
    dataset_service = DatasetService()
    extraction_service = ExtractionService()

    announcements, _ = dataset_service.load_dataset()
    sample = announcements[:args.limit]

    print("=" * 60)
    print(f"  LPU SmartNotice - Sample Analysis (Limit: {args.limit}, Dry-Run: {args.dry_run})")
    print("=" * 60)

    if args.dry_run:
        print(f"\n[DRY RUN MODE] Simulating processing of {len(sample)} announcements.")
        print(f"Estimated Gemini API calls: {len(sample)}")
        print("Estimated token usage: ~{len(sample) * 400} input tokens")
        for i, ann in enumerate(sample, 1):
            print(f"\n[{i}/{len(sample)}] {ann.title}")
            print(f"  ID: {ann.announcement_id} | Date: {ann.publication_date} | Has Attachment: {ann.attachment_present}")
            meta = extraction_service.fallback_heuristic_extraction(ann)
            print(f"  Category: {meta.category} | Action Type: {meta.action_type} | Urgency: {meta.urgency}")
        print("\nDry-run completed successfully.")
        return

    print(f"\nProcessing {len(sample)} records using Gemini structured output...")
    for i, ann in enumerate(sample, 1):
        print(f"\n--- [{i}/{len(sample)}] ID: {ann.announcement_id} ---")
        print(f"Title: {ann.title}")
        meta = extraction_service.extract_metadata(ann, use_cache=True)
        print(f"Category: {meta.category}")
        print(f"Summary: {meta.summary}")
        print(f"Action Required: {meta.action_required} ({meta.action_type})")
        print(f"Decision Completeness: {meta.decision_completeness}")
        print(f"Confidence: {meta.confidence}")

    print("\nSample analysis complete.")

if __name__ == "__main__":
    main()
