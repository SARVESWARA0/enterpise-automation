"""
Enterprise Autopilot — Database Connection Singleton.
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", os.getenv("DB_URL", "postgresql://postgres:1234@localhost:5432/enterprise_autopilot"))


def get_connection():
    """Return a new psycopg2 connection."""
    return psycopg2.connect(DB_URL)


def execute_query(query: str, fetch: bool = True) -> dict:
    """Execute a SQL query and return results."""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query)
        rows = []
        if fetch and cursor.description:
            rows = cursor.fetchall()
        conn.commit()
        row_count = cursor.rowcount
        cursor.close()
        conn.close()
        return {"success": True, "rowCount": row_count, "data": rows}
    except Exception as e:
        return {"success": False, "error": str(e)}
