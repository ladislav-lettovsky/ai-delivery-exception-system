"""Tool: read delivery logs from CSV."""

import csv

from langchain_core.tools import tool

from delivery_exception_system.config import settings


@tool
def read_delivery_logs() -> list[dict]:
    """Read all delivery log rows from CSV. Used by preprocessor only."""
    with open(settings.delivery_logs_path, "r") as f:
        return list(csv.DictReader(f))
