from collections import defaultdict, deque
from time import monotonic
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models import User

WINDOW_SECONDS = 60
MAX_REQUESTS = 60

_HITS: dict[str, deque[float]] = defaultdict(deque)


def clear_rate_limit() -> None:
    _HITS.clear()


def rate_limit(user: Annotated[User, Depends(get_current_user)]) -> None:
    """Límite simple por usuario en memoria (una instancia)."""
    key = str(user.id)
    now = monotonic()
    hits = _HITS[key]
    while hits and hits[0] <= now - WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes; intenta más tarde",
        )
    hits.append(now)
