import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://rumbo:rumbo@localhost:5432/rumbo_test",
)
os.environ.setdefault("SESSION_SECRET", "test-session-secret-0123456789")
os.environ.setdefault("ENV", "test")

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from psycopg import connect  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

import app.models  # noqa: E402,F401  (registra las tablas en Base.metadata)
from app.api.deps import get_current_user  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(autouse=True)
def reset_rate_limit() -> Generator[None, None, None]:
    from app.api.rate_limit import clear_rate_limit

    clear_rate_limit()
    yield
    clear_rate_limit()


@pytest.fixture(scope="session")
def db_engine():
    settings = get_settings()
    url = make_url(settings.database_url)
    with connect(
        dbname="postgres",
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        autocommit=True,
    ) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone()
        if exists is None:
            conn.execute(f'CREATE DATABASE "{url.database}"')

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE external_cache, ai_requests, messages, "
                "conversations, ai_services, api_tokens, sessions, users, "
                "activities, destinations RESTART IDENTITY CASCADE"
            )
        )
    testing_session = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        email="admin-test@rumbo.ai",
        password_hash="not-used",
        full_name="Admin Test",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def regular_user(db_session: Session) -> User:
    user = User(
        email="user-test@rumbo.ai",
        password_hash="not-used",
        full_name="User Test",
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def as_admin(
    client: TestClient, admin_user: User
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def as_user(
    client: TestClient, regular_user: User
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_current_user] = lambda: regular_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)
