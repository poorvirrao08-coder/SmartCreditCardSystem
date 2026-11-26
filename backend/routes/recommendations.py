"""Smart recommendation REST endpoints."""

from flask import Blueprint, request

from ..db import fetch_all
from ..recommendation import recommend
from ..security import current_user
from ..validation import ok

bp = Blueprint("api_recommendations", __name__, url_prefix="/api")


@bp.get("/recommendation-categories")
def recommendation_categories():
    return ok(fetch_all(
        "SELECT bc.category_name, bc.description FROM benefit_categories bc "
        "WHERE EXISTS (SELECT 1 FROM card_benefits b WHERE b.benefit_category=bc.category_name) "
        "ORDER BY bc.category_name"
    ))


@bp.post("/recommendations")
def recommendations():
    data = request.get_json(silent=True) or {}
    user = current_user()
    result = recommend(data, user_id=user["user_id"] if user else None)
    return ok(result)
