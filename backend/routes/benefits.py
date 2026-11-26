"""Card benefit and benefit-condition endpoints."""

from flask import Blueprint, request

from ..db import cursor, execute, fetch_all, fetch_one, transaction
from ..errors import APIError
from ..security import api_login_required
from ..validation import as_decimal, as_int, ok, require_fields

bp = Blueprint("api_benefits", __name__, url_prefix="/api")

BENEFIT_SQL = """
SELECT b.benefit_id, b.card_id, c.card_name, c.bank_name,
       b.benefit_category, b.cashback_percentage, b.reward_type,
       b.reward_value, b.reward_unit, b.point_value, b.benefit_description,
       b.benefit_status, rc.condition_id, rc.reward_cap, rc.minimum_spend,
       rc.spending_condition, rc.exclusions
FROM card_benefits b
JOIN credit_cards c ON c.card_id = b.card_id
LEFT JOIN reward_conditions rc ON rc.benefit_id = b.benefit_id
"""


@bp.get("/benefits")
def list_benefits():
    card_id = request.args.get("card_id")
    params = ()
    sql = BENEFIT_SQL
    if card_id:
        sql += " WHERE b.card_id = %s"
        params = (as_int(card_id, "card_id", 1),)
    sql += " ORDER BY c.card_name, b.benefit_category LIMIT 500"
    return ok(fetch_all(sql, params))


@bp.get("/benefit-categories")
def benefit_categories():
    return ok(fetch_all("SELECT * FROM benefit_categories ORDER BY category_name"))


@bp.post("/benefits")
@api_login_required
def add_benefit(user):
    data = request.get_json(silent=True) or {}
    require_fields(data, ("card_id", "benefit_category"))
    card_id = as_int(data["card_id"], "card_id", 1)
    if not fetch_one("SELECT card_id FROM credit_cards WHERE card_id=%s", (card_id,)):
        raise APIError("Card not found", 404)

    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "INSERT INTO card_benefits "
            "(card_id, benefit_category, cashback_percentage, reward_type, reward_value, "
            " reward_unit, point_value, benefit_description, benefit_status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                card_id,
                str(data["benefit_category"]).strip(),
                as_decimal(data["cashback_percentage"], "cashback_percentage", 0, 100) if data.get("cashback_percentage") not in (None, "") else None,
                str(data.get("reward_type") or "Cashback").strip(),
                as_decimal(data["reward_value"], "reward_value", 0) if data.get("reward_value") not in (None, "") else None,
                str(data.get("reward_unit") or "INR").strip(),
                as_decimal(data["point_value"], "point_value", 0) if data.get("point_value") not in (None, "") else None,
                str(data.get("benefit_description") or "").strip() or None,
                str(data.get("benefit_status") or "Verified").strip(),
            ),
        )
        benefit_id = cur.lastrowid
        cur.execute(
            "INSERT INTO reward_conditions "
            "(benefit_id, reward_cap, minimum_spend, spending_condition, exclusions) "
            "VALUES (%s,%s,%s,%s,%s)",
            (
                benefit_id,
                as_decimal(data["reward_cap"], "reward_cap", 0) if data.get("reward_cap") not in (None, "") else None,
                as_decimal(data["minimum_spend"], "minimum_spend", 0) if data.get("minimum_spend") not in (None, "") else None,
                str(data.get("spending_condition") or "").strip() or None,
                str(data.get("exclusions") or "").strip() or None,
            ),
        )
    return ok({"benefit_id": benefit_id}, 201, message="Benefit added")


@bp.put("/benefits/<int:benefit_id>")
@api_login_required
def update_benefit(user, benefit_id):
    data = request.get_json(silent=True) or {}
    current = fetch_one(
        "SELECT b.*, rc.condition_id FROM card_benefits b "
        "LEFT JOIN reward_conditions rc ON rc.benefit_id=b.benefit_id "
        "WHERE b.benefit_id=%s",
        (benefit_id,),
    )
    if current is None:
        raise APIError("Benefit not found", 404)

    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "UPDATE card_benefits SET benefit_category=%s, cashback_percentage=%s, "
            "reward_type=%s, reward_value=%s, reward_unit=%s, point_value=%s, "
            "benefit_description=%s, benefit_status=%s WHERE benefit_id=%s",
            (
                str(data.get("benefit_category") or current["benefit_category"]).strip(),
                as_decimal(data["cashback_percentage"], "cashback_percentage", 0, 100) if "cashback_percentage" in data else current["cashback_percentage"],
                str(data.get("reward_type") or current["reward_type"]).strip(),
                as_decimal(data["reward_value"], "reward_value", 0) if "reward_value" in data else current["reward_value"],
                str(data.get("reward_unit") or current["reward_unit"]).strip(),
                as_decimal(data["point_value"], "point_value", 0) if "point_value" in data else current["point_value"],
                str(data.get("benefit_description") or current["benefit_description"] or "").strip() or None,
                str(data.get("benefit_status") or current["benefit_status"]).strip(),
                benefit_id,
            ),
        )
        if current["condition_id"]:
            cur.execute(
                "UPDATE reward_conditions SET reward_cap=%s, minimum_spend=%s, "
                "spending_condition=%s, exclusions=%s WHERE benefit_id=%s",
                (
                    as_decimal(data["reward_cap"], "reward_cap", 0) if "reward_cap" in data else current["reward_cap"],
                    as_decimal(data["minimum_spend"], "minimum_spend", 0) if "minimum_spend" in data else current["minimum_spend"],
                    str(data.get("spending_condition") or current["spending_condition"] or "").strip() or None,
                    str(data.get("exclusions") or current["exclusions"] or "").strip() or None,
                    benefit_id,
                ),
            )
    return ok(message="Benefit updated")


@bp.delete("/benefits/<int:benefit_id>")
@api_login_required
def delete_benefit(user, benefit_id):
    if not fetch_one("SELECT benefit_id FROM card_benefits WHERE benefit_id=%s", (benefit_id,)):
        raise APIError("Benefit not found", 404)
    execute("DELETE FROM card_benefits WHERE benefit_id=%s", (benefit_id,))
    return ok(message="Benefit deleted")
