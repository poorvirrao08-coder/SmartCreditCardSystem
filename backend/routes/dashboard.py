"""Dashboard aggregation endpoints."""

from decimal import Decimal

from flask import Blueprint, request

from ..db import fetch_all, fetch_one
from ..errors import APIError
from ..recommendation import recommend
from ..security import api_login_required
from ..validation import as_decimal, ok

bp = Blueprint("api_dashboard", __name__, url_prefix="/api")


@bp.get("/dashboard")
@api_login_required
def dashboard(user):
    user_id = user["user_id"]

    credit = fetch_one(
        "SELECT COUNT(*) AS card_count, "
        "COALESCE(SUM(credit_limit),0) AS total_limit, "
        "COALESCE(SUM(available_credit),0) AS available_credit, "
        "COALESCE(SUM(used_credit),0) AS used_credit, "
        "ROUND(COALESCE(SUM(used_credit),0)/NULLIF(SUM(credit_limit),0)*100,2) AS utilization "
        "FROM v_user_card_summary WHERE user_id=%s",
        (user_id,),
    )

    spending = fetch_one(
        "SELECT COALESCE(SUM(total_spent),0) AS monthly_spending, "
        "COALESCE(SUM(transaction_count),0) AS monthly_transactions "
        "FROM v_monthly_spending WHERE user_id=%s AND spend_month=DATE_FORMAT(CURDATE(), '%Y-%m')",
        (user_id,),
    )

    outstanding = fetch_one(
        "SELECT COALESCE(SUM(total_due-amount_paid),0) AS outstanding "
        "FROM statements s JOIN user_cards uc ON uc.user_card_id=s.user_card_id "
        "WHERE uc.user_id=%s AND LOWER(s.status)<>'paid'",
        (user_id,),
    )

    category_breakdown = fetch_all(
        "SELECT category_name, SUM(total_spent) AS total_spent, SUM(transaction_count) AS transactions "
        "FROM v_monthly_spending WHERE user_id=%s AND spend_month=DATE_FORMAT(CURDATE(), '%Y-%m') "
        "GROUP BY category_name ORDER BY total_spent DESC",
        (user_id,),
    )

    trend = fetch_all(
        "SELECT spend_month, SUM(total_spent) AS total_spent, SUM(transaction_count) AS transactions "
        "FROM v_monthly_spending WHERE user_id=%s GROUP BY spend_month ORDER BY spend_month DESC LIMIT 6",
        (user_id,),
    )
    trend.reverse()

    recent_transactions = fetch_all(
        "SELECT t.transaction_id, t.merchant_name, t.amount, t.transaction_date, "
        "sc.category_name, c.card_name, uc.card_number_masked "
        "FROM transactions t JOIN spending_categories sc ON sc.category_id=t.category_id "
        "JOIN user_cards uc ON uc.user_card_id=t.user_card_id "
        "JOIN credit_cards c ON c.card_id=uc.card_id "
        "WHERE t.user_id=%s ORDER BY t.transaction_date DESC LIMIT 6",
        (user_id,),
    )

    upcoming = fetch_all(
        "SELECT * FROM v_upcoming_payments WHERE user_id=%s ORDER BY due_date ASC LIMIT 5",
        (user_id,),
    )

    suggestion = None
    if category_breakdown:
        top = category_breakdown[0]
        try:
            result = recommend(
                {"amount": top["total_spent"], "category": top["category_name"]},
                user_id=user_id,
            )
            suggestion = result.get("recommended")
        except APIError:
            suggestion = None

    return ok({
        "credit": credit,
        "spending": spending,
        "outstanding": outstanding["outstanding"],
        "category_breakdown": category_breakdown,
        "spending_trend": trend,
        "recent_transactions": recent_transactions,
        "upcoming_payments": upcoming,
        "suggested_card": suggestion,
    })


@bp.get("/dashboard/utilization")
@api_login_required
def utilization(user):
    return ok(fetch_all(
        "SELECT card_name, bank_name, card_number_masked, credit_limit, "
        "available_credit, used_credit, utilization_pct FROM v_user_card_summary "
        "WHERE user_id=%s ORDER BY utilization_pct DESC",
        (user["user_id"],),
    ))


@bp.post("/advisor")
def advisor():
    data = request.get_json(silent=True) or {}
    income = as_decimal(data.get("monthly_income"), "monthly_income", minimum=1)
    categories = ["Shopping", "Dining", "Travel", "Fuel", "Groceries", "Entertainment"]
    spending = {
        name: as_decimal(data.get(name.lower(), 0), name, minimum=0)
        for name in categories
    }
    total = sum(spending.values())
    highest = max(spending, key=spending.get) if total else None

    advice = []
    if total > income:
        advice.append("Your monthly spending is higher than your income. Reduce discretionary categories first.")
    elif total > income * Decimal("0.7"):
        advice.append("You are spending over 70% of your income. Build a larger emergency buffer.")
    else:
        advice.append("Your spending is within a comfortable range of your income.")
    if highest:
        advice.append(f"{highest} is your largest category. A category-specific rewards card can improve returns.")
    if spending["Fuel"] > 0:
        advice.append("Check fuel cashback cards, but watch for excluded merchants and monthly caps.")

    recommendation = None
    if highest and spending[highest] > 0:
        result = recommend({
            "amount": spending[highest],
            "category": highest,
            "merchant": data.get("merchant", ""),
        })
        recommendation = result.get("recommended")

    return ok({
        "monthly_income": income,
        "total_spending": total,
        "category_spending": spending,
        "highest_category": highest,
        "advice": advice,
        "recommended_card": recommendation,
    })
