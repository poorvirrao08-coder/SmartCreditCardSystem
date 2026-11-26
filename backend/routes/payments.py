"""Payment and due-date tracking endpoints."""

from datetime import date
from decimal import Decimal

from flask import Blueprint, request

from ..db import cursor, fetch_all, fetch_one, transaction
from ..errors import APIError
from ..security import api_login_required
from ..validation import as_date, as_decimal, as_int, ok, require_fields

bp = Blueprint("api_payments", __name__, url_prefix="/api")


@bp.get("/payments")
@api_login_required
def list_payments(user):
    params = [user["user_id"]]
    where = "WHERE uc.user_id=%s"
    status = request.args.get("status", "").strip()
    if status:
        where += " AND p.status=%s"
        params.append(status)
    rows = fetch_all(
        "SELECT p.payment_id, p.amount, p.payment_date, p.payment_method, p.status, "
        "p.reference_number, p.notes, p.statement_id, uc.user_card_id, "
        "c.card_name, c.bank_name, uc.card_number_masked "
        "FROM payments p JOIN user_cards uc ON uc.user_card_id=p.user_card_id "
        "JOIN credit_cards c ON c.card_id=uc.card_id " + where +
        " ORDER BY p.payment_date DESC LIMIT 500",
        tuple(params),
    )
    return ok(rows)


@bp.get("/payments/upcoming")
@api_login_required
def upcoming_payments(user):
    return ok(fetch_all(
        "SELECT * FROM v_upcoming_payments WHERE user_id=%s "
        "ORDER BY due_date ASC LIMIT 50",
        (user["user_id"],),
    ))


def _apply_payment(cur, user_card_id, amount, statement_id):
    cur.execute("SELECT * FROM user_cards WHERE user_card_id=%s FOR UPDATE", (user_card_id,))
    card = cur.fetchone()
    if card is None:
        raise APIError("Card not found", 404)
    restored = min(amount, card["credit_limit"] - card["available_credit"])
    if restored > 0:
        cur.execute(
            "UPDATE user_cards SET available_credit=available_credit+%s WHERE user_card_id=%s",
            (restored, user_card_id),
        )
    if statement_id:
        cur.execute(
            "UPDATE statements SET amount_paid=amount_paid+%s, "
            "status=CASE WHEN amount_paid+%s >= total_due THEN 'paid' ELSE status END "
            "WHERE statement_id=%s",
            (amount, amount, statement_id),
        )


def _revert_payment(cur, user_card_id, amount, statement_id):
    cur.execute("SELECT * FROM user_cards WHERE user_card_id=%s FOR UPDATE", (user_card_id,))
    card = cur.fetchone()
    if card is None:
        return
    rollback_amount = min(amount, card["credit_limit"] - card["available_credit"])
    if rollback_amount > 0:
        cur.execute(
            "UPDATE user_cards SET available_credit=available_credit-%s WHERE user_card_id=%s",
            (rollback_amount, user_card_id),
        )
    if statement_id:
        cur.execute(
            "UPDATE statements SET amount_paid=GREATEST(0, amount_paid-%s), "
            "status=CASE WHEN amount_paid-%s < total_due THEN 'open' ELSE status END "
            "WHERE statement_id=%s",
            (amount, amount, statement_id),
        )


@bp.post("/payments")
@api_login_required
def add_payment(user):
    data = request.get_json(silent=True) or {}
    require_fields(data, ("user_card_id", "amount"))
    amount = as_decimal(data["amount"], "amount", minimum=Decimal("0.01"))
    card_id = as_int(data["user_card_id"], "user_card_id", 1)
    payment_date = as_date(data["payment_date"], "payment_date") if data.get("payment_date") else date.today()
    status = str(data.get("status") or "completed").lower()
    if status not in ("pending", "completed", "failed"):
        raise APIError("Invalid payment status", 400)
    statement_id = as_int(data["statement_id"], "statement_id", 1) if data.get("statement_id") else None
    method = str(data.get("payment_method") or "upi").lower()
    if method not in ("net_banking", "upi", "card", "cash", "other"):
        raise APIError("Invalid payment method", 400)

    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "SELECT user_card_id FROM user_cards WHERE user_card_id=%s AND user_id=%s",
            (card_id, user["user_id"]),
        )
        if cur.fetchone() is None:
            raise APIError("Card not found", 404)
        cur.execute(
            "INSERT INTO payments (user_card_id, statement_id, amount, payment_date, "
            "payment_method, reference_number, status, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                card_id, statement_id, amount, payment_date, method,
                str(data.get("reference_number") or "").strip() or None,
                status, str(data.get("notes") or "").strip() or None,
            ),
        )
        payment_id = cur.lastrowid
        if status == "completed":
            _apply_payment(cur, card_id, amount, statement_id)
    return ok({"payment_id": payment_id}, 201, message="Payment recorded")


@bp.put("/payments/<int:payment_id>")
@api_login_required
def update_payment(user, payment_id):
    data = request.get_json(silent=True) or {}
    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "SELECT p.*, uc.user_id FROM payments p JOIN user_cards uc ON uc.user_card_id=p.user_card_id "
            "WHERE p.payment_id=%s FOR UPDATE",
            (payment_id,),
        )
        old = cur.fetchone()
        if old is None or old["user_id"] != user["user_id"]:
            raise APIError("Payment not found", 404)

        new_status = str(data.get("status") or old["status"]).lower()
        if new_status not in ("pending", "completed", "failed"):
            raise APIError("Invalid payment status", 400)
        if old["status"] == "completed" and new_status != "completed":
            _revert_payment(cur, old["user_card_id"], old["amount"], old["statement_id"])
        elif old["status"] != "completed" and new_status == "completed":
            _apply_payment(cur, old["user_card_id"], old["amount"], old["statement_id"])
        cur.execute(
            "UPDATE payments SET status=%s, notes=COALESCE(%s, notes) WHERE payment_id=%s",
            (new_status, str(data.get("notes") or "").strip() or None, payment_id),
        )
    return ok(message="Payment updated")


@bp.delete("/payments/<int:payment_id>")
@api_login_required
def delete_payment(user, payment_id):
    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "SELECT p.*, uc.user_id FROM payments p JOIN user_cards uc ON uc.user_card_id=p.user_card_id "
            "WHERE p.payment_id=%s FOR UPDATE",
            (payment_id,),
        )
        row = cur.fetchone()
        if row is None or row["user_id"] != user["user_id"]:
            raise APIError("Payment not found", 404)
        if row["status"] == "completed":
            _revert_payment(cur, row["user_card_id"], row["amount"], row["statement_id"])
        cur.execute("DELETE FROM payments WHERE payment_id=%s", (payment_id,))
    return ok(message="Payment deleted")
