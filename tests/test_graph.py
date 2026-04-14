"""Integration tests for the LangGraph workflow.

These tests require LLM API keys and are skipped by default.
Run with: pytest tests/test_graph.py --run-integration
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires LLM API keys")


@pytest.mark.integration
class TestGraphIntegration:
    """Placeholder for integration tests that require LLM API access."""

    def test_placeholder(self):
        """Remove this test when real integration tests are added."""
        pytest.skip("Integration tests require LLM API keys")
