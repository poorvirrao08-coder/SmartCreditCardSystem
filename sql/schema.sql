-- ============================================================
-- Smart Credit Card Management System - MySQL schema (3NF)
-- Safe to run on an existing database: CREATE TABLE IF NOT EXISTS
-- never removes or replaces existing tables/rows.
-- ============================================================

-- ---------- Existing catalogue tables (compatible definitions) ----------

CREATE TABLE IF NOT EXISTS issuers (
    issuer_id   INT AUTO_INCREMENT PRIMARY KEY,
    issuer_name VARCHAR(150) NOT NULL,
    issuer_code VARCHAR(20) NULL,
    country     VARCHAR(60) DEFAULT 'India',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_issuer_name (issuer_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS credit_cards (
    card_id         INT AUTO_INCREMENT PRIMARY KEY,
    bank_name       VARCHAR(150) NOT NULL,
    card_name       VARCHAR(150) NOT NULL,
    card_type       VARCHAR(80) NULL,
    annual_fee      DECIMAL(10,2) NULL,
    joining_fee     DECIMAL(10,2) NULL,
    reward_rate     DECIMAL(6,2) NULL,
    minimum_income  DECIMAL(12,2) NULL,
    description     TEXT NULL,
    issuer_id       INT NULL,
    bank_id         INT NULL,
    card_status     VARCHAR(30) DEFAULT 'Unverified',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_credit_cards_issuer (issuer_id),
    KEY idx_credit_cards_status (card_status),
    CONSTRAINT fk_credit_cards_issuer FOREIGN KEY (issuer_id)
        REFERENCES issuers(issuer_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS card_benefits (
    benefit_id           INT AUTO_INCREMENT PRIMARY KEY,
    card_id              INT NOT NULL,
    benefit_category     VARCHAR(80) NULL,
    cashback_percentage  DECIMAL(6,2) NULL,
    reward_type          VARCHAR(40) NULL,
    reward_value         DECIMAL(12,2) NULL,
    reward_unit          VARCHAR(40) NULL,
    point_value          DECIMAL(10,4) NULL,
    benefit_description  TEXT NULL,
    benefit_status       VARCHAR(30) DEFAULT 'Sample',
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_benefits_card (card_id),
    KEY idx_benefits_category (benefit_category),
    CONSTRAINT fk_benefits_card FOREIGN KEY (card_id)
        REFERENCES credit_cards(card_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS reward_conditions (
    condition_id       INT AUTO_INCREMENT PRIMARY KEY,
    benefit_id         INT NOT NULL,
    reward_cap         DECIMAL(12,2) NULL,
    minimum_spend      DECIMAL(12,2) NULL,
    spending_condition VARCHAR(255) NULL,
    exclusions         TEXT NULL,
    KEY idx_reward_conditions_benefit (benefit_id),
    CONSTRAINT fk_reward_conditions_benefit FOREIGN KEY (benefit_id)
        REFERENCES card_benefits(benefit_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS data_sources (
    source_id     INT AUTO_INCREMENT PRIMARY KEY,
    card_id       INT NOT NULL,
    source_url    VARCHAR(500) NOT NULL,
    source_type   VARCHAR(100) NULL,
    last_verified DATE NULL,
    KEY idx_data_sources_card (card_id),
    CONSTRAINT fk_data_sources_card FOREIGN KEY (card_id)
        REFERENCES credit_cards(card_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- New normalised tables ----------

CREATE TABLE IF NOT EXISTS banks (
    bank_id     INT AUTO_INCREMENT PRIMARY KEY,
    bank_name   VARCHAR(150) NOT NULL,
    bank_code   VARCHAR(20) NULL,
    country     VARCHAR(60) DEFAULT 'India',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_bank_name (bank_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
    user_id         INT AUTO_INCREMENT PRIMARY KEY,
    full_name       VARCHAR(120) NOT NULL,
    email           VARCHAR(190) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    phone           VARCHAR(20) NULL,
    monthly_income  DECIMAL(12,2) NULL,
    is_active       TINYINT(1) NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_users_email (email),
    CONSTRAINT chk_users_email CHECK (email <> '')
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS spending_categories (
    category_id   INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(80) NOT NULL,
    description   VARCHAR(255) NULL,
    parent_id     INT NULL,
    is_active     TINYINT(1) NOT NULL DEFAULT 1,
    UNIQUE KEY uq_spending_category_name (category_name),
    KEY idx_spending_category_parent (parent_id),
    CONSTRAINT fk_spending_category_parent FOREIGN KEY (parent_id)
        REFERENCES spending_categories(category_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS benefit_categories (
    benefit_category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name       VARCHAR(80) NOT NULL,
    description         VARCHAR(255) NULL,
    UNIQUE KEY uq_benefit_category_name (category_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS user_cards (
    user_card_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id           INT NOT NULL,
    card_id           INT NOT NULL,
    bank_id           INT NULL,
    card_number_masked VARCHAR(23) NOT NULL,
    cardholder_name   VARCHAR(120) NULL,
    credit_limit      DECIMAL(12,2) NOT NULL,
    available_credit  DECIMAL(12,2) NOT NULL,
    billing_day       TINYINT UNSIGNED NOT NULL DEFAULT 1,
    due_day           TINYINT UNSIGNED NOT NULL DEFAULT 20,
    status            ENUM('active','frozen','closed') NOT NULL DEFAULT 'active',
    added_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_card_number (user_id, card_number_masked),
    KEY idx_user_cards_user (user_id),
    KEY idx_user_cards_card (card_id),
    CONSTRAINT fk_user_cards_user FOREIGN KEY (user_id)
        REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_cards_card FOREIGN KEY (card_id)
        REFERENCES credit_cards(card_id) ON DELETE RESTRICT,
    CONSTRAINT fk_user_cards_bank FOREIGN KEY (bank_id)
        REFERENCES banks(bank_id) ON DELETE SET NULL,
    CONSTRAINT chk_user_card_credit CHECK (
        available_credit >= 0 AND available_credit <= credit_limit
    ),
    CONSTRAINT chk_user_card_days CHECK (
        billing_day BETWEEN 1 AND 28 AND due_day BETWEEN 1 AND 31
    )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS statements (
    statement_id     INT AUTO_INCREMENT PRIMARY KEY,
    user_card_id     INT NOT NULL,
    statement_month  DATE NOT NULL,
    billing_date     DATE NOT NULL,
    due_date         DATE NOT NULL,
    total_due        DECIMAL(12,2) NOT NULL DEFAULT 0,
    amount_paid      DECIMAL(12,2) NOT NULL DEFAULT 0,
    status           ENUM('open','paid','overdue') NOT NULL DEFAULT 'open',
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_statement_period (user_card_id, statement_month),
    KEY idx_statements_due (due_date),
    CONSTRAINT fk_statements_card FOREIGN KEY (user_card_id)
        REFERENCES user_cards(user_card_id) ON DELETE CASCADE,
    CONSTRAINT chk_statement_amounts CHECK (
        total_due >= 0 AND amount_paid >= 0
    )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id  INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    user_card_id    INT NOT NULL,
    category_id     INT NOT NULL,
    statement_id    INT NULL,
    merchant_name   VARCHAR(150) NOT NULL,
    amount          DECIMAL(12,2) NOT NULL,
    transaction_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description     VARCHAR(300) NULL,
    status          ENUM('pending','posted') NOT NULL DEFAULT 'posted',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_transactions_user_date (user_id, transaction_date),
    KEY idx_transactions_card_date (user_card_id, transaction_date),
    KEY idx_transactions_category (category_id),
    KEY idx_transactions_statement (statement_id),
    CONSTRAINT fk_transactions_user FOREIGN KEY (user_id)
        REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_transactions_card FOREIGN KEY (user_card_id)
        REFERENCES user_cards(user_card_id) ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_category FOREIGN KEY (category_id)
        REFERENCES spending_categories(category_id) ON DELETE RESTRICT,
    CONSTRAINT fk_transactions_statement FOREIGN KEY (statement_id)
        REFERENCES statements(statement_id) ON DELETE SET NULL,
    CONSTRAINT chk_transaction_amount CHECK (amount > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
    payment_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_card_id    INT NOT NULL,
    statement_id    INT NULL,
    amount          DECIMAL(12,2) NOT NULL,
    payment_date    DATE NOT NULL,
    payment_method  ENUM('net_banking','upi','card','cash','other') NOT NULL DEFAULT 'upi',
    reference_number VARCHAR(80) NULL,
    status          ENUM('pending','completed','failed') NOT NULL DEFAULT 'completed',
    notes           VARCHAR(300) NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_payment_reference (reference_number),
    KEY idx_payments_card_date (user_card_id, payment_date),
    KEY idx_payments_statement (statement_id),
    CONSTRAINT fk_payments_card FOREIGN KEY (user_card_id)
        REFERENCES user_cards(user_card_id) ON DELETE RESTRICT,
    CONSTRAINT fk_payments_statement FOREIGN KEY (statement_id)
        REFERENCES statements(statement_id) ON DELETE SET NULL,
    CONSTRAINT chk_payment_amount CHECK (amount > 0)
) ENGINE=InnoDB;

-- ---------- Views used by the dashboard ----------

CREATE OR REPLACE VIEW v_user_card_summary AS
SELECT
    uc.user_card_id,
    uc.user_id,
    uc.card_number_masked,
    uc.credit_limit,
    uc.available_credit,
    uc.credit_limit - uc.available_credit AS used_credit,
    ROUND((uc.credit_limit - uc.available_credit) / NULLIF(uc.credit_limit, 0) * 100, 2) AS utilization_pct,
    uc.billing_day,
    uc.due_day,
    uc.status,
    c.card_id,
    c.card_name,
    c.bank_name,
    c.card_type
FROM user_cards uc
JOIN credit_cards c ON c.card_id = uc.card_id;

CREATE OR REPLACE VIEW v_monthly_spending AS
SELECT
    t.user_id,
    DATE_FORMAT(t.transaction_date, '%Y-%m') AS spend_month,
    sc.category_id,
    sc.category_name,
    COUNT(*) AS transaction_count,
    SUM(t.amount) AS total_spent,
    AVG(t.amount) AS average_spend,
    MAX(t.amount) AS highest_spend,
    MIN(t.amount) AS lowest_spend
FROM transactions t
JOIN spending_categories sc ON sc.category_id = t.category_id
GROUP BY t.user_id, DATE_FORMAT(t.transaction_date, '%Y-%m'), sc.category_id, sc.category_name;

CREATE OR REPLACE VIEW v_upcoming_payments AS
SELECT
    s.statement_id,
    s.user_card_id,
    uc.user_id,
    c.card_name,
    c.bank_name,
    s.due_date,
    s.total_due - s.amount_paid AS outstanding_amount,
    s.status,
    DATEDIFF(s.due_date, CURDATE()) AS days_until_due
FROM statements s
JOIN user_cards uc ON uc.user_card_id = s.user_card_id
JOIN credit_cards c ON c.card_id = uc.card_id
WHERE LOWER(s.status) <> 'paid'
  AND s.due_date >= CURDATE() - INTERVAL 7 DAY;

CREATE OR REPLACE VIEW v_verified_benefits AS
SELECT
    c.card_id,
    c.card_name,
    c.bank_name,
    b.benefit_id,
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
JOIN card_benefits b ON b.card_id = c.card_id
LEFT JOIN reward_conditions rc ON rc.benefit_id = b.benefit_id
WHERE LOWER(c.card_status) = 'active'
  AND LOWER(b.benefit_status) = 'verified';
