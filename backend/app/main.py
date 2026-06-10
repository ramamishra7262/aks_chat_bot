"""
FastAPI application entrypoint for the AKS Copilot chatbot backend.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, health
from app.core.config import get_settings

settings = get_settings()

logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="AKS Copilot",
    description="Chatbot that troubleshoots AKS clusters and manages Kubernetes objects via Azure OpenAI tool calling.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)


@app.get("/")
def root():
    return {
        "name": "AKS Copilot",
        "docs": "/docs",
        "health": "/healthz",
        "chat": "/api/chat/stream",
    }
