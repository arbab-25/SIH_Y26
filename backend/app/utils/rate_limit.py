import time
from typing import Dict, List
from fastapi import HTTPException, status

# In-memory store: key -> list of timestamps
_rate_limits: Dict[str, List[float]] = {}

def check_rate_limit(key: str, max_requests: int = 30, window_seconds: int = 60):
    """
    Check if the given key has exceeded the rate limit.
    Raises an HTTPException (429) if the limit is exceeded.
    """
    now = time.time()
    
    if key not in _rate_limits:
        _rate_limits[key] = []
        
    # Clean up timestamps older than the time window
    _rate_limits[key] = [ts for ts in _rate_limits[key] if now - ts < window_seconds]
    
    if len(_rate_limits[key]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later."
        )
        
    _rate_limits[key].append(now)
