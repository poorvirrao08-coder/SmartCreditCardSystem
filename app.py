import os

from flask import Flask, render_template, request
import mysql.connector


app = Flask(__name__)


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db_connection():
    """Connect to MySQL using environment variables."""
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "smartcard_app"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE", "smart_credit_card")
    )


# ==========================================
# SPENDING CATEGORY DETECTION
# ==========================================

def detect_spending_categories(text):
    text = (text or "").lower()

    keywords = {
        "Shopping": [
            "shopping", "online shopping", "amazon",
            "flipkart", "myntra", "purchases", "retail"
        ],
        "Dining": [
            "dining", "restaurant", "restaurants",
            "food", "eating out", "cafe", "cafes"
        ],
        "Travel": [
            "travel", "travelling", "flights",
            "flight", "airline", "holiday", "vacation",
            "train", "bus"
        ],
        "Fuel": [
            "fuel", "petrol", "diesel",
            "gas station", "gasoline"
        ]
    }

    detected_categories = []

    for category, words in keywords.items():
        for word in words:
            if word in text:
                detected_categories.append(category)
                break

    return detected_categories


# ==========================================
# REWARD CALCULATION HELPERS
# ==========================================

def calculate_monthly_cashback(
    spending,
    percentage,
    reward_cap=None,
    spending_condition="",
    reward_unit=""
):
    """Calculate monthly cashback and apply explicitly monthly caps."""

    gross_reward = float(spending) * float(percentage) / 100

    condition_text = (spending_condition or "").lower()
    unit_text = (reward_unit or "").lower()

    cap_is_monthly = (
        "per calendar month" in condition_text
        or "per month" in condition_text
        or "monthly cap" in condition_text
    )

    if reward_cap is not None and cap_is_monthly:

        # Apply the cap only when the reward unit has a known
        # rupee-equivalent interpretation.
        if (
            "cashpoint" in unit_text
            or unit_text in ("inr", "rupee", "rupees", "₹")
        ):
            gross_reward = min(
                gross_reward,
                float(reward_cap)
            )

    return round(gross_reward, 2)


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# TEST DATABASE CONNECTION
# ==========================================

@app.route("/test-db")
def test_db():
    connection = None

    try:
        connection = get_db_connection()
        return "MySQL connection successful!"

    except mysql.connector.Error as error:
        app.logger.exception("Database connection failed")
        return f"MySQL connection failed: {error}"

    finally:
        if connection is not None and connection.is_connected():
            connection.close()


# ==========================================
# BROWSE CREDIT CARDS
# ==========================================

@app.route("/cards")
def browse_cards():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM credit_cards
            ORDER BY bank_name, card_name
        """)

        cards = cursor.fetchall()

        return render_template(
            "cards.html",
            cards=cards
        )

    except mysql.connector.Error as error:
        app.logger.exception("Browse cards database error")
        return f"Unable to load credit cards: {error}", 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# ==========================================
# COMPARE CREDIT CARDS
# ==========================================

@app.route("/compare")
def compare_cards():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM credit_cards
            ORDER BY bank_name, card_name
        """)

        cards = cursor.fetchall()

        return render_template(
            "compare.html",
            cards=cards
        )

    except mysql.connector.Error as error:
        app.logger.exception("Compare cards database error")
        return f"Unable to load cards for comparison: {error}", 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# ==========================================
# SMART CREDIT CARD RECOMMENDATIONS
# ==========================================

@app.route("/recommend", methods=["GET", "POST"])
def recommend():

    recommendations = []
    error = None
    searched = request.method == "POST"
    no_verified_results = False

    if searched:

        spending = request.form.get(
            "spending_category", ""
        ).strip()

        income_text = request.form.get(
            "monthly_income", ""
        ).strip()

        try:
            monthly_income = float(income_text)

            if monthly_income <= 0:

                error = "Please enter a valid monthly income."

            elif not spending:

                error = "Please select a spending category."

            else:

                annual_income = monthly_income * 12

                connection = get_db_connection()
                cursor = connection.cursor(dictionary=True)

                # Only Active cards with Verified benefits
                # are eligible for recommendations.

                cursor.execute(
                    """
                    SELECT DISTINCT
                        c.*,
                        b.benefit_category,
                        b.benefit_description,
                        b.reward_type,
                        b.reward_value,
                        b.reward_unit,
                        b.cashback_percentage,
                        b.benefit_status

                    FROM credit_cards c

                    INNER JOIN card_benefits b
                        ON c.card_id = b.card_id

                    WHERE LOWER(c.card_status) = 'active'
                      AND LOWER(b.benefit_status) = 'verified'

                      AND (
                          c.minimum_income IS NULL
                          OR c.minimum_income <= %s
                      )

                      AND (
                          b.benefit_category = %s
                          OR c.card_type = %s
                      )

                    ORDER BY
                        CASE
                            WHEN c.annual_fee IS NULL THEN 1
                            ELSE 0
                        END,
                        c.annual_fee ASC
                    """,
                    (annual_income, spending, spending)
                )

                recommendations = cursor.fetchall()

                no_verified_results = (
                    len(recommendations) == 0
                )

                cursor.close()
                connection.close()

        except ValueError:

            error = (
                "Please enter a valid number for monthly income."
            )

        except mysql.connector.Error as database_error:

            app.logger.exception(
                "Recommendation database error"
            )

            error = f"Database Error: {database_error}"

    return render_template(
        "recommend.html",
        recommendations=recommendations,
        error=error,
        searched=searched,
        no_verified_results=no_verified_results
    )


# ==========================================
# SMART SPENDING ADVISOR
# ==========================================

@app.route("/advisor", methods=["GET", "POST"])
def advisor():

    recommendations = []
    error = None

    spending_summary = {}
    total_spending = 0
    highest_category = None
    detected_categories = []

    spending_problem = ""
    no_verified_results = False

    if request.method == "POST":

        spending_problem = request.form.get(
            "spending_problem", ""
        )

        connection = None
        cursor = None

        try:

            # STEP 1: READ MONTHLY INCOME

            monthly_income = float(
                request.form.get("monthly_income") or 0
            )

            if monthly_income <= 0:

                error = "Please enter a valid monthly income."

            else:

                annual_income = monthly_income * 12

                # STEP 2: READ MONTHLY EXPENSES

                categories = {
                    "Shopping": float(
                        request.form.get("shopping") or 0
                    ),
                    "Dining": float(
                        request.form.get("dining") or 0
                    ),
                    "Travel": float(
                        request.form.get("travel") or 0
                    ),
                    "Fuel": float(
                        request.form.get("fuel") or 0
                    )
                }

                # Optional dedicated inputs for HDFC Millennia.
                # These fields can be added to the advisor form later.

                eligible_merchant_spending = float(
                    request.form.get(
                        "eligible_merchant_spending"
                    ) or 0
                )

                other_eligible_spending = float(
                    request.form.get(
                        "other_eligible_spending"
                    ) or 0
                )

                all_entered_amounts = (
                    list(categories.values())
                    + [
                        eligible_merchant_spending,
                        other_eligible_spending
                    ]
                )

                if any(
                    amount < 0
                    for amount in all_entered_amounts
                ):

                    error = "Expenses cannot be negative."

                else:

                    # STEP 3: DETECT SPENDING CATEGORIES

                    detected_categories = (
                        detect_spending_categories(
                            spending_problem
                        )
                    )

                    # STEP 4: CREATE SPENDING SUMMARY

                    spending_summary = {
                        category: amount
                        for category, amount in categories.items()
                        if amount > 0
                    }

                    if eligible_merchant_spending > 0:

                        spending_summary[
                            "HDFC eligible merchants"
                        ] = eligible_merchant_spending

                    if other_eligible_spending > 0:

                        spending_summary[
                            "Other eligible spends"
                        ] = other_eligible_spending

                    total_spending = (
                        sum(categories.values())
                        + eligible_merchant_spending
                        + other_eligible_spending
                    )

                    if total_spending <= 0:

                        if detected_categories:

                            error = (
                                "We identified your spending categories: "
                                + ", ".join(detected_categories)
                                + ". Please enter the monthly amounts "
                                "to calculate estimated rewards."
                            )

                        else:

                            error = (
                                "Please describe your spending or enter "
                                "at least one monthly expense."
                            )

                    else:

                        highest_category = max(
                            categories,
                            key=categories.get
                        )

                        # STEP 5: CONNECT TO MYSQL

                        connection = get_db_connection()

                        cursor = connection.cursor(
                            dictionary=True
                        )

                        # STEP 6: FETCH ONLY ACTIVE CARDS
                        # WITH VERIFIED BENEFITS.
                        #
                        # Sample and Unverified benefits
                        # cannot enter the recommendation engine.

                        cursor.execute(
                            """
                            SELECT
                                c.card_id,
                                c.card_name,
                                c.bank_name,
                                c.card_type,
                                c.annual_fee,
                                c.minimum_income,
                                c.description,
                                c.card_status,

                                b.benefit_category,
                                b.cashback_percentage,
                                b.reward_type,
                                b.reward_value,
                                b.reward_unit,
                                b.benefit_description,

                                rc.reward_cap,
                                rc.minimum_spend,
                                rc.spending_condition,
                                rc.exclusions

                            FROM credit_cards c

                            INNER JOIN card_benefits b
                                ON c.card_id = b.card_id

                            LEFT JOIN reward_conditions rc
                                ON b.benefit_id = rc.benefit_id

                            WHERE LOWER(c.card_status) = 'active'
                              AND LOWER(b.benefit_status) = 'verified'
                            """
                        )

                        rows = cursor.fetchall()

                        # STEP 7: PROCESS ELIGIBLE CARDS

                        card_results = {}

                        for row in rows:

                            card_id = row["card_id"]

                            minimum_income = (
                                row["minimum_income"]
                            )

                            # Check income eligibility
                            # when the requirement is available.

                            if (
                                minimum_income is not None
                                and annual_income < float(
                                    minimum_income
                                )
                            ):

                                continue

                            if card_id not in card_results:

                                card_results[card_id] = {

                                    "card_name": row["card_name"],

                                    "bank_name": row["bank_name"],

                                    "card_type": row["card_type"],

                                    "annual_fee": (
                                        float(row["annual_fee"])
                                        if row["annual_fee"] is not None
                                        else None
                                    ),

                                    "minimum_income": (
                                        float(minimum_income)
                                        if minimum_income is not None
                                        else None
                                    ),

                                    "eligibility_status": (
                                        "Meets stored income requirement"
                                        if minimum_income is not None
                                        else
                                        "Income requirement not available; "
                                        "confirm with issuer"
                                    ),

                                    "description": row["description"],

                                    "monthly_rewards": 0,

                                    "matched_categories": [],

                                    "reward_details": [],

                                    "has_calculable_cashback": False
                                }

                            # STEP 8: MATCH VERIFIED BENEFITS
                            # TO THE USER'S SPENDING.
                            #
                            # HDFC Millennia's 5% benefit is limited
                            # to its named eligible merchants.
                            # General Shopping is NOT automatically
                            # considered eligible merchant spending.

                            category = row["benefit_category"]

                            card_name = (
                                row["card_name"] or ""
                            ).strip().lower()

                            if card_name == "hdfc millennia":

                                if category == "Shopping":

                                    spend_amount = (
                                        eligible_merchant_spending
                                    )

                                    display_category = (
                                        "HDFC eligible merchants"
                                    )

                                elif category == "Other Eligible Spends":

                                    spend_amount = (
                                        other_eligible_spending
                                    )

                                    display_category = (
                                        "Other eligible spends"
                                    )

                                else:

                                    spend_amount = 0
                                    display_category = category

                            else:

                                spend_amount = categories.get(
                                    category,
                                    0
                                )

                                display_category = category

                            if spend_amount > 0:

                                reward_type = (
                                    row["reward_type"] or ""
                                ).strip().lower()

                                cashback_percentage = (
                                    row["cashback_percentage"]
                                )

                                if (
                                    reward_type == "cashback"
                                    and cashback_percentage is not None
                                ):

                                    percentage = float(
                                        cashback_percentage
                                    )

                                    minimum_spend = row.get(
                                        "minimum_spend"
                                    )

                                    if (
                                        minimum_spend is not None
                                        and spend_amount < float(
                                            minimum_spend
                                        )
                                    ):

                                        continue

                                    monthly_reward = (
                                        calculate_monthly_cashback(
                                            spending=spend_amount,
                                            percentage=percentage,
                                            reward_cap=row.get("reward_cap"),
                                            spending_condition=row.get(
                                                "spending_condition"
                                            ),
                                            reward_unit=row.get("reward_unit")
                                        )
                                    )

                                    card_results[card_id][
                                        "monthly_rewards"
                                    ] += monthly_reward

                                    card_results[card_id][
                                        "has_calculable_cashback"
                                    ] = True

                                    card_results[card_id][
                                        "reward_details"
                                    ].append({

                                        "category": display_category,

                                        "spending": spend_amount,

                                        "percentage": percentage,

                                        "reward": monthly_reward,

                                        "reward_type": row["reward_type"],

                                        "reward_cap": (
                                            float(row["reward_cap"])
                                            if row.get("reward_cap") is not None
                                            else None
                                        ),

                                        "spending_condition": (
                                            row.get("spending_condition")
                                        ),

                                        "exclusions": (
                                            row.get("exclusions")
                                        )
                                    })

                                else:

                                    # Points, miles and discounts are not
                                    # converted into rupees without a
                                    # verified conversion rule.

                                    card_results[card_id][
                                        "reward_details"
                                    ].append({

                                        "category": display_category,

                                        "spending": spend_amount,

                                        "percentage": None,

                                        "reward": None,

                                        "reward_type": row["reward_type"],

                                        "benefit_description": (
                                            row["benefit_description"]
                                        ),

                                        "spending_condition": (
                                            row.get("spending_condition")
                                        ),

                                        "exclusions": (
                                            row.get("exclusions")
                                        )
                                    })

                                card_results[card_id][
                                    "matched_categories"
                                ].append(display_category)

                        # STEP 9: CALCULATE ANNUAL REWARDS

                        for card in card_results.values():

                            if card["matched_categories"]:

                                if card["has_calculable_cashback"]:

                                    annual_rewards = (
                                        card["monthly_rewards"] * 12
                                    )

                                    card["annual_rewards"] = (
                                        annual_rewards
                                    )

                                    card["estimated_annual_rewards"] = (
                                        annual_rewards
                                    )

                                    # Unknown annual fees are not
                                    # treated as zero.

                                    if card["annual_fee"] is not None:

                                        card[
                                            "estimated_annual_net_value"
                                        ] = (
                                            annual_rewards
                                            - card["annual_fee"]
                                        )

                                    else:

                                        card[
                                            "estimated_annual_net_value"
                                        ] = None

                                else:

                                    card["annual_rewards"] = None

                                    card[
                                        "estimated_annual_rewards"
                                    ] = None

                                    card[
                                        "estimated_annual_net_value"
                                    ] = None

                                card["reason"] = (
                                    "This active card has verified "
                                    "benefits matching your spending in "
                                    + ", ".join(
                                        sorted(
                                            set(
                                                card[
                                                    "matched_categories"
                                                ]
                                            )
                                        )
                                    )
                                    + "."
                                )

                                recommendations.append(card)

                        # STEP 10: SORT RECOMMENDATIONS

                        recommendations.sort(
                            key=lambda card: (
                                card[
                                    "estimated_annual_net_value"
                                ] is not None,

                                card[
                                    "estimated_annual_net_value"
                                ]
                                if card[
                                    "estimated_annual_net_value"
                                ] is not None
                                else 0
                            ),
                            reverse=True
                        )

                        no_verified_results = (
                            len(recommendations) == 0
                        )

        except ValueError:

            error = (
                "Please enter valid numerical amounts."
            )

        except mysql.connector.Error as database_error:

            app.logger.exception(
                "Advisor database error"
            )

            error = f"Database Error: {database_error}"

        except Exception:

            app.logger.exception(
                "Unexpected advisor error"
            )

            error = (
                "An unexpected error occurred. "
                "Check the Flask terminal."
            )

        finally:

            if cursor is not None:
                cursor.close()

            if (
                connection is not None
                and connection.is_connected()
            ):

                connection.close()

    return render_template(
        "advisor.html",
        recommendations=recommendations,
        recommended_cards=recommendations,
        error=error,
        spending_summary=spending_summary,
        total_spending=total_spending,
        highest_category=highest_category,
        spending_problem=spending_problem,
        detected_categories=detected_categories,
        no_verified_results=no_verified_results,
        annual_projection_note=(
            "Annual rewards are an estimate assuming the same eligible "
            "spending and monthly reward conditions repeat for 12 months."
        )
    )


# ==========================================
# SMART DASHBOARD / REST API INTEGRATION
# ==========================================

from backend.app import extend_app  # noqa: E402

extend_app(app)


# ==========================================
# RUN FLASK APPLICATION
# ==========================================

if __name__ == "__main__":
    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=True,
    )