"""
Enterprise Autopilot — Database Connection Singleton.
Uses the shared connection pool from db.connection for efficiency.
"""
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from db.connection import get_conn


def get_connection():
    """Return a connection from the shared pool (use as context manager)."""
    return get_conn()


def execute_query(query: str, fetch: bool = True) -> dict:
    """Execute a SQL query using the connection pool and return results."""
    try:
        with get_conn() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            rows = []
            if fetch and cursor.description:
                rows = cursor.fetchall()
            row_count = cursor.rowcount
        return {"success": True, "rowCount": row_count, "data": rows}
    except Exception as e:
        return {"success": False, "error": str(e)}
