import copy
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, PROJECT_DIR, listen_for_sqlite_foreign_keys
from app.demo_limits import SlidingWindowLimiter, client_address
from app.invoice_processing import process_invoice
from app.reference_data import seed_reference_data

logger = logging.getLogger("invoiceflow.demo")

DEMO_STATIC_DIR = PROJECT_DIR / "static" / "demo"
SAMPLE_IDS = ("valid", "quantity-mismatch", "price-mismatch")

SAMPLES = {
    "valid": {
        "file_name": "valid_invoice.json",
        "title": "Clean invoice",
        "scenario": (
            "INV-1001 bills Northstar Office Supply purchase order PO-1001 "
            "for the ordered quantities and unit prices."
        ),
    },
    "quantity-mismatch": {
        "file_name": "quantity_mismatch.json",
        "title": "Quantity mismatch",
        "scenario": (
            "INV-1003 bills 5 units of toner. PO-1001 ordered 6. "
            "The invoice line totals agree with its own quantities and prices."
        ),
    },
    "price-mismatch": {
        "file_name": "price_mismatch.json",
        "title": "Unit price mismatch",
        "scenario": (
            "INV-1002 bills paper at a higher unit price than PO-1001. "
            "The invoice line totals agree with its own quantities and prices."
        ),
    },
}

SECURITY_HEADERS = (
    ("x-content-type-options", "nosniff"),
    ("referrer-policy", "no-referrer"),
    ("x-frame-options", "DENY"),
    (
        "content-security-policy",
        "default-src 'none'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'none'; "
        "connect-src 'self'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'; "
        "frame-src 'none'",
    ),
)

DEFAULT_RATE_LIMIT = 30
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_MAX_BODY_BYTES = 256
DEFAULT_MAX_LIMIT_KEYS = 4096


class ExampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: Literal["valid", "quantity-mismatch", "price-mismatch"] = Field(
        ...,
        description="Allowlisted synthetic example.",
    )


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.error("Invalid %s; using the default.", name)
        return default
    if value < minimum or value > maximum:
        logger.error("Invalid %s; using the default.", name)
        return default
    return value


def public_link(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if candidate == "":
        return None
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or parsed.netloc == "":
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return candidate


def create_memory_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    listen_for_sqlite_foreign_keys(engine)
    return engine


def load_sample_invoice(project_dir: Path, file_name: str) -> dict:
    path = project_dir / "fixtures" / "invoices" / file_name
    with path.open(encoding="utf-8") as file:
        invoice = json.load(file)
    if not isinstance(invoice, dict):
        raise ValueError("Sample invoice fixture is not an object.")
    return invoice


def initialize_demo(project_dir: Path) -> tuple[object, dict]:
    engine = create_memory_engine()
    Base.metadata.create_all(engine)
    results = {}

    with Session(engine) as session:
        seed_reference_data(session, project_dir, echo=False)
        session.commit()
        for sample_id in SAMPLE_IDS:
            invoice = load_sample_invoice(
                project_dir,
                SAMPLES[sample_id]["file_name"],
            )
            results[sample_id] = process_invoice(session, invoice)

    return engine, results


async def read_bounded_body(receive, max_bytes: int) -> tuple[bytes, bool]:
    chunks = []
    kept = 0

    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return b"", False
        if message["type"] != "http.request":
            continue

        data = message.get("body", b"")
        room = max_bytes + 1 - kept
        if room <= 0 or len(data) > room:
            return b"", True

        if data:
            chunks.append(data)
            kept += len(data)

        if kept > max_bytes:
            return b"", True
        if not message.get("more_body", False):
            return b"".join(chunks), False


def _declared_content_length(scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            return int(value.decode("ascii"))
        except (UnicodeError, ValueError):
            return None
    return None


def _error(status_code: int, detail: str, code: str, headers: dict | None = None):
    response = JSONResponse(
        status_code=status_code,
        content={"detail": detail, "code": code},
        headers=headers,
    )
    response.headers["cache-control"] = "no-store"
    return response


def _validation_response(exc: RequestValidationError):
    errors = exc.errors()
    if any(error.get("type") == "extra_forbidden" for error in errors):
        return _error(
            422,
            "The demo only accepts a sample id.",
            "UNEXPECTED_FIELD",
        )

    sample_errors = [
        error for error in errors if error.get("loc") == ("body", "sample_id")
    ]
    if sample_errors:
        if any(error.get("type") == "missing" for error in sample_errors):
            return _error(422, "A sample id is required.", "INVALID_REQUEST")
        return _error(422, "Unknown sample id.", "UNKNOWN_SAMPLE")

    return _error(
        422,
        "The request is not a supported sample.",
        "INVALID_REQUEST",
    )


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                for name, value in SECURITY_HEADERS:
                    encoded_name = name.encode("ascii")
                    if encoded_name.lower() not in present:
                        headers.append((encoded_name, value.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class DemoGuardMiddleware:
    """Rate-limit and body-cap the one demo action."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        if scope.get("path") != "/api/examples":
            await self.app(scope, receive, send)
            return

        app = scope.get("app")
        app_state = getattr(app, "state", None)
        limiter = getattr(app_state, "limiter", None)
        max_body = getattr(app_state, "max_body_bytes", DEFAULT_MAX_BODY_BYTES)

        if limiter is not None:
            allowed, retry_after = limiter.check(client_address(scope))
            if not allowed:
                response = _error(
                    429,
                    "Too many requests. Try again later.",
                    "RATE_LIMITED",
                    headers={"retry-after": str(retry_after)},
                )
                await response(scope, receive, send)
                return

        declared = _declared_content_length(scope)
        if declared is not None and declared > max_body:
            response = _error(
                413,
                "Request body is too large.",
                "PAYLOAD_TOO_LARGE",
            )
            await response(scope, receive, send)
            return

        body, too_large = await read_bounded_body(receive, max_body)
        if too_large:
            response = _error(
                413,
                "Request body is too large.",
                "PAYLOAD_TOO_LARGE",
            )
            await response(scope, receive, send)
            return

        sent = False

        async def replay_receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)


_UNSET = object()


def create_app(
    *,
    project_dir: Path = PROJECT_DIR,
    rate_limit_per_minute: int | None = None,
    window_seconds: int | None = None,
    max_body_bytes: int | None = None,
    max_limit_keys: int = DEFAULT_MAX_LIMIT_KEYS,
    source_url: str | None | object = _UNSET,
    walkthrough_url: str | None | object = _UNSET,
    contact_url: str | None | object = _UNSET,
) -> FastAPI:
    if rate_limit_per_minute is None:
        rate_limit_per_minute = _env_int(
            "DEMO_RATE_LIMIT_PER_MINUTE",
            DEFAULT_RATE_LIMIT,
            1,
            600,
        )
    if window_seconds is None:
        window_seconds = _env_int(
            "DEMO_RATE_LIMIT_WINDOW_SECONDS",
            DEFAULT_WINDOW_SECONDS,
            1,
            3600,
        )
    if max_body_bytes is None:
        max_body_bytes = _env_int(
            "DEMO_MAX_BODY_BYTES",
            DEFAULT_MAX_BODY_BYTES,
            64,
            4096,
        )

    if source_url is _UNSET:
        source_url = os.environ.get("DEMO_SOURCE_URL")
    if walkthrough_url is _UNSET:
        walkthrough_url = os.environ.get("DEMO_WALKTHROUGH_URL")
    if contact_url is _UNSET:
        contact_url = os.environ.get("DEMO_CONTACT_URL")

    links = {
        "source_url": public_link(source_url),
        "walkthrough_url": public_link(walkthrough_url),
        "contact_url": public_link(contact_url),
    }

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            engine, results = initialize_demo(project_dir)
            app.state.engine = engine
            app.state.results = results
            app.state.ready = True
        except Exception as exc:
            app.state.engine = None
            app.state.results = {}
            app.state.ready = False
            logger.error(
                "Demo initialization failed: %s",
                exc.__class__.__name__,
            )
        yield

    app = FastAPI(
        title="InvoiceFlow demo",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.ready = False
    app.state.results = {}
    app.state.engine = None
    app.state.project_dir = project_dir
    app.state.max_body_bytes = max_body_bytes
    app.state.links = links
    app.state.limiter = SlidingWindowLimiter(
        limit=rate_limit_per_minute,
        window_seconds=window_seconds,
        max_keys=max_limit_keys,
    )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        return _validation_response(exc)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.error("Demo request failed: %s", exc.__class__.__name__)
        return _error(
            500,
            "The demo could not complete that request.",
            "SERVER_ERROR",
        )

    @app.get("/health")
    def health(request: Request):
        if request.app.state.ready:
            return JSONResponse(
                status_code=200,
                content={"status": "ok", "demo_initialized": True},
                headers={"cache-control": "no-store"},
            )
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "demo_initialized": False},
            headers={"cache-control": "no-store"},
        )

    @app.get("/api/config")
    def demo_config(request: Request):
        return JSONResponse(
            content=request.app.state.links,
            headers={"cache-control": "no-store"},
        )

    @app.post("/api/examples")
    def run_example(example: ExampleRequest, request: Request):
        if not request.app.state.ready:
            return _error(
                503,
                "The demo is unavailable.",
                "UNAVAILABLE",
            )

        sample_id = example.sample_id
        cached = request.app.state.results.get(sample_id)
        if cached is None:
            return _error(422, "Unknown sample id.", "UNKNOWN_SAMPLE")

        sample = SAMPLES[sample_id]
        return JSONResponse(
            content={
                "sample_id": sample_id,
                "title": sample["title"],
                "scenario": sample["scenario"],
                "computed_at_startup": True,
                "processing_result": copy.deepcopy(cached),
            },
            headers={"cache-control": "no-store"},
        )

    @app.get("/")
    def serve_demo():
        return FileResponse(DEMO_STATIC_DIR / "index.html")

    app.mount(
        "/static",
        StaticFiles(directory=DEMO_STATIC_DIR),
        name="demo-static",
    )
    app.add_middleware(DemoGuardMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    return app


app = create_app()
