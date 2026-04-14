"""Centralized configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # API Keys
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )
    openai_base_url: str = field(
        default_factory=lambda: os.environ.get("OPENAI_BASE_URL", "")
    )
    hf_token: str = field(
        default_factory=lambda: os.environ.get("HF_TOKEN", "")
    )

    # LangSmith
    langchain_tracing_v2: str = field(
        default_factory=lambda: os.environ.get("LANGCHAIN_TRACING_V2", "false")
    )
    langchain_api_key: str = field(
        default_factory=lambda: os.environ.get("LANGCHAIN_API_KEY", "")
    )
    langchain_project: str = field(
        default_factory=lambda: os.environ.get(
            "LANGCHAIN_PROJECT", "delivery-exception-system"
        )
    )

    # Models
    gen_model: str = "gpt-4o-mini"
    gen_temperature: float = 0.0
    val_model: str = "gpt-4o"
    val_temperature: float = 0.0
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # RAG
    chunk_size: int = 800
    chunk_overlap: int = 200
    retrieve_chunks_num: int = 6

    # Paths
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("DATA_DIR", "data"))
    )

    @property
    def customers_db_path(self) -> Path:
        return self.data_dir / "customers.db"

    @property
    def delivery_logs_path(self) -> Path:
        return self.data_dir / "delivery_logs.csv"

    @property
    def ground_truth_path(self) -> Path:
        return self.data_dir / "ground_truth.csv"

    @property
    def playbook_pdf_path(self) -> Path:
        return self.data_dir / "exception_resolution_playbook.pdf"

    @property
    def vectorstore_dir(self) -> Path:
        return self.data_dir / ".vectorstore"

    # Agent config
    max_loops: int = 2
    max_retries: int = 2

    def apply_env(self) -> None:
        """Push settings into environment variables for LangChain/LangSmith."""
        if self.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.openai_api_key
        if self.openai_base_url:
            os.environ["OPENAI_BASE_URL"] = self.openai_base_url
        if self.hf_token:
            os.environ["HF_TOKEN"] = self.hf_token
        os.environ["LANGCHAIN_TRACING_V2"] = self.langchain_tracing_v2
        if self.langchain_api_key:
            os.environ["LANGCHAIN_API_KEY"] = self.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = self.langchain_project
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"


settings = Settings()
