"""Pure-ASGI middleware: security headers and request IDs.

Implemented at the ASGI layer (not BaseHTTPMiddleware) so streaming SSE
responses pass through without buffering.
"""
from __future__ import annotations

import contextvars
import logging
import uuid

# Exposed so log filters/handlers can annotate records with the request id.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]


class SecurityHeadersMiddleware:
    """Append standard security headers to every HTTP response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                for key, value in _SECURITY_HEADERS:
                    if key not in existing:
                        headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RequestIDMiddleware:
    """Attach a request ID to every request: honoured from X-Request-ID or
    generated, stored in a contextvar for logging, echoed in the response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers", [])).get(b"x-request-id")
        request_id = incoming.decode("latin-1") if incoming else uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


class RateLimitMiddleware:
    """Fixed-window per-IP rate limiting for the expensive endpoints.

    Buckets by path prefix: chat (LLM cost), uploads (parsing cost), and
    computation/search. In-memory — suitable for the single-instance
    self-hosted deployment this app targets.
    """

    def __init__(
        self,
        app,
        *,
        enabled: bool = True,
        chat_per_minute: int = 20,
        upload_per_minute: int = 10,
        compute_per_minute: int = 60,
    ):
        self.app = app
        self.enabled = enabled
        self._buckets = {
            "/api/v1/chat": ("chat", chat_per_minute),
            "/api/v1/documents": ("upload", upload_per_minute),
            "/api/v1/tax": ("compute", compute_per_minute),
            "/api/v1/knowledge": ("compute", compute_per_minute),
        }
        # (ip, bucket) -> [window_start_epoch_minute, count]
        self._counters: dict[tuple[str, str], list[int]] = {}

    def _bucket_for(self, path: str) -> tuple[str, int] | None:
        for prefix, bucket in self._buckets.items():
            if path.startswith(prefix):
                return bucket
        return None

    @staticmethod
    def _client_ip(scope) -> str:
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for")
        if forwarded:
            return forwarded.decode("latin-1").split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"

    async def __call__(self, scope, receive, send):
        if not self.enabled or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        bucket = self._bucket_for(scope.get("path", ""))
        if bucket is None:
            await self.app(scope, receive, send)
            return

        bucket_name, limit = bucket
        import time

        minute = int(time.time() // 60)
        key = (self._client_ip(scope), bucket_name)
        counter = self._counters.get(key)
        if counter is None or counter[0] != minute:
            counter = [minute, 0]
            self._counters[key] = counter
        counter[1] += 1

        # Opportunistic pruning of stale windows
        if len(self._counters) > 10_000:
            self._counters = {
                k: v for k, v in self._counters.items() if v[0] == minute
            }

        if counter[1] > limit:
            retry_after = str(60 - int(time.time() % 60))
            body = (
                b'{"detail": "Rate limit exceeded. Please slow down and try again."}'
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", retry_after.encode("latin-1")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


class RequestIDLogFilter(logging.Filter):
    """Inject the current request id into log records as %(request_id)s."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging with request-id-aware formatting (idempotent)."""
    root = logging.getLogger()
    if any(isinstance(f, RequestIDLogFilter) for h in root.handlers for f in h.filters):
        return
    handler = logging.StreamHandler()
    handler.addFilter(RequestIDLogFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        )
    )
    root.addHandler(handler)
    root.setLevel(level)
