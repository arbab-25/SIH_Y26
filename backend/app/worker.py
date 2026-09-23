"""RQ worker entrypoint — processes scan jobs OUTSIDE the API process.

Run alongside the API when REDIS_URL is configured:

    rq worker scans --url $REDIS_URL          # CLI form, or
    python -m app.worker                      # this module

The job function mirrors app.api.scans._process_scan but works with a
synchronous database session (RQ workers are sync by nature). The result of
processing is written to the same scans row the polling endpoint reads, so
the client contract is unchanged: whichever side finishes the work, the scan
row carries the outcome.
"""

import asyncio
import os
import sys
import time


def process_scan_job(scan_id: str, payload: dict) -> dict:
    """RQ entry: run the async pipeline in a fresh event loop."""
    # Workers import the app package; make sure backend/ is importable.
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    from app.api.scans import process_scan_sync

    result = process_scan_sync(scan_id, payload)
    return result


if __name__ == "__main__":
    from redis import Redis
    from rq import Worker, Queue

    url = os.environ.get("REDIS_URL", "")
    if not url:
        print("REDIS_URL is not set; nothing to do.")
        sys.exit(1)

    listen = Queue("scans", connection=Redis.from_url(url))
    print(f"[OK] RQ worker listening on queue 'scans' ({url})")
    Worker([listen], connection=listen.connection).work()
