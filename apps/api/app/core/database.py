from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import get_settings
from app.models import Profile

settings = get_settings()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if session.exec(select(Profile).where(Profile.is_default)).first() is None:
            session.add(Profile())
            session.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
