"""Parse SQLite data types."""

from __future__ import annotations

import sqlalchemy.types as sat
from sqlalchemy.dialects import sqlite

import ibis.expr.datatypes as dt
from ibis.backends.base.sql.alchemy.datatypes import AlchemyType


def parse(text: str) -> dt.DataType:
    """Parse `text` into an ibis data type."""
    text = text.strip().upper()

    # SQLite affinity rules
    # (see https://www.sqlite.org/datatype3.html).

    # 1. If the declared type contains the string "INT" then it is
    # assigned INTEGER affinity.
    if "INT" in text:
        return dt.int64

    # 2. If the declared type of the column contains any of the
    # strings "CHAR", "CLOB", or "TEXT" then that column has TEXT
    # affinity. Notice that the type VARCHAR contains the string
    # "CHAR" and is thus assigned TEXT affinity.
    if "CHAR" in text or "CLOB" in text or "TEXT" in text:
        return dt.string

    # 3. If the declared type for a column contains the string "BLOB"
    # or if no type is specified then the column has affinity BLOB.
    if not text or "BLOB" in text:
        return dt.binary

    # 4. If the declared type for a column contains any of the strings
    # "REAL", "FLOA", or "DOUB" then the column has REAL affinity.
    if "REAL" in text or "FLOA" in text or "DOUB" in text:
        return dt.float64

    # 5. Otherwise, the affinity is NUMERIC.
    return dt.decimal


class SqliteType(AlchemyType):
    @classmethod
    def from_ibis(cls, dtype: dt.DataType) -> sat.TypeEngine:
        if dtype.is_floating():
            return sat.REAL
        else:
            return super().from_ibis(dtype)

    @classmethod
    def to_ibis(cls, typ: sat.TypeEngine, nullable: bool = True) -> dt.DataType:
        if isinstance(typ, sat.REAL):
            return dt.Float64(nullable=nullable)
        elif isinstance(typ, sqlite.JSON):
            return dt.JSON(nullable=nullable)
        else:
            return super().to_ibis(typ, nullable=nullable)
