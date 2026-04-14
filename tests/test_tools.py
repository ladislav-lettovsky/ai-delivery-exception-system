"""Tests for tool functions using real data files."""

import os
import pytest

# Skip if data files are not present
DATA_DIR = os.environ.get("DATA_DIR", "data")
HAS_DATA = os.path.exists(os.path.join(DATA_DIR, "customers.db"))


@pytest.mark.skipif(not HAS_DATA, reason="Data files not present")
class TestCustomerProfile:
    def test_lookup_existing_customer(self):
        from delivery_exception_system.tools.customer_profile import lookup_customer_profile
        result = lookup_customer_profile.invoke({"customer_id": "CUST-001", "include_pii": False})
        assert result
        assert "tier" in result
        assert "name" not in result  # PII redacted

    def test_lookup_with_pii(self):
        from delivery_exception_system.tools.customer_profile import lookup_customer_profile
        result = lookup_customer_profile.invoke({"customer_id": "CUST-001", "include_pii": True})
        assert "name" in result

    def test_lookup_nonexistent(self):
        from delivery_exception_system.tools.customer_profile import lookup_customer_profile
        result = lookup_customer_profile.invoke({"customer_id": "CUST-999", "include_pii": False})
        assert result == {}


@pytest.mark.skipif(not HAS_DATA, reason="Data files not present")
class TestLockerAvailability:
    def test_check_lockers(self):
        from delivery_exception_system.tools.locker_availability import check_locker_availability
        result = check_locker_availability.invoke({"zip_code": "10001", "package_size": "MEDIUM"})
        assert isinstance(result, list)
        for locker in result:
            assert "eligible" in locker
            assert "reason" in locker


@pytest.mark.skipif(not HAS_DATA, reason="Data files not present")
class TestDeliveryLogs:
    def test_read_logs(self):
        from delivery_exception_system.tools.delivery_logs import read_delivery_logs
        result = read_delivery_logs.invoke({})
        assert isinstance(result, list)
        assert len(result) > 0
        assert "shipment_id" in result[0]
