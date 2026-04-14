"""Shared test fixtures."""

import os
import sys

import pytest

# Ensure the src/ directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Point DATA_DIR to the project data/ directory
os.environ["DATA_DIR"] = os.path.join(os.path.dirname(__file__), "..", "data")
# Suppress LangSmith tracing during tests
os.environ["LANGCHAIN_TRACING_V2"] = "false"
