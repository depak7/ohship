import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from planlog.api.main import app
from planlog.auth import hash_api_key
from planlog.db import get_session
from planlog.models import Organization, User
from planlog.services.orgs import create_organization


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="user_and_key")
def user_and_key_fixture(session: Session) -> tuple[User, str, Organization]:
    key = "dl_test_integration_key"
    user = User(name="Alice", email="alice@test.com", api_key_hash=hash_api_key(key))
    session.add(user)
    session.commit()
    session.refresh(user)
    org = create_organization(session, "Acme", user)
    return user, key, org
