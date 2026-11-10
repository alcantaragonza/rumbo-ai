from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Destination, User
from scripts.seed import seed


def test_seed_is_idempotent(db_session: Session) -> None:
    first = seed(db_session)
    second = seed(db_session)

    assert first == {
        "users": 2,
        "destinations": 2,
        "activities": 6,
        "services": 3,
        "embeddings": 8,
    }
    assert second == {
        "users": 0,
        "destinations": 0,
        "activities": 0,
        "services": 0,
        "embeddings": 0,
    }
    assert db_session.scalar(select(func.count()).select_from(User)) == 2
    assert db_session.scalar(select(func.count()).select_from(Destination)) == 2
    assert db_session.scalar(select(func.count()).select_from(Activity)) == 6
