"""Input validation and JSON serialisation helpers."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .errors import APIError

DIGITS_ONLY = re.compile(r"^\d{13,19}$")


def require_fields(data, fields):
    missing = [field for field in fields if data.get(field) in (None, "")]
    if missing:
        raise APIError(
            "Missing required fields: " + ", ".join(missing),
            400,
            {"missing": missing},
        )


def as_decimal(value, field, minimum=None, maximum=None):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise APIError(f"{field} must be a number", 400)
    if not number.is_finite():
        raise APIError(f"{field} must be a finite number", 400)
    if minimum is not None and number < Decimal(str(minimum)):
        raise APIError(f"{field} must be at least {minimum}", 400)
    if maximum is not None and number > Decimal(str(maximum)):
        raise APIError(f"{field} must be at most {maximum}", 400)
    return number


def as_int(value, field, minimum=None, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise APIError(f"{field} must be an integer", 400)
    if minimum is not None and number < minimum:
        raise APIError(f"{field} must be at least {minimum}", 400)
    if maximum is not None and number > maximum:
        raise APIError(f"{field} must be at most {maximum}", 400)
    return number


def as_date(value, field):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise APIError(f"{field} must be a date in YYYY-MM-DD format", 400)


def luhn_valid(number):
    digits = [int(char) for char in number]
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def mask_card_number(number):
    digits = re.sub(r"\s+", "", str(number or ""))
    if not DIGITS_ONLY.match(digits) or not luhn_valid(digits):
        raise APIError(
            "Card number must be 13-19 digits and pass the Luhn check", 400
        )
    return "**** **** **** " + digits[-4:], digits[-4:]


def serialize(value):
    """Convert Decimal/date objects into JSON-safe primitives."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    return value


def ok(payload=None, status_code=200, **extra):
    from flask import jsonify

    body = {"success": True}
    if payload is not None:
        body["data"] = serialize(payload)
    body.update(serialize(extra))
    return jsonify(body), status_code
