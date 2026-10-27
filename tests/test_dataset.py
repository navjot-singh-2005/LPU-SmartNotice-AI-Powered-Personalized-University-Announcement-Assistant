import pytest
from app.services.dataset_service import DatasetService

def test_load_dataset_success():
    service = DatasetService()
    announcements, report = service.load_dataset()

    assert len(announcements) > 0
    assert report["total_records"] > 0
    assert report["valid_records"] == len(announcements)
    assert report["missing_titles"] == 0
    assert report["missing_contents"] == 0

def test_deterministic_id_generation():
    service = DatasetService()
    dummy_record = {
        "title": "Placement Drive Notice",
        "publication_date": "2026-10-05",
        "reference_number": "LPU/PLAC/01",
        "full_content": "Registration open for software engineer placement."
    }

    id1 = service.generate_deterministic_id(dummy_record, 0)
    id2 = service.generate_deterministic_id(dummy_record, 0)

    assert id1 == id2
    assert id1.startswith("ANN-20261005-")
