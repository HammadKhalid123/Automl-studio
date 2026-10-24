from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

_attempts = defaultdict(deque)
_lock = Lock()


def check_auth_rate_limit(request: Request, action: str, limit: int = 8, window_seconds: int = 300):
    host = request.client.host if request.client else "unknown"
    key = (action, host)
    now = monotonic()
    with _lock:
        attempts = _attempts[key]
        while attempts and now - attempts[0] >= window_seconds:
            attempts.popleft()
        if len(attempts) >= limit:
            retry = max(1, int(window_seconds - (now - attempts[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry)},
            )
        attempts.append(now)
        if len(_attempts) > 10_000:
            cutoff = now - window_seconds
            for old_key in [item for item, queue in _attempts.items() if not queue or queue[-1] < cutoff]:
                _attempts.pop(old_key, None)
