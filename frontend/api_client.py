"""Small standard-library client for the local KnowGraph FastAPI service."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class APIError(RuntimeError):
    pass


def api_base_url() -> str:
    base_url = os.getenv("KNOWGRAPH_API_URL", "http://localhost:8000").rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise APIError("KNOWGRAPH_API_URL must point to a local address (localhost).")
    return base_url


def _request(path: str, method: str = "GET", payload: dict | None = None, timeout: float = 5.0) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        api_base_url() + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            detail = json.load(exc).get("detail", f"HTTP {exc.code}")
        except (ValueError, OSError):
            detail = f"HTTP {exc.code}"
        raise APIError(str(detail)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise APIError(f"Cannot reach the KnowGraph API at {api_base_url()}: {exc}") from exc
    except ValueError as exc:
        raise APIError("The KnowGraph API returned invalid JSON.") from exc


def get_health() -> dict:
    return _request("/health", timeout=3.0)


def ask(question: str) -> dict:
    return _request("/chat", method="POST", payload={"question": question}, timeout=180.0)
