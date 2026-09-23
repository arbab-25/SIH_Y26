"""Redis connection + tiny cache and job-queue helpers.

Design notes (Phase 2):
- REDIS_URL is OPTIONAL. When unset (local dev, Render free tier without an
  addon) every helper degrades to a no-op and the app behaves exactly as
  before — scans run as FastAPI background tasks, rule lookups hit Postgres.
- When REDIS_URL IS set, the queue becomes RQ (Redis Queue): scan jobs run in
  a separate worker process, so a 30-second OCR never occupies the API's
  event loop. Valkey 7 (open source, Redis-compatible) or Upstash's free
  Redis REST/tcp endpoint both work — anything speaking the RESP protocol.
- Caching uses plain GET/SET with a namespace prefix; no extra dependency
  beyond `redis` (which RQ already requires).
"""

from typing import Optional, Any, Tuple, cast
import json

from app.config import settings

_pool = None
_available: Optional[bool] = None

CACHE_PREFIX = "codemaze:cache:"
CACHE_TTL_SECONDS = 3600


def _get_pool():
    """Lazily create the connection pool; returns None when Redis is unconfigured."""
    global _pool
    if _pool is not None:
        return _pool
    url = settings.REDIS_URL
    if not url:
        return None
    import redis

    _pool = redis.ConnectionPool.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    return _pool


def redis_available() -> bool:
    """True when REDIS_URL is set AND a PING succeeds (cached after first try)."""
    global _available
    if _available is not None:
        return _available
    pool = _get_pool()
    if pool is None:
        _available = False
        return False
    try:
        import redis

        client = redis.Redis(connection_pool=pool)
        _available = bool(client.ping())
    except Exception as exc:
        print(f"[WARN] Redis unavailable ({type(exc).__name__}); continuing without it.")
        _available = False
    return _available


def reset_redis_state() -> None:
    """Testing hook: forget the cached availability/pool."""
    global _pool, _available
    _pool = None
    _available = None


# --------------------------------------------------------------------- cache
def cache_get(key: str) -> Optional[Any]:
    """Namespaced GET; returns None on miss or when Redis is down."""
    if not redis_available():
        return None
    try:
        import redis

        client = redis.Redis(connection_pool=_get_pool())
        raw = client.get(CACHE_PREFIX + key)
        if raw is None:
            return None
        # redis-py's sync client may hand back bytes; json.loads wants str.
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        return json.loads(cast(str, text))
    except Exception as exc:
        print(f"[WARN] cache_get failed: {type(exc).__name__}")
        return None


def cache_set(key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> bool:
    """Namespaced SETEX; silently no-ops without Redis. Returns success."""
    if not redis_available():
        return False
    try:
        import redis

        client = redis.Redis(connection_pool=_get_pool())
        client.setex(CACHE_PREFIX + key, ttl, json.dumps(value, default=str))
        return True
    except Exception as exc:
        print(f"[WARN] cache_set failed: {type(exc).__name__}")
        return False


def cache_delete_prefix(prefix: str) -> int:
    """Invalidate every cache key starting with prefix. Returns count deleted."""
    if not redis_available():
        return 0
    try:
        import redis

        client = redis.Redis(connection_pool=_get_pool())
        pattern = CACHE_PREFIX + prefix + "*"
        deleted = 0
        cursor = 0
        while True:
            scan_result: Tuple[int, list] = cast(
                Tuple[int, list], client.scan(cursor=cursor, match=pattern, count=100)
            )
            cursor = int(scan_result[0])
            keys = list(scan_result[1])
            if keys:
                deleted += cast(int, client.delete(*keys))
            if cursor == 0:
                break
        return deleted
    except Exception as exc:
        print(f"[WARN] cache_delete_prefix failed: {type(exc).__name__}")
        return 0


# ------------------------------------------------------------------- enqueue
def enqueue_scan_job(scan_id: str, payload: dict) -> Optional[str]:
    """Submit the scan-processing job to RQ; returns a job id or None.

    Returns None when Redis/RQ is unavailable — callers then fall back to the
    in-process FastAPI background task, so behaviour never regresses.
    """
    if not redis_available():
        return None
    try:
        from redis import Redis
        from rq import Queue

        queue = Queue(
            "scans",
            connection=Redis(connection_pool=_get_pool()),
            default_timeout=600,
        )
        job = queue.enqueue(
            "app.worker.process_scan_job",
            scan_id,
            payload,
            job_id=f"scan-{scan_id}",
            meta={"enqueued_at_payload": payload},
        )
        return job.get_id()
    except Exception as exc:
        print(f"[WARN] RQ enqueue failed ({type(exc).__name__}); using in-process fallback.")
        return None


def fetch_job_status(job_id: str) -> Optional[dict]:
    """Read an RQ job's status; None when RQ/Redis is unavailable or unknown id."""
    if not redis_available():
        return None
    try:
        from redis import Redis
        from rq.job import Job
        from rq.exceptions import NoSuchJobError

        try:
            job = Job.fetch(job_id, connection=Redis(connection_pool=_get_pool()))
        except NoSuchJobError:
            return None
        return {
            "job_id": job.get_id(),
            "status": job.get_status(),  # queued | started | finished | failed
            "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        }
    except Exception as exc:
        print(f"[WARN] fetch_job_status failed: {type(exc).__name__}")
        return None
