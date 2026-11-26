"""MySQL connection helpers and transaction management."""

from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error as MySQLError

from .config import Config


def connect():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        autocommit=False,
    )


@contextmanager
def connection():
    """Yield a connection, COMMIT on success and ROLLBACK on any error."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def transaction():
    """Explicit transaction context used by money-changing operations."""
    conn = connect()
    try:
        conn.start_transaction()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def cursor(conn, dictionary=True):
    cur = conn.cursor(dictionary=dictionary)
    try:
        yield cur
    finally:
        cur.close()


def fetch_all(sql, params=None):
    with connection() as conn, cursor(conn) as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def fetch_one(sql, params=None):
    with connection() as conn, cursor(conn) as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql, params=None):
    """Execute a single statement and return the generated id / row count."""
    with connection() as conn, cursor(conn, dictionary=False) as cur:
        cur.execute(sql, params or ())
        last_id = cur.lastrowid
        rowcount = cur.rowcount
    return last_id, rowcount


__all__ = [
    "MySQLError",
    "connect",
    "connection",
    "transaction",
    "cursor",
    "fetch_all",
    "fetch_one",
    "execute",
]
