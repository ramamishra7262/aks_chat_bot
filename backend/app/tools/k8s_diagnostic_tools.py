"""
Read-only Kubernetes diagnostic tools exposed to Azure OpenAI via function/tool calling.

Each entry pairs an OpenAI tool schema with a callable that the dispatcher
in app/services/openai_service.py invokes.
"""
from typing import Any, Dict
from app.services.kubernetes_service import get_kubernetes_service

DIAGNOSTIC_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_pods",
            "description": "List pods in a namespace with status, restarts, and node placement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Kubernetes namespace"},
                    "label_selector": {"type": "string", "description": "Optional label selector, e.g. app=backend"},
                },
                "required": ["namespace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pod_logs",
            "description": "Fetch recent logs for a pod/container. Use to diagnose crash loops or errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "pod_name": {"type": "string"},
                    "container": {"type": "string", "description": "Optional container name"},
                    "tail_lines": {"type": "integer", "description": "Number of lines to return", "default": 200},
                    "previous": {"type": "boolean", "description": "Get logs from previous (crashed) container instance", "default": False},
                },
                "required": ["namespace", "pod_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_pod",
            "description": "Get detailed status, conditions, and container states for a pod (like kubectl describe).",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "pod_name": {"type": "string"},
                },
                "required": ["namespace", "pod_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": "List recent Kubernetes events in a namespace (Warning/Normal), useful for root cause analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "field_selector": {"type": "string", "description": "Optional field selector, e.g. involvedObject.name=mypod"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["namespace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deployments",
            "description": "List deployments in a namespace with replica counts and rollout status.",
            "parameters": {
                "type": "object",
                "properties": {"namespace": {"type": "string"}},
                "required": ["namespace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_services",
            "description": "List services in a namespace with type, cluster IP, and ports.",
            "parameters": {
                "type": "object",
                "properties": {"namespace": {"type": "string"}},
                "required": ["namespace"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_nodes",
            "description": "List cluster nodes with readiness, capacity, and allocatable resources.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_pod_health",
            "description": "Quick health summary for a namespace - counts healthy vs unhealthy pods and lists problem pods.",
            "parameters": {
                "type": "object",
                "properties": {"namespace": {"type": "string"}},
                "required": ["namespace"],
            },
        },
    },
]


def dispatch_diagnostic_tool(name: str, arguments: Dict[str, Any]) -> Any:
    k8s = get_kubernetes_service()
    if name == "get_pods":
        return k8s.get_pods(arguments["namespace"], arguments.get("label_selector"))
    if name == "get_pod_logs":
        return k8s.get_pod_logs(
            arguments["namespace"], arguments["pod_name"],
            arguments.get("container"), arguments.get("tail_lines", 200),
            arguments.get("previous", False),
        )
    if name == "describe_pod":
        return k8s.describe_pod(arguments["namespace"], arguments["pod_name"])
    if name == "get_events":
        return k8s.get_events(arguments["namespace"], arguments.get("field_selector"), arguments.get("limit", 50))
    if name == "get_deployments":
        return k8s.get_deployments(arguments["namespace"])
    if name == "get_services":
        return k8s.get_services(arguments["namespace"])
    if name == "get_nodes":
        return k8s.get_nodes()
    if name == "check_pod_health":
        return k8s.check_pod_health(arguments["namespace"])
    raise ValueError(f"Unknown diagnostic tool: {name}")
