from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10)
SessionFactory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session() -> Session:
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
