"""
Helpers for converting OpenAIService event dicts into Server-Sent Events (SSE).
"""
import json
from typing import AsyncGenerator, Dict


async def to_sse(events: AsyncGenerator[Dict, None]) -> AsyncGenerator[str, None]:
    """Format event dicts as SSE 'data: <json>\\n\\n' frames."""
    async for event in events:
        yield f"data: {json.dumps(event, default=str)}\n\n"
    yield "data: [DONE]\n\n"
