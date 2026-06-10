"""
Application configuration loaded from environment variables / .env
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-05-01-preview"

    # Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index: str = "aks-runbooks-index"

    # Kubernetes
    kube_context: str = "in-cluster"
    kube_namespace_allowlist: str = "default,app,monitoring"
    enable_mutations: bool = True

    # App
    app_env: str = "production"
    log_level: str = "INFO"
    cors_origins: str = "*"

    @property
    def allowed_namespaces(self) -> List[str]:
        return [ns.strip() for ns in self.kube_namespace_allowlist.split(",") if ns.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
