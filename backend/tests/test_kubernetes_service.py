import pytest

from app.services.kubernetes_service import KubernetesService


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(KubernetesService, "_load_config", lambda self: None)
    svc = KubernetesService.__new__(KubernetesService)
    from app.core.config import get_settings
    svc._settings = get_settings()
    svc._settings.kube_namespace_allowlist = "default,app"
    svc._settings.enable_mutations = True
    return svc


def test_namespace_allowlist_blocks(service):
    with pytest.raises(PermissionError):
        service._check_namespace("kube-system")


def test_namespace_allowlist_allows(service):
    service._check_namespace("app")  # should not raise


def test_mutations_disabled(service):
    service._settings.enable_mutations = False
    with pytest.raises(PermissionError):
        service._check_mutations_enabled()
