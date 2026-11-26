"""Authentication and profile REST endpoints."""

import re

from flask import Blueprint, request

from ..db import execute, fetch_one, transaction, cursor
from ..errors import APIError
from ..security import current_user, hash_password, start_session, end_session, verify_password
from ..validation import as_decimal, ok, require_fields

bp = Blueprint("api_auth", __name__, url_prefix="/api/auth")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    require_fields(data, ("full_name", "email", "password"))
    email = str(data["email"]).strip().lower()
    if not EMAIL_RE.match(email):
        raise APIError("A valid email address is required", 400)
    password = str(data["password"])
    if len(password) < 8:
        raise APIError("Password must be at least 8 characters", 400)

    if fetch_one("SELECT user_id FROM users WHERE email = %s", (email,)):
        raise APIError("An account with this email already exists", 409)

    income = None
    if data.get("monthly_income") not in (None, ""):
        income = as_decimal(data["monthly_income"], "monthly_income", minimum=0)

    user_id, _ = execute(
        "INSERT INTO users (full_name, email, password_hash, phone, monthly_income) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            str(data["full_name"]).strip(),
            email,
            hash_password(password),
            str(data.get("phone") or "").strip() or None,
            income,
        ),
    )
    user = fetch_one(
        "SELECT user_id, full_name, email, phone, monthly_income FROM users WHERE user_id=%s",
        (user_id,),
    )
    start_session(user)
    return ok(user, 201, message="Account created")


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    require_fields(data, ("email", "password"))
    email = str(data["email"]).strip().lower()
    user = fetch_one("SELECT * FROM users WHERE email = %s AND is_active = 1", (email,))
    if user is None or not verify_password(str(data["password"]), user["password_hash"]):
        raise APIError("Invalid email or password", 401)

    start_session(user)
    return ok(
        {
            "user_id": user["user_id"],
            "full_name": user["full_name"],
            "email": user["email"],
        },
        message="Logged in successfully",
    )


@bp.post("/logout")
def logout():
    end_session()
    return ok(message="Logged out")


@bp.get("/me")
def me():
    user = current_user()
    if user is None:
        raise APIError("Not authenticated", 401)
    return ok(user)


@bp.put("/profile")
def update_profile():
    user = current_user()
    if user is None:
        raise APIError("Authentication required", 401)
    data = request.get_json(silent=True) or {}
    full_name = str(data.get("full_name") or user["full_name"]).strip()
    phone = data.get("phone", user["phone"])
    income = data.get("monthly_income", user["monthly_income"])
    if income not in (None, ""):
        income = as_decimal(income, "monthly_income", minimum=0)
    else:
        income = None

    with transaction() as conn, cursor(conn) as cur:
        cur.execute(
            "UPDATE users SET full_name=%s, phone=%s, monthly_income=%s WHERE user_id=%s",
            (full_name, str(phone or "").strip() or None, income, user["user_id"]),
        )
    return ok(message="Profile updated")
