from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from knowgraph.agent import Investigator
from knowgraph.config import settings
from knowgraph.db import check_connection, connect
from knowgraph.models import ChatRequest, ChatResponse
from knowgraph.ollama import OllamaClient


class HealthResponse(BaseModel):
    status: str
    graph_available: bool
    ollama_available: bool
    model: str


def create_app(graph_factory=connect, ollama_factory=OllamaClient) -> FastAPI:
    app = FastAPI(title="KnowGraph AI", version="0.2.0")

    @app.get("/health", response_model=HealthResponse)
    def health():
        try:
            graph_available = check_connection(graph_factory())
        except Exception:
            graph_available = False
        try:
            ollama_available = ollama_factory().available()
        except Exception:
            ollama_available = False
        return HealthResponse(
            status="ready" if graph_available and ollama_available else "degraded",
            graph_available=graph_available,
            ollama_available=ollama_available,
            model=settings.ollama_model,
        )

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest):
        try:
            graph = graph_factory()
            if not check_connection(graph):
                raise HTTPException(status_code=503, detail="Graph database is unavailable")
        except HTTPException:
            raise
        except Exception as exc:
            # Avoid disclosing database endpoints, credentials, or provider internals.
            raise HTTPException(status_code=503, detail="Graph database is unavailable") from exc
        try:
            ollama = ollama_factory()
            if not ollama.available():
                raise HTTPException(status_code=503, detail="Configured local Ollama model is unavailable")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Configured local Ollama model is unavailable") from exc
        try:
            return Investigator(graph, ollama).investigate(request.question)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Investigation is temporarily unavailable") from exc

    return app


app = create_app()
