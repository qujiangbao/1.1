"""pgvector SQLAlchemy type with a dependency-light schema fallback."""
from __future__ import annotations

from typing import Any

try:
    from pgvector.sqlalchemy import Vector as Vector
except ModuleNotFoundError:
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):
        """Declare PostgreSQL VECTOR(n) when pgvector's Python package is absent.

        The application requirements still install the official package in the
        supported runtime. This fallback only keeps schema imports, offline
        migration generation, and database-disabled operation functional.
        """

        cache_ok = True

        def __init__(self, dimensions: int) -> None:
            self.dimensions = dimensions

        def get_col_spec(self, **kw: Any) -> str:
            return f"VECTOR({self.dimensions})"

        def bind_processor(self, dialect):
            def process(value):
                if value is None or isinstance(value, str):
                    return value
                return "[" + ",".join(str(float(item)) for item in value) + "]"

            return process
