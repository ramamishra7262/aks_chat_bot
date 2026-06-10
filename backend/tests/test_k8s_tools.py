from unittest.mock import MagicMock, patch

from app.tools.k8s_diagnostic_tools import dispatch_diagnostic_tool
from app.tools.k8s_mutation_tools import dispatch_mutation_tool


@patch("app.tools.k8s_diagnostic_tools.get_kubernetes_service")
def test_dispatch_get_pods(mock_get_service):
    mock_service = MagicMock()
    mock_service.get_pods.return_value = [{"name": "pod-1", "phase": "Running"}]
    mock_get_service.return_value = mock_service

    result = dispatch_diagnostic_tool("get_pods", {"namespace": "default"})

    assert result == [{"name": "pod-1", "phase": "Running"}]
    mock_service.get_pods.assert_called_once_with("default", None)


@patch("app.tools.k8s_diagnostic_tools.get_kubernetes_service")
def test_dispatch_unknown_tool_raises(mock_get_service):
    try:
        dispatch_diagnostic_tool("not_a_tool", {})
        assert False, "expected ValueError"
    except ValueError:
        pass


@patch("app.tools.k8s_mutation_tools.get_kubernetes_service")
def test_dispatch_scale_deployment(mock_get_service):
    mock_service = MagicMock()
    mock_service.scale_deployment.return_value = {"status": "scaled", "name": "api", "replicas": 3}
    mock_get_service.return_value = mock_service

    result = dispatch_mutation_tool("scale_deployment", {"namespace": "app", "name": "api", "replicas": 3})

    assert result["status"] == "scaled"
    mock_service.scale_deployment.assert_called_once_with("app", "api", 3)


@patch("app.tools.k8s_mutation_tools.get_kubernetes_service")
def test_dispatch_create_deployment_builds_manifest(mock_get_service):
    mock_service = MagicMock()
    mock_service.create_object.return_value = {"status": "created"}
    mock_get_service.return_value = mock_service

    dispatch_mutation_tool("create_deployment", {
        "namespace": "app", "name": "web", "image": "nginx:1.25", "replicas": 2, "container_port": 80,
    })

    args, kwargs = mock_service.create_object.call_args
    namespace, manifest, dry_run = args
    assert namespace == "app"
    assert manifest["kind"] == "Deployment"
    assert manifest["spec"]["replicas"] == 2
    assert manifest["spec"]["template"]["spec"]["containers"][0]["image"] == "nginx:1.25"
