"""Tests for preprocessing functions."""

from delivery_exception_system.preprocessing.preprocessor import (
    consolidate_event,
    deduplicate_rows,
)


class TestDeduplication:
    def test_removes_duplicates(self):
        rows = [
            {"shipment_id": "SHP-001", "is_duplicate_scan": "False", "status_code": "DAMAGED"},
            {"shipment_id": "SHP-001", "is_duplicate_scan": "True", "status_code": "DAMAGED"},
        ]
        result = deduplicate_rows(rows)
        assert len(result) == 1

    def test_keeps_all_non_duplicates(self):
        rows = [
            {"shipment_id": "SHP-001", "is_duplicate_scan": "False"},
            {"shipment_id": "SHP-001", "is_duplicate_scan": "False"},
        ]
        result = deduplicate_rows(rows)
        assert len(result) == 2

    def test_handles_missing_field(self):
        rows = [{"shipment_id": "SHP-001"}]
        result = deduplicate_rows(rows)
        assert len(result) == 1


class TestConsolidation:
    def test_picks_highest_attempt(self):
        rows = [
            {"shipment_id": "SHP-001", "attempt_number": "1", "status_code": "ATTEMPTED",
             "timestamp": "t1", "status_description": "Not home", "customer_id": "C1",
             "delivery_address": "123 Main, 10001", "package_type": "STD", "package_size": "MEDIUM"},
            {"shipment_id": "SHP-001", "attempt_number": "2", "status_code": "ATTEMPTED",
             "timestamp": "t2", "status_description": "Still not home", "customer_id": "C1",
             "delivery_address": "123 Main, 10001", "package_type": "STD", "package_size": "MEDIUM"},
        ]
        result = consolidate_event(rows, rows)
        assert result["attempt_number"] == 2
        assert result["status_description"] == "Still not home"

    def test_includes_prior_notes(self):
        rows = [
            {"shipment_id": "SHP-001", "attempt_number": "1", "status_code": "ATTEMPTED",
             "timestamp": "t1", "status_description": "Not home", "customer_id": "C1",
             "delivery_address": "123 Main, 10001", "package_type": "STD", "package_size": "MEDIUM"},
            {"shipment_id": "SHP-001", "attempt_number": "2", "status_code": "ATTEMPTED",
             "timestamp": "t2", "status_description": "Still not home", "customer_id": "C1",
             "delivery_address": "123 Main, 10001", "package_type": "STD", "package_size": "MEDIUM"},
        ]
        result = consolidate_event(rows, rows)
        assert len(result["prior_attempt_notes"]) == 1
        assert "Attempt 1" in result["prior_attempt_notes"][0]

    def test_single_row(self):
        rows = [
            {"shipment_id": "SHP-001", "attempt_number": "1", "status_code": "DAMAGED",
             "timestamp": "t1", "status_description": "Crushed", "customer_id": "C1",
             "delivery_address": "123 Main, 10001", "package_type": "STD", "package_size": "MEDIUM"},
        ]
        result = consolidate_event(rows, rows)
        assert result["attempt_number"] == 1
        assert result["prior_attempt_notes"] == []
