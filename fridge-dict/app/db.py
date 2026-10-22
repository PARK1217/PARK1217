"""SQLite + SQLAlchemy 2.0. create_all만 쓰고 마이그레이션 도구는 두지 않는다."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import DB_PATH
from .models import Base

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _pragmas(conn, _record):
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# 기존 DB에 뒤늦게 추가된 컬럼. (테이블, 컬럼, DDL 타입과 기본값)
_ADDED_COLUMNS = (
    ("recipes", "spicy", "VARCHAR(10) DEFAULT ''"),
    ("meal_log", "recipe_id", "VARCHAR(80)"),
)


def init_db() -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table, col, ddl in _ADDED_COLUMNS:
            cols = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if cols and col not in cols:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
