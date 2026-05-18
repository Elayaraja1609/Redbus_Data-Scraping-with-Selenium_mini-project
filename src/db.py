from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator, Iterable, Optional

import pandas as pd

from src.config import (
    DATA_DIR,
    GOVERNMENT_BUS_KEYWORDS,
    MYSQL_CONFIG,
    SQL_DIR,
    SQLITE_PATH,
    USE_MYSQL,
)

INSERT_SQL = """
INSERT INTO bus_routes (
    route_name, route_link, busname, bustype,
    departing_time, duration, reaching_time,
    star_rating, price, seats_available, is_government
) VALUES (
    %(route_name)s, %(route_link)s, %(busname)s, %(bustype)s,
    %(departing_time)s, %(duration)s, %(reaching_time)s,
    %(star_rating)s, %(price)s, %(seats_available)s, %(is_government)s
)
"""

FILTER_QUERY = """
SELECT
    id, route_name, route_link, busname, bustype,
    departing_time, duration, reaching_time,
    star_rating, price, seats_available, is_government, scraped_at
FROM bus_routes
WHERE 1=1
"""


@dataclass
class BusFilters:
    route_names: Optional[list[str]] = None
    bustypes: Optional[list[str]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    min_seats: Optional[int] = None
    government_only: bool = False
    search_busname: Optional[str] = None


def is_government_bus(busname: str) -> bool:
    upper = (busname or "").upper()
    return any(kw.upper() in upper for kw in GOVERNMENT_BUS_KEYWORDS)


class Database:
    def __init__(self, use_mysql: Optional[bool] = None) -> None:
        self.use_mysql = USE_MYSQL if use_mysql is None else use_mysql

    @contextmanager
    def connect(self) -> Generator[Any, None, None]:
        if self.use_mysql:
            import mysql.connector

            conn = mysql.connector.connect(**MYSQL_CONFIG)
            try:
                yield conn
            finally:
                conn.close()
        else:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    def init_schema(self) -> None:
        if self.use_mysql:
            self._init_mysql()
        else:
            self._init_sqlite()

    def _init_mysql(self) -> None:
        import mysql.connector

        schema_path = SQL_DIR / "schema.sql"
        raw = schema_path.read_text(encoding="utf-8")
        statements = [s.strip() for s in raw.split(";") if s.strip()]
        base_config = {k: v for k, v in MYSQL_CONFIG.items() if k != "database"}
        conn = mysql.connector.connect(**base_config)
        cursor = conn.cursor()
        try:
            for stmt in statements:
                cursor.execute(stmt)
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        print(f"MySQL schema initialized ({MYSQL_CONFIG['database']})")

    def _init_sqlite(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(SQLITE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bus_routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route_name TEXT NOT NULL,
                route_link TEXT,
                busname TEXT NOT NULL,
                bustype TEXT,
                departing_time TEXT,
                duration TEXT,
                reaching_time TEXT,
                star_rating REAL,
                price REAL,
                seats_available INTEGER,
                is_government INTEGER DEFAULT 0,
                scraped_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_route_name ON bus_routes(route_name)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_price ON bus_routes(price)")
        conn.commit()
        conn.close()
        print(f"SQLite schema initialized at {SQLITE_PATH}")

    def insert_buses(self, records: Iterable[dict[str, Any]]) -> int:
        rows = []
        for rec in records:
            busname = rec.get("busname", "")
            rows.append(
                {
                    "route_name": rec["route_name"],
                    "route_link": rec.get("route_link"),
                    "busname": busname,
                    "bustype": rec.get("bustype"),
                    "departing_time": rec.get("departing_time"),
                    "duration": rec.get("duration"),
                    "reaching_time": rec.get("reaching_time"),
                    "star_rating": rec.get("star_rating"),
                    "price": rec.get("price"),
                    "seats_available": rec.get("seats_available"),
                    "is_government": int(
                        rec.get("is_government", is_government_bus(busname))
                    ),
                }
            )
        if not rows:
            return 0

        with self.connect() as conn:
            cursor = conn.cursor()
            if self.use_mysql:
                cursor.executemany(INSERT_SQL, rows)
            else:
                cursor.executemany(
                    """
                    INSERT INTO bus_routes (
                        route_name, route_link, busname, bustype,
                        departing_time, duration, reaching_time,
                        star_rating, price, seats_available, is_government
                    ) VALUES (
                        :route_name, :route_link, :busname, :bustype,
                        :departing_time, :duration, :reaching_time,
                        :star_rating, :price, :seats_available, :is_government
                    )
                    """,
                    rows,
                )
            conn.commit()
        return len(rows)

    def fetch_buses(self, filters: Optional[BusFilters] = None) -> pd.DataFrame:
        filters = filters or BusFilters()
        sql = FILTER_QUERY
        params: list[Any] = []

        if filters.route_names:
            placeholders = ",".join(["%s"] * len(filters.route_names))
            if not self.use_mysql:
                placeholders = ",".join(["?"] * len(filters.route_names))
            sql += f" AND route_name IN ({placeholders})"
            params.extend(filters.route_names)

        if filters.bustypes:
            placeholders = ",".join(["%s"] * len(filters.bustypes))
            if not self.use_mysql:
                placeholders = ",".join(["?"] * len(filters.bustypes))
            sql += f" AND bustype IN ({placeholders})"
            params.extend(filters.bustypes)

        if filters.min_price is not None:
            sql += " AND price >= %s" if self.use_mysql else " AND price >= ?"
            params.append(filters.min_price)

        if filters.max_price is not None:
            sql += " AND price <= %s" if self.use_mysql else " AND price <= ?"
            params.append(filters.max_price)

        if filters.min_rating is not None:
            sql += " AND star_rating >= %s" if self.use_mysql else " AND star_rating >= ?"
            params.append(filters.min_rating)

        if filters.min_seats is not None:
            sql += " AND seats_available >= %s" if self.use_mysql else " AND seats_available >= ?"
            params.append(filters.min_seats)

        if filters.government_only:
            sql += " AND is_government = 1"

        if filters.search_busname:
            pattern = f"%{filters.search_busname}%"
            sql += " AND busname LIKE %s" if self.use_mysql else " AND busname LIKE ?"
            params.append(pattern)

        sql += " ORDER BY route_name, price"

        with self.connect() as conn:
            if self.use_mysql:
                return pd.read_sql(sql, conn, params=params or None)
            return pd.read_sql(sql, conn, params=params)

    def get_distinct_values(self, column: str) -> list[str]:
        allowed = {"route_name", "bustype"}
        if column not in allowed:
            raise ValueError(f"Column not allowed: {column}")
        sql = f"SELECT DISTINCT {column} FROM bus_routes WHERE {column} IS NOT NULL ORDER BY {column}"
        with self.connect() as conn:
            df = pd.read_sql(sql, conn)
        return df[column].dropna().astype(str).tolist()

    def get_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            df = pd.read_sql("SELECT COUNT(*) AS total FROM bus_routes", conn)
            gov = pd.read_sql(
                "SELECT COUNT(*) AS gov_count FROM bus_routes WHERE is_government = 1",
                conn,
            )
            routes = pd.read_sql(
                "SELECT COUNT(DISTINCT route_name) AS route_count FROM bus_routes",
                conn,
            )
        return {
            "total_buses": int(df["total"].iloc[0]),
            "government_buses": int(gov["gov_count"].iloc[0]),
            "unique_routes": int(routes["route_count"].iloc[0]),
        }

    def clear_route(self, route_name: str) -> None:
        sql = "DELETE FROM bus_routes WHERE route_name = %s"
        if not self.use_mysql:
            sql = "DELETE FROM bus_routes WHERE route_name = ?"
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (route_name,))
            conn.commit()


def init_db() -> None:
    Database().init_schema()


if __name__ == "__main__":
    init_db()
