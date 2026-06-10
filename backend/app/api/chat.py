"""
Chat API: streams Azure OpenAI tool-calling responses as Server-Sent Events.
"""
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest
from app.services.openai_service import get_openai_service
from app.services.streaming_service import to_sse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streams assistant tokens and tool-call events for a conversation turn.

    Event types (one JSON object per SSE frame):
      - {"type": "token", "content": "..."}
      - {"type": "tool_call", "tool_name": "...", "arguments": {...}, "status": "started|completed|failed", "result": ...}
      - {"type": "done", "finish_reason": "..."}
    """
    service = get_openai_service()
    events = service.stream_chat(request.messages, use_rag=request.use_rag)
    return EventSourceResponse(to_sse(events))
