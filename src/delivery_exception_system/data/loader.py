"""Data loading utilities for CSV, SQLite, and PDF sources."""

import logging

import pandas as pd
from langchain_core.documents import Document
from pypdf import PdfReader

from delivery_exception_system.config import settings

logger = logging.getLogger(__name__)


def load_delivery_logs() -> pd.DataFrame:
    """Load delivery logs CSV into a DataFrame."""
    df = pd.read_csv(settings.delivery_logs_path)
    logger.info("Loaded %d delivery log rows", len(df))
    return df


def load_ground_truth() -> pd.DataFrame:
    """Load ground truth CSV into a DataFrame."""
    df = pd.read_csv(settings.ground_truth_path)
    logger.info("Loaded %d ground truth rows", len(df))
    return df


def extract_playbook_pages() -> list[Document]:
    """Extract text pages from the playbook PDF as LangChain Documents."""
    reader = PdfReader(settings.playbook_pdf_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append(
                Document(page_content=text, metadata={"source": "playbook", "page": i + 1})
            )
    logger.info("Extracted %d pages from playbook PDF", len(pages))
    return pages
