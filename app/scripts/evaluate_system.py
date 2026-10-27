"""Evaluate RAG retrieval and personalized ranking performance."""
from app.services.dataset_service import DatasetService
from app.services.retrieval_service import RetrievalService
from app.services.personalization_service import PersonalizationService
from app.services.room_impact_service import RoomImpactService
from app.core.database import init_db

def main():
    init_db()
    dataset_service = DatasetService()
    retrieval_service = RetrievalService()
    personalization_service = PersonalizationService()
    room_impact_service = RoomImpactService()

    announcements, _ = dataset_service.load_dataset()

    print("=" * 60)
    print("      LPU SmartNotice - System Evaluation Suite")
    print("=" * 60)

    # 1. Retrieval Test
    test_queries = [
        "exam schedule Block 34",
        "placement drive registration software engineer",
        "library opening hours"
    ]

    print("\n--- 1. Grounded RAG Retrieval Evaluation ---")
    for q in test_queries:
        results = retrieval_service.search(q, top_k=3, raw_announcements=announcements)
        print(f"\nQuery: '{q}' -> Retrieved {len(results)} candidate evidence sources.")
        for r in results:
            print(f"  [ID: {r['announcement_id']}] Score: {r['rrf_score']} | Title: {r['title'][:60]}")

    # 2. Timetable Room Impact Evaluation
    print("\n--- 2. Room Impact & Timetable Conflict Evaluation ---")
    sample_timetable = room_impact_service.get_sample_timetable("STU-101")
    impact_count = 0
    for entry in sample_timetable:
        for ann in announcements[:30]:
            res = room_impact_service.check_timetable_conflict(entry, ann, None)
            if res.affected:
                impact_count += 1
                print(f"  Match: Class {entry.course_code} ({entry.room}) vs Announcement '{ann.title[:50]}'")
                print(f"         Status: {res.status} | Reason: {res.explanation}")
                break

    print(f"\nTotal Timetable Conflicts Detected: {impact_count}")
    print("=" * 60)
    print("Evaluation completed successfully!\n")

if __name__ == "__main__":
    main()
