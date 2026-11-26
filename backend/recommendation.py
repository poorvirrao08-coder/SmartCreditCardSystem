"""Smart card recommendation engine.

The engine ranks cards by the *actual* benefit earned on the requested
purchase after applying reward caps, minimum-spend rules, category
exclusions, point conversion values, annual fees and available credit.
"""

from decimal import Decimal

from .db import fetch_all
from .errors import APIError
from .validation import as_decimal, require_fields

CARD_SQL = """
SELECT
    uc.user_card_id,
    uc.card_number_masked,
    uc.credit_limit,
    uc.available_credit,
    c.card_id,
    c.card_name,
    c.bank_name,
    c.card_type,
    c.annual_fee,
    b.benefit_id,
    b.benefit_category,
    b.cashback_percentage,
    b.reward_type,
    b.reward_value,
    b.reward_unit,
    b.point_value,
    b.benefit_description,
    rc.reward_cap,
    rc.minimum_spend,
    rc.spending_condition,
    rc.exclusions
FROM user_cards uc
JOIN credit_cards c ON c.card_id = uc.card_id
JOIN card_benefits b ON b.card_id = c.card_id
LEFT JOIN reward_conditions rc ON rc.benefit_id = b.benefit_id
WHERE uc.user_id = %s
  AND LOWER(uc.status) = 'active'
  AND LOWER(b.benefit_status) = 'verified'
"""

CATALOG_SQL = """
SELECT
    NULL AS user_card_id,
    NULL AS card_number_masked,
    NULL AS credit_limit,
    NULL AS available_credit,
    c.card_id,
    c.card_name,
    c.bank_name,
    c.card_type,
    c.annual_fee,
    b.benefit_id,
    b.benefit_category,
    b.cashback_percentage,
    b.reward_type,
    b.reward_value,
    b.reward_unit,
    b.point_value,
    b.benefit_description,
    rc.reward_cap,
    rc.minimum_spend,
    rc.spending_condition,
    rc.exclusions
FROM credit_cards c
JOIN card_benefits b ON b.card_id = c.card_id
LEFT JOIN reward_conditions rc ON rc.benefit_id = b.benefit_id
WHERE LOWER(c.card_status) = 'active'
  AND LOWER(b.benefit_status) = 'verified'
"""

GENERAL_CATEGORIES = {"all", "general", "everyday", "other", "any"}


def _category_matches(benefit_category, card_type, category):
    wanted = (category or "").strip().lower()
    offered = (benefit_category or "").strip().lower()
    kind = (card_type or "").strip().lower()
    if not offered or offered in GENERAL_CATEGORIES or wanted == offered:
        return True
    return kind == wanted


def _excluded(exclusions, category, merchant):
    text = (exclusions or "").lower()
    if not text.strip():
        return False
    if category and category.lower() in text:
        return True
    if merchant:
        words = [word for word in merchant.lower().split() if len(word) > 3]
        if any(word in text for word in words):
            return True
    return False


def _money(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def calculate_benefit(row, amount, category, merchant):
    """Return (cashback, points, rupee_value, notes) for one benefit row."""
    notes = []
    reward_type = (row.get("reward_type") or "").strip().lower()
    unit = (row.get("reward_unit") or "").strip().lower()
    condition = (row.get("spending_condition") or "").strip()
    cap = _money(row.get("reward_cap"))
    cashback = Decimal("0")
    points = Decimal("0")
    value = None

    if reward_type == "cashback" or row.get("cashback_percentage") is not None:
        percentage = _money(row.get("cashback_percentage")) or Decimal("0")
        cashback = amount * percentage / Decimal("100")
        notes.append(f"{percentage}% cashback on {category}")
        if cap is not None and (
            "cash" in unit or "rupee" in unit or "inr" in unit
            or unit in ("", "₹") or "cap" in condition.lower()
            or "up to" in condition.lower()
        ):
            if cashback > cap:
                cashback = cap
                notes.append(f"cashback capped at ₹{cap}")
        value = cashback
    elif reward_type in ("reward points", "points", "miles", "cashpoints"):
        reward_value = _money(row.get("reward_value")) or Decimal("0")
        per_hundred = "100" in (row.get("benefit_description") or "")
        points = (amount / Decimal("100") * reward_value) if per_hundred else amount * reward_value
        notes.append(f"{reward_value} {unit or 'points'} per eligible spend")
        if cap is not None and ("point" in unit or "mile" in unit or "cashpoint" in unit):
            if points > cap:
                points = cap
                notes.append(f"points capped at {cap}")
        point_value = _money(row.get("point_value"))
        if point_value is not None:
            value = points * point_value
            notes.append(f"points valued at ₹{point_value} each")
        else:
            notes.append("point conversion value is not recorded")

    if row.get("exclusions"):
        notes.append("category exclusions checked")
    if condition:
        notes.append(condition)
    return cashback, points, value, notes


def recommend(payload, user_id=None):
    """Return ranked recommendations for a purchase.

    `payload` must contain `amount` and `category`; `merchant` is optional.
    """
    require_fields(payload, ("amount", "category"))
    amount = as_decimal(payload.get("amount"), "amount", minimum=Decimal("0.01"))
    category = str(payload.get("category", "")).strip()
    merchant = str(payload.get("merchant", "") or "").strip()

    if user_id is not None:
        rows = fetch_all(CARD_SQL, (user_id,))
    else:
        rows = fetch_all(CATALOG_SQL)

    eligible, ineligible = [], []

    for row in rows:
        if not _category_matches(row.get("benefit_category"), row.get("card_type"), category):
            continue

        reasons = []
        if _excluded(row.get("exclusions"), category, merchant):
            ineligible.append({
                "card_name": row["card_name"],
                "bank_name": row["bank_name"],
                "reason": f"{category} is excluded from this benefit",
            })
            continue

        minimum_spend = _money(row.get("minimum_spend"))
        if minimum_spend is not None and amount < minimum_spend:
            ineligible.append({
                "card_name": row["card_name"],
                "bank_name": row["bank_name"],
                "reason": f"minimum eligible spend is ₹{minimum_spend}",
            })
            continue

        if row.get("available_credit") is not None:
            if amount > Decimal(str(row["available_credit"])):
                ineligible.append({
                    "card_name": row["card_name"],
                    "bank_name": row["bank_name"],
                    "reason": "purchase exceeds available credit",
                })
                continue
            reasons.append("sufficient available credit")

        cashback, points, value, notes = calculate_benefit(row, amount, category, merchant)
        if value is None:
            value = cashback
        if value is None or value <= 0:
            ineligible.append({
                "card_name": row["card_name"],
                "bank_name": row["bank_name"],
                "reason": "no calculable monetary benefit for this purchase",
            })
            continue

        annual_fee = _money(row.get("annual_fee")) or Decimal("0")
        monthly_fee = annual_fee / Decimal("12")
        net_value = value - monthly_fee
        reasons.extend(notes)
        if annual_fee > 0:
            reasons.append(f"annual fee ₹{annual_fee} amortised over 12 months")

        eligible.append({
            "user_card_id": row["user_card_id"],
            "card_id": row["card_id"],
            "card_name": row["card_name"],
            "bank_name": row["bank_name"],
            "card_type": row["card_type"],
            "card_number_masked": row["card_number_masked"],
            "available_credit": row["available_credit"],
            "credit_limit": row["credit_limit"],
            "annual_fee": annual_fee,
            "expected_cashback": cashback,
            "expected_points": points,
            "expected_value": value,
            "net_monthly_value": net_value,
            "benefit_category": row["benefit_category"],
            "benefit_description": row["benefit_description"],
            "reason": "; ".join(reasons),
        })

    eligible.sort(key=lambda item: (item["net_monthly_value"], item["expected_value"]), reverse=True)
    for index, item in enumerate(eligible, start=1):
        item["rank"] = index
        item["is_recommended"] = index == 1

    return {
        "amount": amount,
        "category": category,
        "merchant": merchant,
        "recommended": eligible[0] if eligible else None,
        "eligible_cards": eligible,
        "ineligible_cards": ineligible,
    }
