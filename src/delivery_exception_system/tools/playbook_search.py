"""Tool: search the playbook vector store."""

from langchain_core.tools import tool

from delivery_exception_system.data.vectorstore import get_retriever


@tool
def search_playbook(query: str) -> list[dict]:
    """Retrieve relevant playbook sections via vector search. Returns chunks with page metadata."""
    retriever = get_retriever()
    docs = retriever.invoke(query)
    return [
        {"content": d.page_content, "page": d.metadata.get("page", "?")}
        for d in docs
    ]
