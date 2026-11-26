"""Password hashing, sessions and route guards."""

from functools import wraps

from flask import jsonify, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import fetch_one
from .errors import APIError


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256:260000")


def verify_password(password, password_hash):
    try:
        return check_password_hash(password_hash, password)
    except (TypeError, ValueError):
        return False


def start_session(user_row):
    session.clear()
    session["user_id"] = user_row["user_id"]
    session["user_email"] = user_row["email"]
    session["user_name"] = user_row["full_name"]


def end_session():
    session.clear()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return fetch_one(
        "SELECT user_id, full_name, email, phone, monthly_income, created_at "
        "FROM users WHERE user_id = %s AND is_active = 1",
        (user_id,),
    )


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            raise APIError("Authentication required", 401)
        return view(user, *args, **kwargs)

    return wrapped


def page_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("pages.login"))
        return view(*args, **kwargs)

    return wrapped
