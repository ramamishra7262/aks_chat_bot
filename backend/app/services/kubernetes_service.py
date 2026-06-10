"""
Thin wrapper around the official Kubernetes Python client.

Loads in-cluster config when running inside AKS (via the bot's ServiceAccount
and RBAC bindings - see k8s/serviceaccount.yaml), falling back to local
kubeconfig for development.
"""
import logging
from typing import Any, Dict, List, Optional

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class KubernetesService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._load_config()
        self.core = client.CoreV1Api()
        self.apps = client.AppsV1Api()
        self.events_api = client.EventsV1Api()

    def _load_config(self) -> None:
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except config.ConfigException:
            try:
                config.load_kube_config()
                logger.info("Loaded local kubeconfig")
            except config.ConfigException:
                logger.warning("No Kubernetes config found - K8s tools will fail until configured")

    # ------------------------------------------------------------------
    # Guardrails
    # ------------------------------------------------------------------
    def _check_namespace(self, namespace: str) -> None:
        allowed = self._settings.allowed_namespaces
        if "*" in allowed:
            return
        if namespace not in allowed:
            raise PermissionError(
                f"Namespace '{namespace}' is not in the allowlist {allowed}. "
                "Update KUBE_NAMESPACE_ALLOWLIST to permit this namespace."
            )

    def _check_mutations_enabled(self) -> None:
        if not self._settings.enable_mutations:
            raise PermissionError("Mutating operations are disabled (ENABLE_MUTATIONS=false).")

    # ------------------------------------------------------------------
    # Diagnostic (read-only) operations
    # ------------------------------------------------------------------
    def get_pods(self, namespace: str, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        self._check_namespace(namespace)
        pods = self.core.list_namespaced_pod(namespace, label_selector=label_selector or "")
        result = []
        for p in pods.items:
            container_statuses = p.status.container_statuses or []
            restarts = sum(cs.restart_count for cs in container_statuses)
            result.append({
                "name": p.metadata.name,
                "namespace": p.metadata.namespace,
                "phase": p.status.phase,
                "node": p.spec.node_name,
                "restarts": restarts,
                "containers": [c.name for c in p.spec.containers],
                "ready": all(cs.ready for cs in container_statuses) if container_statuses else False,
                "start_time": str(p.status.start_time) if p.status.start_time else None,
            })
        return result

    def get_pod_logs(self, namespace: str, pod_name: str, container: Optional[str] = None,
                      tail_lines: int = 200, previous: bool = False) -> str:
        self._check_namespace(namespace)
        try:
            return self.core.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
                previous=previous,
            )
        except ApiException as e:
            return f"Error fetching logs: {e.reason} (status {e.status})"

    def describe_pod(self, namespace: str, pod_name: str) -> Dict[str, Any]:
        self._check_namespace(namespace)
        pod = self.core.read_namespaced_pod(pod_name, namespace)
        conditions = [
            {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
            for c in (pod.status.conditions or [])
        ]
        container_statuses = []
        for cs in pod.status.container_statuses or []:
            state = cs.state
            state_desc = "unknown"
            if state.running:
                state_desc = f"running since {state.running.started_at}"
            elif state.waiting:
                state_desc = f"waiting: {state.waiting.reason} - {state.waiting.message}"
            elif state.terminated:
                state_desc = (
                    f"terminated: {state.terminated.reason} "
                    f"(exit code {state.terminated.exit_code})"
                )
            container_statuses.append({
                "name": cs.name,
                "ready": cs.ready,
                "restart_count": cs.restart_count,
                "state": state_desc,
            })
        return {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "phase": pod.status.phase,
            "node": pod.spec.node_name,
            "conditions": conditions,
            "container_statuses": container_statuses,
            "labels": pod.metadata.labels,
        }

    def get_events(self, namespace: str, field_selector: Optional[str] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        self._check_namespace(namespace)
        events = self.core.list_namespaced_event(namespace, field_selector=field_selector or "")
        items = sorted(
            events.items,
            key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp,
            reverse=True,
        )[:limit]
        return [{
            "type": e.type,
            "reason": e.reason,
            "message": e.message,
            "involved_object": f"{e.involved_object.kind}/{e.involved_object.name}",
            "count": e.count,
            "last_timestamp": str(e.last_timestamp or e.event_time),
        } for e in items]

    def get_deployments(self, namespace: str) -> List[Dict[str, Any]]:
        self._check_namespace(namespace)
        deployments = self.apps.list_namespaced_deployment(namespace)
        return [{
            "name": d.metadata.name,
            "namespace": d.metadata.namespace,
            "replicas": d.spec.replicas,
            "ready_replicas": d.status.ready_replicas or 0,
            "available_replicas": d.status.available_replicas or 0,
            "updated_replicas": d.status.updated_replicas or 0,
            "image": d.spec.template.spec.containers[0].image if d.spec.template.spec.containers else None,
            "strategy": d.spec.strategy.type if d.spec.strategy else None,
        } for d in deployments.items]

    def get_services(self, namespace: str) -> List[Dict[str, Any]]:
        self._check_namespace(namespace)
        services = self.core.list_namespaced_service(namespace)
        return [{
            "name": s.metadata.name,
            "type": s.spec.type,
            "cluster_ip": s.spec.cluster_ip,
            "ports": [{"port": p.port, "target_port": str(p.target_port), "protocol": p.protocol}
                      for p in (s.spec.ports or [])],
            "selector": s.spec.selector,
        } for s in services.items]

    def get_nodes(self) -> List[Dict[str, Any]]:
        nodes = self.core.list_node()
        result = []
        for n in nodes.items:
            conditions = {c.type: c.status for c in (n.status.conditions or [])}
            result.append({
                "name": n.metadata.name,
                "ready": conditions.get("Ready") == "True",
                "conditions": conditions,
                "capacity": n.status.capacity,
                "allocatable": n.status.allocatable,
                "kubelet_version": n.status.node_info.kubelet_version if n.status.node_info else None,
                "labels": n.metadata.labels,
            })
        return result

    def check_pod_health(self, namespace: str) -> Dict[str, Any]:
        """Aggregate health summary - useful for fast triage."""
        pods = self.get_pods(namespace)
        unhealthy = [
            p for p in pods
            if p["phase"] not in ("Running", "Succeeded") or not p["ready"] or p["restarts"] > 5
        ]
        return {
            "namespace": namespace,
            "total_pods": len(pods),
            "healthy_pods": len(pods) - len(unhealthy),
            "unhealthy_pods": unhealthy,
        }

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------
    def create_object(self, namespace: str, manifest: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        self._check_namespace(namespace)
        self._check_mutations_enabled()

        kind = manifest.get("kind", "")
        api_version = manifest.get("apiVersion", "v1")
        dry_run_param = "All" if dry_run else None

        try:
            if kind == "Pod":
                resp = self.core.create_namespaced_pod(namespace, manifest, dry_run=dry_run_param)
            elif kind == "Deployment":
                resp = self.apps.create_namespaced_deployment(namespace, manifest, dry_run=dry_run_param)
            elif kind == "Service":
                resp = self.core.create_namespaced_service(namespace, manifest, dry_run=dry_run_param)
            elif kind == "Secret":
                resp = self.core.create_namespaced_secret(namespace, manifest, dry_run=dry_run_param)
            elif kind == "ConfigMap":
                resp = self.core.create_namespaced_config_map(namespace, manifest, dry_run=dry_run_param)
            else:
                raise ValueError(f"Unsupported kind '{kind}' (apiVersion {api_version}). "
                                  "Supported: Pod, Deployment, Service, Secret, ConfigMap.")
            return {
                "status": "created" if not dry_run else "validated (dry-run)",
                "kind": kind,
                "name": resp.metadata.name,
                "namespace": resp.metadata.namespace,
            }
        except ApiException as e:
            return {"status": "error", "kind": kind, "reason": e.reason, "details": e.body}

    def delete_resource(self, namespace: str, kind: str, name: str) -> Dict[str, Any]:
        self._check_namespace(namespace)
        self._check_mutations_enabled()
        try:
            if kind == "Pod":
                self.core.delete_namespaced_pod(name, namespace)
            elif kind == "Deployment":
                self.apps.delete_namespaced_deployment(name, namespace)
            elif kind == "Service":
                self.core.delete_namespaced_service(name, namespace)
            elif kind == "Secret":
                self.core.delete_namespaced_secret(name, namespace)
            elif kind == "ConfigMap":
                self.core.delete_namespaced_config_map(name, namespace)
            else:
                raise ValueError(f"Unsupported kind '{kind}'.")
            return {"status": "deleted", "kind": kind, "name": name, "namespace": namespace}
        except ApiException as e:
            return {"status": "error", "reason": e.reason, "details": e.body}

    def scale_deployment(self, namespace: str, name: str, replicas: int) -> Dict[str, Any]:
        self._check_namespace(namespace)
        self._check_mutations_enabled()
        try:
            patch = {"spec": {"replicas": replicas}}
            resp = self.apps.patch_namespaced_deployment_scale(name, namespace, patch)
            return {"status": "scaled", "name": name, "replicas": resp.spec.replicas}
        except ApiException as e:
            return {"status": "error", "reason": e.reason, "details": e.body}

    def restart_deployment(self, namespace: str, name: str) -> Dict[str, Any]:
        """Triggers a rolling restart via the kubectl.kubernetes.io/restartedAt annotation."""
        self._check_namespace(namespace)
        self._check_mutations_enabled()
        from datetime import datetime, timezone
        patch = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            }
        }
        try:
            self.apps.patch_namespaced_deployment(name, namespace, patch)
            return {"status": "restart-triggered", "name": name, "namespace": namespace}
        except ApiException as e:
            return {"status": "error", "reason": e.reason, "details": e.body}


_kubernetes_service: Optional[KubernetesService] = None


def get_kubernetes_service() -> KubernetesService:
    global _kubernetes_service
    if _kubernetes_service is None:
        _kubernetes_service = KubernetesService()
    return _kubernetes_service
