"""
Pydantic models shared across the API.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = ""
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Conversation/session identifier")
    messages: List[ChatMessage]
    namespace: Optional[str] = Field(
        default=None, description="Default Kubernetes namespace context for this turn"
    )
    use_rag: bool = Field(default=True, description="Augment with AI Search runbook context")


class ToolCallEvent(BaseModel):
    type: str = "tool_call"
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "started"  # started | completed | failed
    result: Optional[Any] = None


class StreamToken(BaseModel):
    type: str = "token"
    content: str


class StreamDone(BaseModel):
    type: str = "done"
    finish_reason: Optional[str] = None


class HealthStatus(BaseModel):
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    kubernetes_connected: bool
    azure_openai_configured: bool
    azure_search_configured: bool


class K8sObjectSpec(BaseModel):
    """Generic spec used when chatbot is asked to create a K8s object from a YAML/dict manifest."""
    namespace: str
    manifest: Dict[str, Any]
    dry_run: bool = False
