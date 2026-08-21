from __future__ import annotations

import logging
import os
import socket
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator
from urllib.parse import urlparse

import httpx

from core.settings import settings

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return bool(
        settings.use_langfuse
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


def _load_env() -> None:
    """Configure the SDK before its first import/initialization."""
    values = {
        "LANGFUSE_PUBLIC_KEY": settings.langfuse_public_key,
        "LANGFUSE_SECRET_KEY": settings.langfuse_secret_key,
        "LANGFUSE_BASE_URL": settings.langfuse_base_url,
        "LANGFUSE_TRACING_ENVIRONMENT": settings.langfuse_tracing_environment,
        "LANGFUSE_SAMPLE_RATE": str(settings.langfuse_sample_rate),
    }
    for key, value in values.items():
        if value:
            os.environ.setdefault(key, value)


@lru_cache(maxsize=1)
def get_langfuse_client() -> Any | None:
    if not _enabled():
        return None
    _load_env()
    try:
        from langfuse import get_client
    except ImportError as exc:
        raise RuntimeError(
            "USE_LANGFUSE is enabled, but the langfuse package is not installed."
        ) from exc
    return get_client()


@lru_cache(maxsize=1)
def get_langfuse_handler() -> Any | None:
    if not _enabled():
        return None
    _load_env()
    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


def langchain_config(
    run_name: str,
    *,
    metadata: dict[str, Any] | None = None,
    recursion_limit: int | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {"run_name": run_name}
    handler = get_langfuse_handler()
    if handler is not None:
        config["callbacks"] = [handler]
    if metadata:
        config["metadata"] = metadata
    if recursion_limit is not None:
        config["recursion_limit"] = recursion_limit
    return config


class _NoopObservation:
    def update(self, **_: Any) -> None:
        return None


@contextmanager
def trace_scope(
    name: str,
    *,
    input: Any = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    as_type: str = "chain",
) -> Iterator[Any]:
    """Create one searchable trace while preserving a no-op disabled path."""
    client = get_langfuse_client()
    if client is None:
        yield _NoopObservation()
        return

    from langfuse import propagate_attributes

    with propagate_attributes(
        trace_name=name,
        session_id=session_id,
        tags=tags or [],
        metadata=metadata or {},
    ):
        with client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=input,
            metadata=metadata,
        ) as observation:
            yield observation


def verify_connection() -> None:
    """Fail startup early only when tracing was explicitly enabled."""
    if not settings.use_langfuse:
        logger.info("Langfuse tracing is disabled.")
        return
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        raise RuntimeError(
            "USE_LANGFUSE=true requires LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY."
        )

    client = get_langfuse_client()
    host = urlparse(settings.langfuse_base_url).hostname
    if not host:
        raise RuntimeError("LANGFUSE_BASE_URL must be a valid HTTP(S) URL.")
    try:
        socket.getaddrinfo(host, None)
        response = httpx.get(
            f"{settings.langfuse_base_url.rstrip('/')}/api/public/health", timeout=5.0
        )
        response.raise_for_status()
    except (OSError, httpx.HTTPError) as exc:
        raise RuntimeError(
            f"Langfuse is enabled but {settings.langfuse_base_url} is unreachable: {exc}"
        ) from exc
    try:
        if not client.auth_check():
            raise RuntimeError("Langfuse rejected the configured credentials.")
    except Exception as exc:
        raise RuntimeError(f"Langfuse credential verification failed: {exc}") from exc
    logger.info("Langfuse tracing is connected (%s).", settings.langfuse_tracing_environment)


def flush() -> None:
    client = get_langfuse_client()
    if client is not None:
        client.flush()
