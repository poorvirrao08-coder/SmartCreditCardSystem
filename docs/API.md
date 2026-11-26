# REST API Reference

Base URL: `http://127.0.0.1:5000/api`

All request and response bodies are JSON. Errors use:

```json
{
  "success": false,
  "error": "Human readable message",
  "details": {}
}
```

Successful responses use `{"success": true, "data": ..., "message": "..."}` unless noted.

Protected endpoints require a logged-in session. Log in first with `POST /api/auth/login`.

---

## Authentication

### POST `/api/auth/register`

Creates a new user and an empty wallet.

```json
{
  "full_name": "Aarav Sharma",
  "email": "aarav@example.com",
  "password": "StrongPass123",
  "phone": "9876543210",
  "monthly_income": 75000
}
```

`201 Created`:

```json
{
  "success": true,
  "message": "Account created",
  "data": {"user_id": 3, "full_name": "Aarav Sharma", "email": "aarav@example.com", "monthly_income": 75000.0, "phone": "9876543210"}
}
```

### POST `/api/auth/login`

```json
{"email": "demo@smartcard.local", "password": "Demo@12345"}
```

`200 OK`:

```json
{
  "success": true,
  "message": "Logged in successfully",
  "data": {"user_id": 1, "full_name": "Demo User", "email": "demo@smartcard.local"}
}
```

### POST `/api/auth/logout`

`200 OK`: `{"success": true, "message": "Logged out"}`

### GET `/api/auth/me`

Protected. Returns current user profile.

### PUT `/api/auth/profile`

Protected. Any of `full_name`, `phone`, `monthly_income`, `credit_score` may be updated.

---

## Cards

### GET `/api/cards/catalogue`

Returns catalogue cards with aggregated verified benefits, min annual fee and available income requirement.

### GET `/api/cards`

Protected. Returns logged-in user's cards with utilization.

### POST `/api/cards`

Protected. Adds a card to the user's wallet.

```json
{
  "card_name": "HDFC Millennia Credit Card",
  "card_number": "4111111111111111",
  "cardholder_name": "AARAV SHARMA",
  "credit_limit": 150000,
  "billing_day": 5,
  "due_day": 25,
  "bank_name": "HDFC Bank",
  "card_type": "Cashback",
  "annual_fee": 1000
}
```

Only `card_name`, `card_number`, `cardholder_name` and `credit_limit` are required. The number is Luhn-checked and stored masked.

### PUT `/api/cards/<user_card_id>`

Protected. Updates limit, billing/due day, status or cardholder name. Changing the limit adjusts available credit by the same delta.

### DELETE `/api/cards/<user_card_id>`

Protected. Deletes related payments, transactions, statements and the user card.

---

## Benefits

### GET `/api/benefits`

Verified benefits with card, category, reward and condition details. Optional filters: `card_id`, `category`.

### GET `/api/benefit-categories`

Lists distinct benefit categories from cards, benefits and spending categories.

### POST `/api/benefits`

```json
{
  "card_id": 1,
  "benefit_category": "Shopping",
  "cashback_percentage": 5,
  "reward_type": "cashback",
  "benefit_status": "verified",
  "minimum_spend": 0,
  "maximum_benefit": 500,
  "cap_period": "monthly"
}
```

### PUT `/api/benefits/<benefit_id>`

Updates benefit fields and matching `reward_conditions`.

### DELETE `/api/benefits/<benefit_id>`

Deletes the benefit and its conditions.

---

## Transactions

### GET `/api/transactions`

Protected. Optional filters: `month=YYYY-MM`, `category=Shopping`, `card_id=1`.

### GET `/api/transactions/summary`

Protected. Returns aggregate spend/count per category and per card.

### POST `/api/transactions`

Protected. Uses a MySQL transaction with `SELECT ... FOR UPDATE`, decreases available credit, updates statement total and COMMITs. On any validation/DB failure it ROLLBACKs.

```json
{
  "user_card_id": 1,
  "amount": 2499,
  "category": "Shopping",
  "merchant_name": "Amazon India",
  "description": "Headphones",
  "transaction_date": "2026-11-20"
}
```

`category` and `merchant_name` are required; unknown categories are created automatically.

### PUT `/api/transactions/<transaction_id>`

Protected. Changing `amount` or `user_card_id` reverses the old effect and applies the new one inside one transaction.

### DELETE `/api/transactions/<transaction_id>`

Protected. Restores available credit and reduces statement total.

---

## Payments

### GET `/api/payments`

Protected. Payment history for the logged-in user.

### GET `/api/payments/upcoming`

Protected. Open statements with `days_until_due`, outstanding amount and due date.

### POST `/api/payments`

Protected. Adds a payment, restores available credit and marks the statement `paid` when fully settled.

```json
{
  "user_card_id": 1,
  "amount": 5000,
  "payment_date": "2026-11-20",
  "payment_method": "upi",
  "reference_number": "UPI123456"
}
```

### PUT `/api/payments/<payment_id>`

Protected. Reverts the old payment effect and applies the updated payment.

### DELETE `/api/payments/<payment_id>`

Protected. Removes the payment and restores the previous credit/statement state.

---

## Dashboard

### GET `/api/dashboard`

Protected. Example response:

```json
{
  "success": true,
  "data": {
    "credit": {"card_count": 2, "total_limit": 350000.0, "available_credit": 292500.0, "used_credit": 57500.0, "utilization": 16.43},
    "outstanding": 32500.0,
    "category_breakdown": [{"category_name": "Travel", "total_spent": 15200.0, "transactions": 1}],
    "spending_trend": [{"spend_month": "2026-11", "daily_spend": 28000.0}],
    "recent_transactions": [],
    "upcoming_payments": [],
    "suggested_card": {"card_name": "SC Demo Cashback Plus", "net_monthly_value": 166.75}
  }
}
```

### GET `/api/dashboard/utilization`

Protected. Per-card utilization percentages.

---

## Recommendations

### GET `/api/recommendation-categories`

Returns common suggestion categories.

### POST `/api/recommendations`

Public when not logged in; uses user cards when logged in.

```json
{"amount": 12000, "category": "Shopping", "merchant": "Amazon India"}
```

Returns `recommended`, `eligible_cards`, `ineligible_cards`, the normalized category and amount. The recommendation score is:

```text
expected_value = cashback + (points * point_value)
net_monthly_value = expected_value - (annual_fee / 12)
```

Caps, minimum spend, exclusions and available credit are checked before ranking.

---

## Page routes

| Route | Purpose |
| --- | --- |
| `/dashboard` | Dashboard UI |
| `/my-cards` | Wallet UI |
| `/transactions` | Transactions UI |
| `/payments` | Payments UI |
| `/profile` | Profile UI |
| `/login`, `/register`, `/logout` | Auth UI |
| `/`, `/cards`, `/compare`, `/recommend`, `/advisor` | Original legacy pages |
