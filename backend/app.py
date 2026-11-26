"""Extend the existing Flask app with REST APIs and the new dashboard pages."""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from .config import Config
from .db import MySQLError
from .errors import APIError
from .security import current_user, end_session
from .validation import serialize

pages = Blueprint("pages", __name__)


@pages.app_context_processor
def inject_user():
    return {"current_user": current_user()}


@pages.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@pages.route("/my-cards")
def my_cards():
    return render_template("mycards.html")


@pages.route("/transactions")
def transactions():
    return render_template("transactions.html")


@pages.route("/payments")
def payments():
    return render_template("payments.html")


@pages.route("/profile")
def profile():
    return render_template("profile.html")


@pages.route("/login")
def login_page():
    return render_template("login.html")


@pages.route("/register")
def register_page():
    return render_template("register.html")


@pages.route("/logout")
def logout_page():
    end_session()
    return redirect(url_for("home"))


def register_errors(app):
    @app.errorhandler(APIError)
    def handle_api_error(error):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(MySQLError)
    def handle_database_error(error):
        app.logger.exception("Database error")
        return jsonify({
            "success": False,
            "error": "Database operation failed",
            "details": {"message": str(error)},
        }), 500

    @app.errorhandler(404)
    def handle_404(error):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Endpoint not found"}), 404
        return error

    @app.errorhandler(405)
    def handle_405(error):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Method not allowed"}), 405
        return error


def extend_app(app):
    """Register every new module on the existing application instance."""
    from .routes.auth import bp as auth_bp
    from .routes.cards import bp as cards_bp
    from .routes.benefits import bp as benefits_bp
    from .routes.transactions import bp as transactions_bp
    from .routes.payments import bp as payments_bp
    from .routes.dashboard import bp as dashboard_bp
    from .routes.recommendations import bp as recommendations_bp

    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.json.default = serialize
    app.register_blueprint(pages)
    for blueprint in (
        auth_bp,
        cards_bp,
        benefits_bp,
        transactions_bp,
        payments_bp,
        dashboard_bp,
        recommendations_bp,
    ):
        app.register_blueprint(blueprint)
    register_errors(app)
    return app
