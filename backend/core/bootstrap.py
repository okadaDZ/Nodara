from __future__ import annotations

import logging
import sys


def bootstrap() -> None:
    """Configure logging and validate settings before the app boots.

    A basic ERROR-level logger is configured first so any failure loading
    settings surfaces as a clean log line rather than a raw traceback.
    Once settings load successfully, the root logger is tuned to the configured LOG_LEVEL.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    try:
        from core.settings import settings
    except Exception as exc:
        logging.getLogger("startup").error(
            "Failed to load application settings: %s", exc
        )
        sys.exit(1)

    logging.getLogger().setLevel(settings.default_log_level)

    if not settings.api_auth_token:
        logging.getLogger("startup").info(
            "API auth token is not set. /api/v1 auth is open for local development."
        )
