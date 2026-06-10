#!/usr/bin/env python3
"""
Builds (or rebuilds) the Azure AI Search index used for RAG over Kubernetes /
AKS troubleshooting runbooks.

It:
  1. Creates a vector-enabled index (if it doesn't already exist).
  2. Chunks each markdown runbook in infra/runbooks/.
  3. Embeds each chunk with the Azure OpenAI text-embedding-3-small deployment.
  4. Uploads the chunks + vectors to Azure AI Search.

Environment variables required:
  AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION
  AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY, AZURE_SEARCH_INDEX
"""
import os
import glob
import hashlib
import sys

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)
from openai import AzureOpenAI

EMBEDDING_DEPLOYMENT = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
RUNBOOK_DIR = os.path.join(os.path.dirname(__file__), "..", "runbooks")
CHUNK_SIZE_CHARS = 1500


def chunk_text(text: str, size: int = CHUNK_SIZE_CHARS):
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) > size and current:
            chunks.append(current.strip())
            current = ""
        current += p + "\n\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def build_index(index_client: SearchIndexClient, index_name: str) -> None:
    if index_name in [i.name for i in index_client.list_indexes()]:
        print(f"Index '{index_name}' already exists - skipping creation")
        return

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="default-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
        profiles=[VectorSearchProfile(name="default-profile", algorithm_configuration_name="default-hnsw")],
    )

    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
    index_client.create_index(index)
    print(f"Created index '{index_name}'")


def main() -> int:
    aoai = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
    )

    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    search_key = os.environ["AZURE_SEARCH_API_KEY"]
    index_name = os.environ.get("AZURE_SEARCH_INDEX", "aks-runbooks-index")
    credential = AzureKeyCredential(search_key)

    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
    build_index(index_client, index_name)

    search_client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)

    docs = []
    for path in sorted(glob.glob(os.path.join(RUNBOOK_DIR, "*.md"))):
        title = os.path.splitext(os.path.basename(path))[0].replace("-", " ").title()
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        for i, chunk in enumerate(chunk_text(content)):
            embedding = aoai.embeddings.create(model=EMBEDDING_DEPLOYMENT, input=chunk).data[0].embedding
            doc_id = hashlib.sha256(f"{path}-{i}".encode()).hexdigest()
            docs.append({
                "id": doc_id,
                "title": title,
                "content": chunk,
                "source": os.path.basename(path),
                "contentVector": embedding,
            })

    if not docs:
        print(f"No runbooks found in {RUNBOOK_DIR} - nothing to index")
        return 0

    result = search_client.upload_documents(documents=docs)
    failed = [r for r in result if not r.succeeded]
    print(f"Indexed {len(docs) - len(failed)}/{len(docs)} chunks into '{index_name}'")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
