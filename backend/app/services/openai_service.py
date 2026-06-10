"""
Azure OpenAI orchestration: streaming chat completions with function/tool
calling against the Kubernetes diagnostic and mutation tools, optionally
grounded with Azure AI Search RAG context.
"""
import json
import logging
from typing import AsyncGenerator, Dict, List, Optional

from openai import AzureOpenAI

from app.core.config import get_settings
from app.models.schemas import ChatMessage
from app.services.search_service import get_search_service
from app.tools.k8s_diagnostic_tools import DIAGNOSTIC_TOOL_SCHEMAS, dispatch_diagnostic_tool
from app.tools.k8s_mutation_tools import MUTATION_TOOL_SCHEMAS, dispatch_mutation_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AKS Copilot, an SRE assistant with live, read/write access to an \
Azure Kubernetes Service (AKS) cluster via function calling.

Responsibilities:
1. Troubleshoot real-time failures: inspect pods, logs, events, deployments, nodes and \
   correlate them to find root cause before suggesting fixes.
2. When asked to create Kubernetes objects (Pod, Deployment, Service, Secret, ConfigMap), \
   use the create_* tools. Always confirm the namespace and summarize what will be created.
3. For destructive or mutating actions (delete, scale, restart, create), briefly explain \
   what you are about to do and why, then call the tool.
4. Use get_pods / describe_pod / get_pod_logs / get_events / check_pod_health to diagnose \
   before recommending or performing remediation.
5. If runbook context is provided in the conversation, prefer remediation steps grounded \
   in that context and cite the runbook title.
6. Be concise and structure findings as: Observation -> Root Cause -> Recommended/Performed Action.

Never fabricate cluster state - always call a tool to retrieve real data before answering \
questions about the cluster.
"""

ALL_TOOL_SCHEMAS = DIAGNOSTIC_TOOL_SCHEMAS + MUTATION_TOOL_SCHEMAS


def _dispatch_tool(name: str, arguments: Dict) -> Dict:
    diagnostic_names = {t["function"]["name"] for t in DIAGNOSTIC_TOOL_SCHEMAS}
    try:
        if name in diagnostic_names:
            result = dispatch_diagnostic_tool(name, arguments)
        else:
            result = dispatch_mutation_tool(name, arguments)
        return {"ok": True, "result": result}
    except PermissionError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tool '%s' failed", name)
        return {"ok": False, "error": str(exc)}


class OpenAIService:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        self._deployment = settings.azure_openai_deployment

    def _build_messages(self, messages: List[ChatMessage], rag_context: Optional[str]) -> List[Dict]:
        out = [{"role": "system", "content": SYSTEM_PROMPT}]
        if rag_context:
            out.append({"role": "system", "content": rag_context})
        for m in messages:
            entry: Dict = {"role": m.role.value, "content": m.content}
            if m.name:
                entry["name"] = m.name
            if m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
            out.append(entry)
        return out

    async def stream_chat(
        self, messages: List[ChatMessage], use_rag: bool = True, max_tool_iterations: int = 6
    ) -> AsyncGenerator[Dict, None]:
        """
        Yields dict events:
          {"type": "token", "content": "..."}
          {"type": "tool_call", "tool_name": ..., "arguments": ..., "status": "started|completed|failed", "result": ...}
          {"type": "done", "finish_reason": ...}
        """
        rag_context = None
        if use_rag:
            search = get_search_service()
            if search.enabled and messages:
                last_user = next((m.content for m in reversed(messages) if m.role.value == "user"), "")
                rag_context = search.build_context_block(last_user)

        conversation = self._build_messages(messages, rag_context)

        for _ in range(max_tool_iterations):
            stream = self._client.chat.completions.create(
                model=self._deployment,
                messages=conversation,
                tools=ALL_TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.2,
                stream=True,
            )

            content_parts: List[str] = []
            tool_calls_acc: Dict[int, Dict] = {}
            finish_reason = None

            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                if delta.content:
                    content_parts.append(delta.content)
                    yield {"type": "token", "content": delta.content}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        acc = tool_calls_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                        if tc.id:
                            acc["id"] = tc.id
                        if tc.function and tc.function.name:
                            acc["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            acc["arguments"] += tc.function.arguments

            assistant_content = "".join(content_parts)

            if finish_reason == "tool_calls" and tool_calls_acc:
                assistant_msg: Dict = {
                    "role": "assistant",
                    "content": assistant_content or None,
                    "tool_calls": [
                        {
                            "id": acc["id"],
                            "type": "function",
                            "function": {"name": acc["name"], "arguments": acc["arguments"]},
                        }
                        for acc in tool_calls_acc.values()
                    ],
                }
                conversation.append(assistant_msg)

                for acc in tool_calls_acc.values():
                    try:
                        args = json.loads(acc["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}

                    yield {
                        "type": "tool_call",
                        "tool_name": acc["name"],
                        "arguments": args,
                        "status": "started",
                    }

                    tool_result = _dispatch_tool(acc["name"], args)

                    yield {
                        "type": "tool_call",
                        "tool_name": acc["name"],
                        "arguments": args,
                        "status": "completed" if tool_result["ok"] else "failed",
                        "result": tool_result.get("result", tool_result.get("error")),
                    }

                    conversation.append({
                        "role": "tool",
                        "tool_call_id": acc["id"],
                        "content": json.dumps(tool_result, default=str)[:8000],
                    })
                # loop again so the model can use tool results
                continue

            # No further tool calls - we're done
            yield {"type": "done", "finish_reason": finish_reason or "stop"}
            return

        yield {"type": "done", "finish_reason": "max_tool_iterations_reached"}


_openai_service: Optional[OpenAIService] = None


def get_openai_service() -> OpenAIService:
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service
