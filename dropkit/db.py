"""SQLite persistence. One file, no server."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    supplier_sku TEXT,
    data TEXT NOT NULL,              -- SupplierProduct JSON
    last_price REAL,
    last_checked REAL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    marketplace TEXT NOT NULL,
    sku TEXT NOT NULL UNIQUE,         -- our inventory SKU on eBay
    content TEXT,                     -- ListingContent JSON
    price REAL,
    quantity INTEGER DEFAULT 0,
    category_id TEXT,
    offer_id TEXT,
    ebay_listing_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',  -- draft | published | paused | ended | blocked
    vero_flags TEXT,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ebay_order_id TEXT NOT NULL UNIQUE,
    sku TEXT,
    quantity INTEGER,
    sale_total REAL,
    buyer_name TEXT,
    ship_to TEXT,                     -- JSON address
    status TEXT NOT NULL DEFAULT 'new',  -- new | ordered | manual | shipped | error | cancelled
    supplier_order_id TEXT,
    tracking_number TEXT,
    carrier TEXT,
    note TEXT,
    raw TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at REAL
);
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    input TEXT NOT NULL,             -- scoring.CheckInput JSON
    result TEXT,                     -- scoring.ScoreResult JSON (NULL = candidate not scored yet)
    score INTEGER,
    source TEXT DEFAULT 'manual',    -- manual | research
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL
);
"""


class DB:
    def __init__(self, path: str = "dropkit.db"):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # --- events -------------------------------------------------------
    def log(self, kind: str, message: str) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO events (ts, kind, message) VALUES (?, ?, ?)", (time.time(), kind, message))

    def events(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    # --- tokens -------------------------------------------------------
    def set_token(self, name: str, value: str, expires_at: float | None) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO tokens (name, value, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value=excluded.value, expires_at=excluded.expires_at",
                (name, value, expires_at),
            )

    def get_token(self, name: str) -> tuple[str, float | None] | None:
        row = self.conn.execute("SELECT value, expires_at FROM tokens WHERE name = ?", (name,)).fetchone()
        return (row["value"], row["expires_at"]) if row else None

    # --- products -----------------------------------------------------
    def upsert_product(self, product: Any) -> int:
        data = product.model_dump_json()
        now = time.time()
        with self.tx() as c:
            c.execute(
                "INSERT INTO products (supplier, url, supplier_sku, data, last_price, last_checked, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET data=excluded.data, last_price=excluded.last_price, "
                "last_checked=excluded.last_checked, supplier_sku=excluded.supplier_sku",
                (product.supplier, product.url, product.supplier_sku, data, product.price, now, now),
            )
            row = c.execute("SELECT id FROM products WHERE url = ?", (product.url,)).fetchone()
        return int(row["id"])

    def product(self, product_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()

    def products(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()

    # --- listings -----------------------------------------------------
    def upsert_listing(self, **fields: Any) -> int:
        fields["updated_at"] = time.time()
        for key in ("content", "vero_flags"):
            if key in fields and not isinstance(fields[key], (str, type(None))):
                fields[key] = json.dumps(fields[key])
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        updates = ", ".join(f"{k}=excluded.{k}" for k in fields if k != "sku")
        with self.tx() as c:
            c.execute(
                f"INSERT INTO listings ({cols}) VALUES ({marks}) ON CONFLICT(sku) DO UPDATE SET {updates}",
                tuple(fields.values()),
            )
            row = c.execute("SELECT id FROM listings WHERE sku = ?", (fields["sku"],)).fetchone()
        return int(row["id"])

    def update_listing(self, sku: str, **fields: Any) -> None:
        fields["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.tx() as c:
            c.execute(f"UPDATE listings SET {sets} WHERE sku = ?", (*fields.values(), sku))

    def listing(self, sku: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM listings WHERE sku = ?", (sku,)).fetchone()

    def listings(self, status: str | None = None) -> list[sqlite3.Row]:
        if status:
            return self.conn.execute("SELECT * FROM listings WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
        return self.conn.execute("SELECT * FROM listings ORDER BY id DESC").fetchall()

    def count_published_since(self, since_ts: float) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE kind = 'publish' AND ts >= ?", (since_ts,)
        ).fetchone()
        return int(row["n"])

    # --- product checks -----------------------------------------------
    def save_check(self, name: str, input_json: str, result_json: str | None, score: int | None,
                   source: str = "manual", check_id: int | None = None) -> int:
        now = time.time()
        with self.tx() as c:
            if check_id:
                c.execute("UPDATE checks SET name=?, input=?, result=?, score=?, updated_at=? WHERE id=?",
                          (name, input_json, result_json, score, now, check_id))
                return check_id
            cur = c.execute(
                "INSERT INTO checks (name, input, result, score, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, input_json, result_json, score, source, now, now))
            return int(cur.lastrowid)

    def checks(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM checks ORDER BY (score IS NULL), score DESC, updated_at DESC").fetchall()

    def check(self, check_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()

    def delete_check(self, check_id: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM checks WHERE id = ?", (check_id,))

    # --- orders -------------------------------------------------------
    def insert_order(self, **fields: Any) -> bool:
        """Insert a new order. Returns False if it already exists."""
        now = time.time()
        fields.setdefault("created_at", now)
        fields["updated_at"] = now
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self.tx() as c:
            cur = c.execute(f"INSERT OR IGNORE INTO orders ({cols}) VALUES ({marks})", tuple(fields.values()))
        return cur.rowcount == 1

    def update_order(self, ebay_order_id: str, **fields: Any) -> None:
        fields["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.tx() as c:
            c.execute(f"UPDATE orders SET {sets} WHERE ebay_order_id = ?", (*fields.values(), ebay_order_id))

    def orders(self, status: str | None = None) -> list[sqlite3.Row]:
        if status:
            return self.conn.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
        return self.conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
