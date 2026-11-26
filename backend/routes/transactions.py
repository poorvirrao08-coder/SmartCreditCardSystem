"""Transaction endpoints with atomic credit-limit updates."""

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, request

from ..db import cursor, fetch_all, fetch_one, transaction
from ..errors import APIError
from ..security import api_login_required
from ..validation import as_date, as_decimal, as_int, ok, require_fields

bp = Blueprint("api_transactions", __name__, url_prefix="/api")

LIST_SQL = """
SELECT t.transaction_id, t.merchant_name, t.amount, t.transaction_date,
       t.description, t.status, t.user_card_id,
       sc.category_name, c.card_name, c.bank_name, uc.card_number_masked
FROM transactions t
JOIN spending_categories sc ON sc.category_id = t.category_id
JOIN user_cards uc ON uc.user_card_id = t.user_card_id
JOIN credit_cards c ON c.card_id = uc.card_id
WHERE t.user_id = %s
"""


def _category_id(cur, data):
    if data.get("category_id") not in (None, ""):
        category_id = as_int(data["category_id"], "category_id", 1)
        if not fetch_one("SELECT category_id FROM spending_categories WHERE category_id=%s", (category_id,)):
            raise APIError("Category not found", 404)
        return category_id
    name = str(data.get("category") or "").strip()
    if not name:
        raise APIError("category or category_id is required", 400)
    row = fetch_one("SELECT category_id FROM spending_categories WHERE category_name=%s", (name,))
    if row:
        return row["category_id"]
    cur.execute("INSERT INTO spending_categories (category_name) VALUES (%s)", (name,))
    return cur.lastrowid


def _statement_id(cur, user_card_id, when):
    cur.execute(
        "SELECT statement_id FROM statements WHERE user_card_id=%s "
        "AND statement_month=DATE_FORMAT(%s, '%Y-%m-01')",
        (user_card_id, when),
    )
    row = cur.fetchone()
    return row["statement_id"] if row else None


def _current_statement(cur, user_card_id):
    cur.execute("SELECT statement_id FROM statements WHERE user_card_id=%s ORDER BY statement_month DESC LIMIT 1", (user_card_id,))
    row = cur.fetchone()
    return row["statement_id"] if row else None


@bp.get("/transactions")
@api_login_required
def list_transactions(user):
    conditions, params = [], [user["user_id"]]
    month = request.args.get("month", "").strip()
    category = request.args.get("category", "").strip()
    card_id = request.args.get("card_id")
    if month:
        conditions.append("DATE_FORMAT(t.transaction_date, '%Y-%m') = %s")
        params.append(month)
    if category:
        conditions.append("sc.category_name = %s")
        params.append(category)
    if card_id:
        conditions.append("t.user_card_id = %s")
        params.append(as_int(card_id, "card_id", 1))
    sql = LIST_SQL
    if conditions:
        sql += " AND " + " AND ".join(conditions)
    sql += " ORDER BY t.transaction_date DESC, t.transaction_id DESC LIMIT 500"
    return ok(fetch_all(sql, tuple(params)))


@bp.get("/transactions/summary")
@api_login_required
def transaction_summary(user):
    month = request.args.get("month", "").strip()
    params = [user["user_id"]]
    where = "WHERE t.user_id=%s"
    if month:
        where += " AND DATE_FORMAT(t.transaction_date, '%Y-%m')=%s"
        params.append(month)
    rows = fetch_all(
        "SELECT sc.category_name, COUNT(*) AS transactions, SUM(t.amount) AS total_spent, "
        "AVG(t.amount) AS average_spend, MAX(t.amount) AS highest_spend, MIN(t.amount) AS lowest_spend "
        "FROM transactions t JOIN spending_categories sc ON sc.category_id=t.category_id "
        + where + " GROUP BY sc.category_name ORDER BY total_spent DESC",
        tuple(params),
    )
    return ok(rows)


@bp.post("/transactions")
@api_login_required
def add_transaction(user):
    data = request.get_json(silent=True) or {}
    require_fields(data, ("user_card_id", "amount", "merchant_name"))
    amount = as_decimal(data["amount"], "amount", minimum=Decimal("0.01"))
    card_id = as_int(data["user_card_id"], "user_card_id", 1)
    merchant = str(data["merchant_name"]).strip()
    when = datetime.now()
    if data.get("transaction_date"):
        parsed = as_date(data["transaction_date"], "transaction_date")
        when = datetime.combine(parsed, datetime.now().time())

    with transaction() as conn, cursor(conn) as cur:
        category_id = _category_id(cur, data)
        cur.execute(
            "SELECT uc.*, c.card_name FROM user_cards uc JOIN credit_cards c ON c.card_id=uc.card_id "
            "WHERE uc.user_card_id=%s AND uc.user_id=%s FOR UPDATE",
            (card_id, user["user_id"]),
        )
        card = cur.fetchone()
        if card is None:
            raise APIError("Card not found", 404)
        if card["status"] != "active":
            raise APIError("Only active cards can be used for transactions", 400)
        if amount > card["available_credit"]:
            raise APIError(
                f"Insufficient available credit (₹{card['available_credit']})", 400
            )

        statement_id = _statement_id(cur, card_id, when)
        cur.execute(
            "INSERT INTO transactions "
            "(user_id, user_card_id, category_id, statement_id, merchant_name, amount, "
            " transaction_date, description, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                user["user_id"], card_id, category_id, statement_id, merchant, amount,
                when, str(data.get("description") or "").strip() or None,
                str(data.get("status") or "posted").lower(),
            ),
        )
        transaction_id = cur.lastrowid
        cur.execute(
            "UPDATE user_cards SET available_credit=available_credit-%s WHERE user_card_id=%s",
            (amount, card_id),
        )
        if statement_id:
            cur.execute(
                "UPDATE statements SET total_due=total_due+%s WHERE statement_id=%s",
                (amount, statement_id),
            )
    return ok({"transaction_id": transaction_id}, 201, message="Transaction recorded")


@bp.put("/transactions/<int:transaction_id>")
@api_login_required
def update_transaction(user, transaction_id):
    data = request.get_json(silent=True) or {}
    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM transactions WHERE transaction_id=%s AND user_id=%s FOR UPDATE",
            (transaction_id, user["user_id"]),
        )
        old = cur.fetchone()
        if old is None:
            raise APIError("Transaction not found", 404)

        category_id = _category_id(cur, data) if ("category" in data or "category_id" in data) else old["category_id"]
        amount = as_decimal(data["amount"], "amount", minimum=Decimal("0.01")) if "amount" in data else old["amount"]
        card_id = as_int(data["user_card_id"], "user_card_id", 1) if "user_card_id" in data else old["user_card_id"]

        cur.execute("SELECT * FROM user_cards WHERE user_card_id=%s FOR UPDATE", (old["user_card_id"],))
        old_card = cur.fetchone()
        if old_card is None:
            raise APIError("Linked card not found", 404)
        cur.execute(
            "UPDATE user_cards SET available_credit=available_credit+%s WHERE user_card_id=%s",
            (old["amount"], old["user_card_id"]),
        )
        if old["statement_id"]:
            cur.execute(
                "UPDATE statements SET total_due=GREATEST(0, total_due-%s) WHERE statement_id=%s",
                (old["amount"], old["statement_id"]),
            )

        if card_id != old["user_card_id"]:
            cur.execute("SELECT * FROM user_cards WHERE user_card_id=%s AND user_id=%s FOR UPDATE", (card_id, user["user_id"]))
            new_card = cur.fetchone()
        else:
            new_card = old_card
        if new_card is None:
            raise APIError("Card not found", 404)
        if amount > new_card["available_credit"]:
            raise APIError("Insufficient available credit for updated transaction", 400)

        statement_id = _current_statement(cur, card_id)
        when = old["transaction_date"]
        if data.get("transaction_date"):
            when = datetime.combine(as_date(data["transaction_date"], "transaction_date"), datetime.now().time())

        cur.execute(
            "UPDATE transactions SET user_card_id=%s, category_id=%s, statement_id=%s, "
            "merchant_name=%s, amount=%s, transaction_date=%s, description=%s WHERE transaction_id=%s",
            (
                card_id, category_id, statement_id,
                str(data.get("merchant_name") or old["merchant_name"]).strip(),
                amount, when,
                str(data.get("description") or old["description"] or "").strip() or None,
                transaction_id,
            ),
        )
        cur.execute(
            "UPDATE user_cards SET available_credit=available_credit-%s WHERE user_card_id=%s",
            (amount, card_id),
        )
        if statement_id:
            cur.execute("UPDATE statements SET total_due=total_due+%s WHERE statement_id=%s", (amount, statement_id))
    return ok(message="Transaction updated")


@bp.delete("/transactions/<int:transaction_id>")
@api_login_required
def delete_transaction(user, transaction_id):
    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM transactions WHERE transaction_id=%s AND user_id=%s FOR UPDATE",
            (transaction_id, user["user_id"]),
        )
        row = cur.fetchone()
        if row is None:
            raise APIError("Transaction not found", 404)
        cur.execute(
            "UPDATE user_cards SET available_credit=available_credit+%s WHERE user_card_id=%s",
            (row["amount"], row["user_card_id"]),
        )
        if row["statement_id"]:
            cur.execute(
                "UPDATE statements SET total_due=GREATEST(0, total_due-%s) WHERE statement_id=%s",
                (row["amount"], row["statement_id"]),
            )
        cur.execute("DELETE FROM transactions WHERE transaction_id=%s", (transaction_id,))
    return ok(message="Transaction deleted")
