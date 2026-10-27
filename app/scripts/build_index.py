"""Build persistent ChromaDB index script with safety limits."""
import sys
import argparse
from app.services.dataset_service import DatasetService
from app.services.vector_store_service import VectorStoreService
from app.services.extraction_service import ExtractionService
from app.core.database import init_db
from app.core.config import settings

def main():
    parser = argparse.ArgumentParser(description="Build persistent ChromaDB vector index for LPU announcements.")
    parser.add_argument("--limit", type=int, default=settings.INITIAL_INDEX_LIMIT, help="Limit number of documents to index")
    parser.add_argument("--confirm-full", action="store_true", help="Explicitly confirm indexing full dataset")
    parser.add_argument("--force-reindex", action="store_true", help="Rebuild entire index from scratch")
    args = parser.parse_args()

    init_db()
    dataset_service = DatasetService()
    vector_store = VectorStoreService()
    extraction_service = ExtractionService()

    announcements, _ = dataset_service.load_dataset()
    total_available = len(announcements)

    if args.confirm_full:
        target_records = announcements
        print(f"\n[CONFIRMED FULL INDEXING] Target: All {total_available} records.")
    else:
        target_records = announcements[:args.limit]
        print(f"\n[SAFE BATCH INDEXING] Target: Top {len(target_records)} of {total_available} records.")
        print("Note: To index all historical records, re-run with '--confirm-full'.")

    # Load cached metadata if available
    extracted_map = {}
    for ann in target_records:
        meta = extraction_service.get_cached_metadata(ann.content_hash or "")
        if meta:
            extracted_map[ann.announcement_id] = meta

    print(f"\nGenerating embeddings and upserting {len(target_records)} records into ChromaDB...")
    added, skipped = vector_store.add_or_update_announcements(
        announcements=target_records,
        extracted_map=extracted_map,
        force_reindex=args.force_reindex
    )

    status = vector_store.get_index_status()
    print("\n" + "=" * 60)
    print("      LPU SmartNotice - Vector Indexing Summary")
    print("=" * 60)
    print(f"[Newly Added/Updated]     {added}")
    print(f"[Skipped (Already In Index)] {skipped}")
    print(f"[Total Indexed Documents]  {status['total_indexed_documents']}")
    print(f"[Embedding Model]          {status['embedding_model']}")
    print(f"[Embedding Dimension]      {status['embedding_dimension']}")
    print(f"[Persistent Path]          {status['chroma_path']}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
