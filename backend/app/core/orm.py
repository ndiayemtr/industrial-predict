"""Shared ORM metadata, independent of application settings and SQL runtimes."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
