"""
Health and readiness endpoints used by AKS liveness/readiness probes and CI smoke tests.
"""
from fastapi import APIRouter

from app.core.config import get_settings
from app.models.schemas import HealthStatus
from app.services.kubernetes_service import get_kubernetes_service

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthStatus)
def healthz() -> HealthStatus:
    settings = get_settings()
    k8s_connected = False
    try:
        get_kubernetes_service().get_nodes()
        k8s_connected = True
    except Exception:  # noqa: BLE001
        k8s_connected = False

    return HealthStatus(
        status="ok",
        kubernetes_connected=k8s_connected,
        azure_openai_configured=bool(settings.azure_openai_endpoint and settings.azure_openai_api_key),
        azure_search_configured=bool(settings.azure_search_endpoint and settings.azure_search_api_key),
    )


@router.get("/readyz")
def readyz() -> dict:
    return {"status": "ready"}
