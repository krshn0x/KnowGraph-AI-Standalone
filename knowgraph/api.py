import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from redis.exceptions import RedisError

from knowgraph.agent import Agent
from knowgraph.config import get_settings
from knowgraph.graph import GraphStore
from knowgraph.ingestion import ingest, parse_csv, parse_json
from knowgraph.models import (
    Answer,
    AskRequest,
    DocumentResult,
    Entity,
    Evidence,
    ExpertResult,
    ImportResult,
    Investigation,
    Kind,
)
from knowgraph.retrieval import NotFound, Retrieval

logger = logging.getLogger(__name__)
MAX_UPLOAD = 8 * 1024 * 1024


def create_app(store: GraphStore | None = None, agent: Agent | None = None) -> FastAPI:
    settings = get_settings()
    database = store or GraphStore(settings)
    retrieval = Retrieval(database)
    investigator = agent or Agent(retrieval, settings)

    @asynccontextmanager
    async def lifespan(app):
        try:
            database.initialize()
        except RedisError:
            logger.warning("Database unavailable during startup; health endpoint will report it.")
        yield
        if store is None:
            database.close()

    app = FastAPI(
        title="KnowGraph AI",
        version="0.1.0",
        lifespan=lifespan,
        description="Evidence-backed engineering knowledge on FalkorDB",
    )

    @app.exception_handler(RedisError)
    async def database_error(request: Request, exc: RedisError):
        logger.warning("Database request failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "FalkorDB is unavailable. Check database readiness and retry."},
        )

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        database.ping()
        counts = database.counts()
        return {
            "status": "ok",
            "database": "ready",
            "ai_configured": investigator.client is not None,
            "model": settings.openai_model,
            **counts,
        }

    @app.get("/entities", response_model=list[Entity])
    def entities(kind: Kind | None = None, q: str = Query(default="", max_length=500)):
        return database.search(q, [kind] if kind else None) if q else database.list_entities(kind)

    @app.get("/entities/{node_id:path}", response_model=Entity)
    def get_entity(node_id: str):
        node = database.get(node_id)
        if node is None:
            raise NotFound(f"Entity not found: {node_id}")
        return node

    @app.post("/ask", response_model=Answer)
    @app.post("/chat", response_model=Answer, include_in_schema=False, deprecated=True)
    def ask(request: AskRequest):
        database.ping()
        return investigator.ask(request)

    @app.get("/incidents/{incident_id:path}/investigation", response_model=Investigation)
    def incident(incident_id: str, lookback_hours: int = Query(default=24, ge=1, le=168)):
        return retrieval.investigate(incident_id, lookback_hours)

    @app.get("/experts", response_model=ExpertResult)
    def experts(q: str = Query(min_length=1, max_length=500)):
        return retrieval.experts(q)

    @app.get("/documents", response_model=DocumentResult)
    def documents(q: str = Query(min_length=1, max_length=500)):
        return retrieval.documents(q)

    @app.get("/graph/neighborhood", response_model=Evidence)
    def neighborhood(
        node_id: str = Query(min_length=1, max_length=200),
        hops: int = Query(default=1, ge=1, le=3),
        limit: int = Query(default=100, ge=1, le=100),
    ):
        if not database.get(node_id):
            raise NotFound(f"Entity not found: {node_id}")
        return database.neighborhood(node_id, hops, limit)

    @app.post("/ingest", response_model=ImportResult)
    def upload(
        bundle_file: UploadFile | None = File(default=None),
        nodes_file: UploadFile | None = File(default=None),
        edges_file: UploadFile | None = File(default=None),
    ):
        if (bundle_file is None) == (nodes_file is None and edges_file is None):
            raise HTTPException(422, "Supply a JSON bundle OR node/edge CSV files.")
        files = [bundle_file, nodes_file, edges_file]
        contents = [f.file.read(MAX_UPLOAD + 1) if f else None for f in files]
        if sum(len(c) for c in contents if c) > MAX_UPLOAD:
            raise HTTPException(413, "Upload exceeds the 8 MiB limit.")
        try:
            bundle = parse_json(contents[0]) if bundle_file else parse_csv(contents[1], contents[2])
        except (ValidationError, ValueError, UnicodeError, TypeError) as exc:
            raise HTTPException(422, f"Invalid upload: {str(exc)[:1500]}") from exc
        result = ingest(database, bundle)
        if result.rejected:
            return JSONResponse(status_code=422, content=result.model_dump())
        return result

    return app


app = create_app()
