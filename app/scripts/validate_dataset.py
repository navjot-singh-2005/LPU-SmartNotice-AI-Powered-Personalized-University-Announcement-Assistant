"""Validate dataset script - executes without making API calls."""
import sys
import argparse
from app.services.dataset_service import DatasetService
from app.services.deduplication_service import DeduplicationService

def main():
    parser = argparse.ArgumentParser(description="Validate LPU SmartNotice announcement dataset.")
    parser.add_argument("--path", type=str, default=None, help="Custom path to dataset JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("      LPU SmartNotice - Dataset Validation Report")
    print("=" * 60)

    dataset_service = DatasetService(args.path)
    dedup_service = DeduplicationService()

    try:
        announcements, report = dataset_service.load_dataset()
    except Exception as e:
        print(f"\n[ERROR] Failed to load dataset: {e}")
        sys.exit(1)

    unique_announcements, dedup_report = dedup_service.process_deduplication(announcements)

    print(f"\n[Dataset Path]        {report['dataset_path']}")
    print(f"[Total Raw Records]   {report['total_records']}")
    print(f"[Valid Records]       {report['valid_records']}")
    print(f"[Malformed Records]   {report['malformed_records']}")
    print(f"[Missing Titles]      {report['missing_titles']}")
    print(f"[Missing Content]     {report['missing_contents']}")
    print(f"[With Attachments]    {report['with_attachments']}")
    print(f"[Without Attachments] {report['without_attachments']}")
    print(f"[Date Range]          {report['min_date']} to {report['max_date']}")

    print("\n" + "-" * 60)
    print("      Deduplication Analysis")
    print("-" * 60)
    print(f"[Unique Records]       {dedup_report['unique_total']}")
    print(f"[Exact Duplicates]     {dedup_report['exact_duplicates_removed']}")
    print(f"[Revisions Preserved]  {dedup_report['revisions_detected']}")
    print("=" * 60)
    print("Dataset validation complete! No external API calls were made.\n")

if __name__ == "__main__":
    main()
