"""ChromaDB vector store creation with optional persistence."""

import hashlib
import logging
import time

import torch
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from delivery_exception_system.config import settings
from delivery_exception_system.data.loader import extract_playbook_pages

logger = logging.getLogger(__name__)

# Module-level cache so we only build once per process
_retriever = None


def _compute_pdf_hash() -> str:
    """Compute SHA-256 hash of the playbook PDF for cache invalidation."""
    h = hashlib.sha256()
    with open(settings.playbook_pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_device() -> str:
    """Select best available device for embeddings."""
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_retriever():
    """Get or create the playbook vector store retriever.

    Uses persistence when possible: if a stored collection exists and the
    PDF hash matches, it reloads from disk instead of re-embedding.
    """
    global _retriever
    if _retriever is not None:
        return _retriever

    device = _get_device()
    logger.info("Embedding device: %s", device)

    embedding_model = HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": device},
    )

    persist_dir = str(settings.vectorstore_dir)
    hash_file = settings.vectorstore_dir / "pdf_hash.txt"

    # Check if we can reuse a persisted collection
    current_hash = _compute_pdf_hash()
    if hash_file.exists():
        stored_hash = hash_file.read_text().strip()
        if stored_hash == current_hash:
            logger.info("Reusing persisted vector store (PDF hash match)")
            vectorstore = Chroma(
                collection_name="playbook",
                embedding_function=embedding_model,
                persist_directory=persist_dir,
            )
            _retriever = vectorstore.as_retriever(
                search_kwargs={"k": settings.retrieve_chunks_num}
            )
            return _retriever

    # Build fresh vector store
    logger.info("Building vector store from playbook PDF...")
    pages = extract_playbook_pages()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = text_splitter.split_documents(pages)
    logger.info("Created %d chunks", len(chunks))

    start = time.perf_counter()
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        collection_name="playbook",
        persist_directory=persist_dir,
    )
    elapsed = time.perf_counter() - start
    logger.info("Vector store ready (%.1fs)", elapsed)

    # Save hash for future runs
    settings.vectorstore_dir.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(current_hash)

    _retriever = vectorstore.as_retriever(
        search_kwargs={"k": settings.retrieve_chunks_num}
    )
    return _retriever
