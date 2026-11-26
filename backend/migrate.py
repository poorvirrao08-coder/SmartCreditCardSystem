"""Apply the SmartCard schema and sample data without destroying existing data."""

import argparse
from pathlib import Path

import mysql.connector

from .config import Config, BASE_DIR
from .security import hash_password

SQL_DIR = BASE_DIR / "sql"


def split_sql(text):
    statements = []
    for raw in text.split(";"):
        cleaned = "\n".join(
            line for line in raw.splitlines()
            if not line.strip().startswith("--")
        ).strip()
        if cleaned:
            statements.append(cleaned)
    return statements


def ensure_database():
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
    )
    try:
        cur = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DATABASE}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cur.close()
        conn.commit()
    finally:
        conn.close()


def ensure_additive_columns(conn):
    """Add columns introduced later, preserving all existing rows."""
    desired = {
        "issuers": [("issuer_code", "VARCHAR(20) NULL AFTER issuer_name")],
        "benefit_categories": [("description", "VARCHAR(255) NULL AFTER category_name")],
        "card_benefits": [("point_value", "DECIMAL(10,4) NULL AFTER reward_unit")],
        "credit_cards": [("bank_id", "INT NULL AFTER issuer_id")],
    }
    cur = conn.cursor()
    for table, columns in desired.items():
        cur.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            (table,),
        )
        existing = {row[0] for row in cur.fetchall()}
        for name, definition in columns:
            if name not in existing:
                cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {definition}")
                print(f"Added {table}.{name}")

    cur.execute(
        "SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'card_benefits' "
        "AND COLUMN_NAME = 'category_id'"
    )
    category = cur.fetchone()
    if category and category[0] == "NO":
        cur.execute(
            "SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'card_benefits' "
            "AND COLUMN_NAME = 'category_id' AND REFERENCED_TABLE_NAME IS NOT NULL"
        )
        key = cur.fetchone()
        if key:
            cur.execute(f"ALTER TABLE card_benefits DROP FOREIGN KEY `{key[0]}`")
        cur.execute("ALTER TABLE card_benefits MODIFY category_id INT NULL")
        if key:
            cur.execute(
                f"ALTER TABLE card_benefits ADD CONSTRAINT `{key[0]}` "
                "FOREIGN KEY (category_id) REFERENCES benefit_categories(category_id) "
                "ON DELETE SET NULL"
            )
        print("Relaxed card_benefits.category_id to nullable")

    conn.commit()
    cur.close()


def backfill_bank_ids(conn):
    cur = conn.cursor()
    cur.execute(
        "UPDATE credit_cards c LEFT JOIN banks b ON b.bank_name = c.bank_name "
        "SET c.bank_id = b.bank_id WHERE c.bank_id IS NULL AND b.bank_id IS NOT NULL"
    )
    conn.commit()
    print(f"Back-filled {cur.rowcount} credit_cards.bank_id values")
    cur.close()


def run_file(conn, filename, replacements=None):
    text = (SQL_DIR / filename).read_text(encoding="utf-8")
    for key, value in (replacements or {}).items():
        text = text.replace(key, value)
    cur = conn.cursor()
    for index, statement in enumerate(split_sql(text), start=1):
        try:
            cur.execute(statement)
        except mysql.connector.Error as error:
            raise RuntimeError(f"{filename} statement #{index} failed: {error}\n{statement}") from error
    conn.commit()
    cur.close()
    print(f"Applied {filename}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init-db", action="store_true", help="Create database if absent")
    parser.add_argument("--skip-seed", action="store_true", help="Only apply the schema")
    args = parser.parse_args()

    if args.init_db:
        ensure_database()

    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
    )
    try:
        run_file(conn, "schema.sql")
        ensure_additive_columns(conn)
        backfill_bank_ids(conn)
        if not args.skip_seed:
            run_file(
                conn,
                "seed.sql",
                {"{{DEMO_PASSWORD_HASH}}": hash_password("Demo@12345")},
            )
        print("Migration complete. Existing card data was preserved.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
