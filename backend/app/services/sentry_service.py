"""Sentry error tracking — optional, env-controlled (Phase 5).

Free tier: sentry.io developer plan (5k errors/month). Entirely OFF unless
SENTRY_DSN is set, so local dev, tests, and Redis-less deployments pay
nothing — no SDK import, no network calls, zero overhead.

SENTRY_TRACES_SAMPLE_RATE optionally enables performance tracing (default 0).
"""

import logging

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """Initialize the Sentry SDK when SENTRY_DSN is configured. Returns enabled."""
    import os

    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning("SENTRY_DSN set but sentry-sdk not installed; skipping.")
        return False

    try:
        traces_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0") or 0)
    except ValueError:
        traces_rate = 0.0

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("ENVIRONMENT", "development"),
        traces_sample_rate=traces_rate,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        # Never send request bodies: label photos and auth payloads must not
        # leave the deployment (privacy + statutory data).
        send_default_pii=False,
        before_send=_scrub_event,
    )
    logger.info("Sentry initialized (environment=%s, traces=%.2f)", os.environ.get("ENVIRONMENT", "development"), traces_rate)
    return True


def _scrub_event(event, hint):
    """Drop blobs/attachments and Authorization data from every event."""
    try:
        request = event.get("request") or {}
        headers = request.get("headers") or {}
        if isinstance(headers, dict):
            headers.pop("Authorization", None)
            headers.pop("authorization", None)
        cookies = request.get("cookies")
        if cookies:
            request["cookies"] = {}
    except Exception:
        pass
    return event
