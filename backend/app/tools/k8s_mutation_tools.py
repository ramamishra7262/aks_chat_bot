"""
Mutating Kubernetes tools (create/scale/delete/restart) exposed to Azure OpenAI
via function/tool calling. Gated by ENABLE_MUTATIONS and namespace allowlist
(see app/services/kubernetes_service.py).
"""
from typing import Any, Dict
from app.services.kubernetes_service import get_kubernetes_service

MUTATION_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_pod",
            "description": "Create a Pod from a minimal spec (image, name, namespace). Use for quick debug/test pods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "name": {"type": "string"},
                    "image": {"type": "string"},
                    "command": {"type": "array", "items": {"type": "string"}, "description": "Optional container command override"},
                    "labels": {"type": "object", "description": "Optional labels", "additionalProperties": {"type": "string"}},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["namespace", "name", "image"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_deployment",
            "description": "Create a Deployment with given image, replicas, and container port.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "name": {"type": "string"},
                    "image": {"type": "string"},
                    "replicas": {"type": "integer", "default": 1},
                    "container_port": {"type": "integer", "default": 8080},
                    "labels": {"type": "object", "additionalProperties": {"type": "string"}},
                    "env": {"type": "object", "description": "Environment variables", "additionalProperties": {"type": "string"}},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["namespace", "name", "image"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_service",
            "description": "Create a ClusterIP/NodePort/LoadBalancer Service that selects pods by label.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "name": {"type": "string"},
                    "selector": {"type": "object", "additionalProperties": {"type": "string"}},
                    "port": {"type": "integer"},
                    "target_port": {"type": "integer"},
                    "service_type": {"type": "string", "enum": ["ClusterIP", "NodePort", "LoadBalancer"], "default": "ClusterIP"},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["namespace", "name", "selector", "port", "target_port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_secret",
            "description": "Create an Opaque Secret with the given key/value string data (values will be base64-encoded).",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "name": {"type": "string"},
                    "string_data": {"type": "object", "additionalProperties": {"type": "string"}},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["namespace", "name", "string_data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_configmap",
            "description": "Create a ConfigMap with the given key/value data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "name": {"type": "string"},
                    "data": {"type": "object", "additionalProperties": {"type": "string"}},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["namespace", "name", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_resource",
            "description": "Delete a Kubernetes object (Pod, Deployment, Service, Secret, ConfigMap) by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "kind": {"type": "string", "enum": ["Pod", "Deployment", "Service", "Secret", "ConfigMap"]},
                    "name": {"type": "string"},
                },
                "required": ["namespace", "kind", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scale_deployment",
            "description": "Scale a Deployment to the given number of replicas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "name": {"type": "string"},
                    "replicas": {"type": "integer"},
                },
                "required": ["namespace", "name", "replicas"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_deployment",
            "description": "Trigger a rolling restart of a Deployment (e.g. to recover from a stuck/crashed state).",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["namespace", "name"],
            },
        },
    },
]


def _pod_manifest(name: str, image: str, command=None, labels=None) -> Dict[str, Any]:
    spec_container: Dict[str, Any] = {"name": name, "image": image}
    if command:
        spec_container["command"] = command
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": name, "labels": labels or {"app": name}},
        "spec": {"containers": [spec_container], "restartPolicy": "Never"},
    }


def _deployment_manifest(name: str, image: str, replicas: int, container_port: int,
                          labels=None, env=None) -> Dict[str, Any]:
    labels = labels or {"app": name}
    env_list = [{"name": k, "value": v} for k, v in (env or {}).items()]
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "labels": labels},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [{
                        "name": name,
                        "image": image,
                        "ports": [{"containerPort": container_port}],
                        "env": env_list,
                    }]
                },
            },
        },
    }


def _service_manifest(name: str, selector: Dict[str, str], port: int, target_port: int,
                       service_type: str) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name},
        "spec": {
            "type": service_type,
            "selector": selector,
            "ports": [{"port": port, "targetPort": target_port}],
        },
    }


def _secret_manifest(name: str, string_data: Dict[str, str]) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "Opaque",
        "metadata": {"name": name},
        "stringData": string_data,
    }


def _configmap_manifest(name: str, data: Dict[str, str]) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name},
        "data": data,
    }


def dispatch_mutation_tool(name: str, arguments: Dict[str, Any]) -> Any:
    k8s = get_kubernetes_service()
    ns = arguments["namespace"]
    dry_run = arguments.get("dry_run", False)

    if name == "create_pod":
        manifest = _pod_manifest(arguments["name"], arguments["image"],
                                  arguments.get("command"), arguments.get("labels"))
        return k8s.create_object(ns, manifest, dry_run)

    if name == "create_deployment":
        manifest = _deployment_manifest(
            arguments["name"], arguments["image"], arguments.get("replicas", 1),
            arguments.get("container_port", 8080), arguments.get("labels"), arguments.get("env"),
        )
        return k8s.create_object(ns, manifest, dry_run)

    if name == "create_service":
        manifest = _service_manifest(
            arguments["name"], arguments["selector"], arguments["port"],
            arguments["target_port"], arguments.get("service_type", "ClusterIP"),
        )
        return k8s.create_object(ns, manifest, dry_run)

    if name == "create_secret":
        manifest = _secret_manifest(arguments["name"], arguments["string_data"])
        return k8s.create_object(ns, manifest, dry_run)

    if name == "create_configmap":
        manifest = _configmap_manifest(arguments["name"], arguments["data"])
        return k8s.create_object(ns, manifest, dry_run)

    if name == "delete_resource":
        return k8s.delete_resource(ns, arguments["kind"], arguments["name"])

    if name == "scale_deployment":
        return k8s.scale_deployment(ns, arguments["name"], arguments["replicas"])

    if name == "restart_deployment":
        return k8s.restart_deployment(ns, arguments["name"])

    raise ValueError(f"Unknown mutation tool: {name}")
