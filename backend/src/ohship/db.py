from collections.abc import Generator

from sqlmodel import Session, create_engine

from ohship.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"connect_timeout": 3},
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception:
        return False
