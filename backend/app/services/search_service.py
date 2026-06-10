"""
Azure AI Search integration for Retrieval-Augmented Generation (RAG).

The index (created by infra/scripts/index-k8s-docs.py) stores chunks of
Kubernetes/AKS troubleshooting runbooks with vector embeddings. We use a
hybrid (vector + keyword) query so the chatbot can ground its answers in
the team's own runbooks rather than hallucinating remediation steps.
"""
import logging
from typing import Any, Dict, List, Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DEPLOYMENT = "text-embedding-3-small"


class SearchService:
    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = bool(settings.azure_search_endpoint and settings.azure_search_api_key)
        self._settings = settings
        if self._enabled:
            self._client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index,
                credential=AzureKeyCredential(settings.azure_search_api_key),
            )
            self._aoai = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
        else:
            logger.warning("Azure AI Search not configured - RAG context will be skipped")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _embed(self, text: str) -> List[float]:
        resp = self._aoai.embeddings.create(model=EMBEDDING_DEPLOYMENT, input=text)
        return resp.data[0].embedding

    def search_runbooks(self, query: str, top: int = 3) -> List[Dict[str, Any]]:
        """Hybrid vector + keyword search over the K8s/AKS runbook index."""
        if not self._enabled:
            return []
        try:
            vector_query = VectorizedQuery(vector=self._embed(query), k_nearest_neighbors=top, fields="contentVector")
            results = self._client.search(
                search_text=query,
                vector_queries=[vector_query],
                select=["id", "title", "content", "source"],
                top=top,
            )
            return [{
                "title": r.get("title"),
                "content": r.get("content"),
                "source": r.get("source"),
                "score": r.get("@search.score"),
            } for r in results]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Azure AI Search query failed")
            return []

    def build_context_block(self, query: str, top: int = 3) -> Optional[str]:
        docs = self.search_runbooks(query, top=top)
        if not docs:
            return None
        parts = ["Relevant runbook excerpts:"]
        for d in docs:
            parts.append(f"### {d['title']} (source: {d['source']})\n{d['content']}")
        return "\n\n".join(parts)


_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
