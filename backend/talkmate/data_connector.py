"""Data Connector с диаграммы компонентов: подключение к БД и выдача сессий."""
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def make_engine(url):
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url == "sqlite://":
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _fk(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


class DataConnector:
    def __init__(self, url):
        self.engine = make_engine(url)
        self._sessionmaker = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_schema(self):
        Base.metadata.create_all(self.engine)
        self._add_missing_columns()

    def _add_missing_columns(self):
        """Простая миграция: столбцы, которые появились в моделях позже, добавляются в уже существующие таблицы."""
        inspector = inspect(self.engine)
        with self.engine.begin() as connection:
            for table in Base.metadata.sorted_tables:
                existing = {column["name"] for column in inspector.get_columns(table.name)}
                for column in table.columns:
                    if column.name not in existing and column.nullable:
                        column_type = column.type.compile(self.engine.dialect)
                        connection.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type}"))

    def session(self):
        return self._sessionmaker()
