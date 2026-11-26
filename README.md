# SmartCredit Card Management System

A college DBMS project that manages credit cards, verified benefits, user cards, transactions, payments, credit tracking and intelligent card recommendations. Built with **Flask**, **MySQL** and **HTML/CSS/JavaScript**.

The project deliberately keeps the original `app.py` and its inserted catalogue data intact. New functionality is added through modular Flask blueprints and non-destructive SQL migrations.

---

## Features

- Card catalogue with issuer/bank details, fees, income eligibility and verified benefits.
- User registration/login with salted PBKDF2 password hashes and server-side sessions.
- Add, edit and delete user cards with masked card numbers and Luhn validation.
- Transaction entry and history with filters by card, category and month.
- Automatic available-credit and statement updates on transaction insert/update/delete.
- Payment tracking with due dates, statement settlement and credit restoration.
- Dashboard with credit utilization, category breakdown, spending trend and upcoming payments.
- Recommendation engine that compares cashback, reward points, caps, exclusions, annual fee and available credit.
- Existing recommendation/advisor pages from the original project remain available.
- REST JSON APIs for every module.
- Responsive dashboard UI built with plain CSS and vanilla JavaScript.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | HTML, CSS, JavaScript |
| Backend | Python 3, Flask |
| Database | MySQL 8+ |
| DB driver | mysql-connector-python |
| Auth | Flask sessions + PBKDF2 password hashing |

---

## Project structure

```text
SmartCreditCardSystem/
├── app.py                       # Original Flask app + legacy routes, extended with backend
├── app_before_advisor_rewards.py
├── backend/
│   ├── app.py                   # Blueprint registration, page routes, error handlers
│   ├── config.py                # Environment configuration
│   ├── db.py                    # MySQL connection/transaction helpers
│   ├── errors.py                # JSON API errors
│   ├── security.py              # Hashing, sessions, auth guards
│   ├── validation.py            # Validation, masking, serialization
│   ├── recommendation.py        # Recommendation algorithm
│   ├── migrate.py               # Non-destructive schema/seed runner
│   └── routes/                  # REST API blueprints
├── sql/
│   ├── schema.sql               # All tables, constraints, indexes, views
│   ├── seed.sql                 # Idempotent demo data
│   └── demo_queries.sql         # Queries for DBMS viva/demo
├── docs/
│   ├── API.md                   # REST API reference
│   └── DATABASE.md              # ER diagram, schema design, SQL concepts
├── templates/
│   ├── base.html                # Dashboard layout
│   ├── dashboard.html
│   ├── mycards.html
│   ├── transactions.html
│   ├── payments.html
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   └── index.html, cards.html, compare.html, recommend.html, advisor.html  # Legacy UI
├── static/
│   ├── css/dashboard.css
│   ├── js/app.js
│   └── style.css                # Original stylesheet
├── .env.example
└── requirements.txt
```

---

## Setup on MacBook

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure MySQL

Create a MySQL database and user:

```sql
CREATE DATABASE IF NOT EXISTS smart_credit_card;
CREATE USER IF NOT EXISTS 'smartcard_app'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON smart_credit_card.* TO 'smartcard_app'@'localhost';
FLUSH PRIVILEGES;
```

Copy `.env.example` to `.env` and update it:

```bash
cp .env.example .env
```

Example `.env`:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=smartcard_app
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=smart_credit_card
FLASK_SECRET_KEY=replace-with-a-long-random-string
```

### 3. Run migrations

```bash
python -m backend.migrate --init-db
```

This only creates missing tables/columns and inserts missing demo rows. It never drops existing tables or deletes existing card data.

To skip demo data:

```bash
python -m backend.migrate --init-db --skip-seed
```

### 4. Start Flask

```bash
python app.py
```

Open <http://127.0.0.1:5001/dashboard>. Port `5001` is used because macOS AirPlay Receiver often occupies `5000`; change `FLASK_PORT` in `.env` if needed.

Demo login:

```text
Email:    demo@smartcard.local
Password: Demo@12345
```

---

## API overview

All APIs are prefixed with `/api`. JSON is sent and returned except the page routes.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register` | Create user |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/me` | Current user |
| PUT | `/api/auth/profile` | Update profile |
| GET | `/api/cards/catalogue` | Card catalogue with aggregated benefits |
| GET/POST | `/api/cards` | List/add user cards |
| PUT/DELETE | `/api/cards/<id>` | Update/delete user card |
| GET | `/api/benefits` | List verified benefits |
| GET | `/api/benefit-categories` | Benefit category list |
| POST/PUT/DELETE | `/api/benefits/...` | Manage benefits |
| GET/POST | `/api/transactions` | List/add transactions |
| GET | `/api/transactions/summary` | Spending summary |
| PUT/DELETE | `/api/transactions/<id>` | Update/delete transaction |
| GET/POST | `/api/payments` | List/add payments |
| GET | `/api/payments/upcoming` | Upcoming dues |
| PUT/DELETE | `/api/payments/<id>` | Update/delete payment |
| GET | `/api/dashboard` | Dashboard data |
| GET | `/api/dashboard/utilization` | Credit utilization |
| GET | `/api/recommendation-categories` | Suggestion categories |
| POST | `/api/recommendations` | Best card recommendation |

See `docs/API.md` for full request/response details.

---

## SQL / DBMS concepts demonstrated

| Concept | Where used |
| --- | --- |
| CREATE TABLE, constraints | `sql/schema.sql` |
| PRIMARY KEY, FOREIGN KEY, UNIQUE | All relational tables |
| CHECK constraints | Credit limits, days, amounts, statuses |
| INDEXES | Card/category/date/amount lookups |
| INSERT, UPDATE, DELETE | `sql/seed.sql`, transaction/payment routes |
| SELECT with WHERE, ORDER BY, LIMIT | Catalogue, history, dashboard |
| GROUP BY, HAVING, COUNT, SUM, AVG, MAX | Views and dashboard summary |
| INNER/LEFT JOIN | User cards, catalogue, transactions, benefits |
| Subqueries / correlated subqueries | Dashboard suggested card and verification status |
| Views | `v_user_card_summary`, `v_monthly_spending`, `v_upcoming_payments`, `v_verified_benefits` |
| Transactions, COMMIT, ROLLBACK, FOR UPDATE | Transaction and payment mutation routes |
| Aggregation + date functions | Monthly spend, due dates, trends |
| Non-destructive migration | `backend/migrate.py` |

See `docs/DATABASE.md` and `sql/demo_queries.sql`.

---

## Notes about existing data

- Original `issuers`, `credit_cards`, `card_benefits`, `reward_conditions` and `data_sources` rows are preserved.
- New columns `card_benefits.point_value` and `credit_cards.bank_id` are added only if absent.
- New tables (`users`, `banks`, `user_cards`, `statements`, `transactions`, `payments`, category tables) are created only if absent.
- Demo data is idempotent: rerunning the migration does not duplicate it.
