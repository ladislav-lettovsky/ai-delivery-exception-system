"""Tool: look up customer profile from SQLite."""

import sqlite3

from langchain_core.tools import tool

from delivery_exception_system.config import settings


@tool
def lookup_customer_profile(customer_id: str, include_pii: bool = False) -> dict:
    """Fetch customer profile from SQLite. PII (name) only included when explicitly requested."""
    with sqlite3.connect(settings.customers_db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
        row = cursor.fetchone()

    if row is None:
        return {}

    profile = dict(row)
    if not include_pii:
        profile.pop("name", None)

    return profile
