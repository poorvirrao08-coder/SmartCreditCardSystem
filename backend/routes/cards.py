"""Credit-card catalogue and user card management endpoints."""

from flask import Blueprint, request

from ..db import cursor, fetch_all, fetch_one, transaction
from ..errors import APIError
from ..security import api_login_required, current_user
from ..validation import as_date, as_decimal, as_int, mask_card_number, ok, require_fields

bp = Blueprint("api_cards", __name__, url_prefix="/api")


@bp.get("/cards/catalogue")
def catalogue():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    params = []
    where = []
    if search:
        where.append("(c.card_name LIKE %s OR c.bank_name LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        where.append("c.card_status = %s")
        params.append(status)
    sql = """
        SELECT c.card_id, c.card_name, c.bank_name, c.card_type,
               c.annual_fee, c.joining_fee, c.reward_rate, c.card_status,
               c.description, MAX(b.cashback_percentage) AS best_cashback,
               COUNT(b.benefit_id) AS benefit_count
        FROM credit_cards c
        LEFT JOIN card_benefits b ON b.card_id = c.card_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY c.card_id ORDER BY c.bank_name, c.card_name LIMIT 500"
    return ok(fetch_all(sql, tuple(params)))


@bp.get("/cards")
@api_login_required
def list_cards(user):
    rows = fetch_all(
        "SELECT * FROM v_user_card_summary WHERE user_id = %s ORDER BY card_name",
        (user["user_id"],),
    )
    return ok(rows)


@bp.get("/cards/<int:card_entry_id>")
@api_login_required
def get_card(user, card_entry_id):
    row = fetch_one(
        "SELECT * FROM v_user_card_summary WHERE user_card_id=%s AND user_id=%s",
        (card_entry_id, user["user_id"]),
    )
    if row is None:
        raise APIError("Card not found", 404)
    return ok(row)


@bp.post("/cards")
@api_login_required
def add_card(user):
    data = request.get_json(silent=True) or {}
    require_fields(data, ("card_number", "credit_limit"))
    masked, last4 = mask_card_number(data["card_number"])
    limit = as_decimal(data["credit_limit"], "credit_limit", minimum=1)
    billing_day = as_int(data.get("billing_day", 1), "billing_day", 1, 28)
    due_day = as_int(data.get("due_day", 20), "due_day", 1, 31)

    with transaction() as conn, cursor(conn) as cur:
        card_id = data.get("card_id")
        if not card_id:
            require_fields(data, ("card_name", "bank_name"))
            cur.execute(
                "INSERT INTO credit_cards (bank_name, card_name, card_type, card_status, description) "
                "VALUES (%s, %s, %s, 'Active', %s)",
                (
                    str(data["bank_name"]).strip(),
                    str(data["card_name"]).strip(),
                    str(data.get("card_type") or "Other").strip(),
                    str(data.get("description") or "User-added credit card").strip(),
                ),
            )
            card_id = cur.lastrowid
        else:
            card_id = as_int(card_id, "card_id", minimum=1)
            if not fetch_one("SELECT card_id FROM credit_cards WHERE card_id=%s", (card_id,)):
                raise APIError("Catalogue card not found", 404)

        cur.execute(
            "INSERT INTO user_cards "
            "(user_id, card_id, card_number_masked, cardholder_name, credit_limit, "
            " available_credit, billing_day, due_day, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')",
            (
                user["user_id"],
                card_id,
                masked,
                str(data.get("cardholder_name") or user["full_name"]).strip(),
                limit,
                limit,
                billing_day,
                due_day,
            ),
        )
        entry_id = cur.lastrowid
    return ok({"user_card_id": entry_id, "card_number_masked": masked}, 201,
              message=f"Card ending {last4} added")


@bp.put("/cards/<int:card_entry_id>")
@api_login_required
def update_card(user, card_entry_id):
    data = request.get_json(silent=True) or {}
    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "SELECT * FROM user_cards WHERE user_card_id=%s AND user_id=%s FOR UPDATE",
            (card_entry_id, user["user_id"]),
        )
        row = cur.fetchone()
        if row is None:
            raise APIError("Card not found", 404)

        limit = as_decimal(data["credit_limit"], "credit_limit", minimum=1) if "credit_limit" in data else row["credit_limit"]
        available = row["available_credit"]
        if limit != row["credit_limit"]:
            available = min(limit, max(DecimalZero, available + (limit - row["credit_limit"])))

        status = str(data.get("status") or row["status"]).lower()
        if status not in ("active", "frozen", "closed"):
            raise APIError("Invalid card status", 400)

        cur.execute(
            "UPDATE user_cards SET credit_limit=%s, available_credit=%s, billing_day=%s, "
            "due_day=%s, cardholder_name=%s, status=%s WHERE user_card_id=%s",
            (
                limit,
                available,
                as_int(data.get("billing_day", row["billing_day"]), "billing_day", 1, 28),
                as_int(data.get("due_day", row["due_day"]), "due_day", 1, 31),
                str(data.get("cardholder_name") or row["cardholder_name"]).strip(),
                status,
                card_entry_id,
            ),
        )
    return ok(message="Card updated")


@bp.delete("/cards/<int:card_entry_id>")
@api_login_required
def delete_card(user, card_entry_id):
    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "SELECT user_card_id FROM user_cards WHERE user_card_id=%s AND user_id=%s FOR UPDATE",
            (card_entry_id, user["user_id"]),
        )
        if cur.fetchone() is None:
            raise APIError("Card not found", 404)
        cur.execute("DELETE FROM payments WHERE user_card_id=%s", (card_entry_id,))
        cur.execute("DELETE FROM transactions WHERE user_card_id=%s", (card_entry_id,))
        cur.execute("DELETE FROM statements WHERE user_card_id=%s", (card_entry_id,))
        cur.execute("DELETE FROM user_cards WHERE user_card_id=%s", (card_entry_id,))
    return ok(message="Card and its related records deleted")


DecimalZero = __import__("decimal").Decimal("0")
