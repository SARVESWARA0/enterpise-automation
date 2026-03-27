"""
Database connection pool using psycopg2.
Call init_db() once at FastAPI startup.
"""
import psycopg2
from psycopg2 import pool
import os
from contextlib import contextmanager

_pool: pool.SimpleConnectionPool = None


def init_db():
    """Initialize the connection pool. Call once at app startup."""
    global _pool
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("DB_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL or DB_URL environment variable is required")
    # Strip surrounding quotes if present
    dsn = dsn.strip().strip('"').strip("'")
    _pool = pool.SimpleConnectionPool(minconn=1, maxconn=10, dsn=dsn)
    print(f"[DB] Connected to PostgreSQL (pool: 1-10 connections)")


@contextmanager
def get_conn():
    """Context manager for a connection from the pool."""
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
