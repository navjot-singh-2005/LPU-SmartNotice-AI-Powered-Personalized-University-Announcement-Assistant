from app.services.personalization_service import PersonalizationService

def test_personalization_scoring(sample_student_profile, sample_raw_announcement, sample_extracted_metadata):
    service = PersonalizationService()
    scores = service.score_announcement(sample_student_profile, sample_raw_announcement, sample_extracted_metadata)

    assert scores["personal_priority_score"] > 0.6
    assert scores["year_match_score"] == 1.0
    assert scores["dept_match_score"] == 1.0
    assert "Targeted for Year 3" in scores["explanation"]

def test_global_importance_override(sample_student_profile, sample_raw_announcement, sample_extracted_metadata):
    service = PersonalizationService()

    # Modify metadata to simulate urgent university-wide notice
    sample_extracted_metadata.target_year = [1] # Mismatched year (Year 1 vs Student Year 3)
    sample_extracted_metadata.global_importance = "HIGH"

    scores = service.score_announcement(sample_student_profile, sample_raw_announcement, sample_extracted_metadata)

    assert scores["is_override"] is True
    assert scores["personal_priority_score"] >= 0.85
    assert "override" in scores["explanation"].lower()


def test_live_notice_recency_primary_sorting(sample_student_profile):
    """Verify newest real-time live notices sort at the top of the feed ahead of older live notices."""
    from app.models.announcement import RawAnnouncement
    service = PersonalizationService()

    older_live = RawAnnouncement(
        announcement_id="ANN-UMS-OLD",
        title="B.Tech Computer Science Coding Contest",
        publication_date="2026-09-15",
        reference_number="REF-001",
        full_content="Coding contest for CSE 3rd year students with python and algorithms.",
        attachment_present=False,
        attachment_names=[],
        content_hash="hash_old",
        source="ums_official",
    )

    newer_live = RawAnnouncement(
        announcement_id="ANN-UMS-NEW",
        title="General Campus Life Announcement",
        publication_date="2026-10-24",
        reference_number="REF-002",
        full_content="General announcement for all students across campus.",
        attachment_present=False,
        attachment_names=[],
        content_hash="hash_new",
        source="ums_official",
    )

    feed_result = service.personalize_feed(
        student=sample_student_profile,
        announcements=[older_live, newer_live],
        page=1,
        page_size=10
    )

    feed = feed_result["feed"]
    assert len(feed) == 2
    # Newer live notice (2026-10-24) must sort at index 0 ahead of older live notice (2026-09-15)
    assert feed[0]["announcement_id"] == "ANN-UMS-NEW"
    assert feed[1]["announcement_id"] == "ANN-UMS-OLD"

