-- ============================================================
-- SmartCredit Card Management System - DBMS demo queries
-- Run after: python -m backend.migrate --init-db
-- ============================================================

-- 1. Basic SELECT, WHERE, ORDER BY and LIMIT
SELECT card_id, card_name, bank_name, card_type, annual_fee
FROM credit_cards
WHERE LOWER(card_status) = 'active'
ORDER BY annual_fee ASC, card_name ASC
LIMIT 10;

-- 2. INNER JOIN: cards with their verified benefits
SELECT c.card_name, c.bank_name, b.benefit_category,
       b.cashback_percentage, b.reward_value, b.reward_unit
FROM credit_cards c
JOIN card_benefits b ON b.card_id = c.card_id
WHERE LOWER(b.benefit_status) = 'verified'
ORDER BY c.card_name, b.benefit_category;

-- 3. Three-table JOIN: spending by card and category
SELECT cc.card_name, sc.category_name,
       t.merchant_name, t.amount, t.transaction_date
FROM transactions t
JOIN user_cards uc ON uc.user_card_id = t.user_card_id
JOIN credit_cards cc ON cc.card_id = uc.card_id
JOIN spending_categories sc ON sc.category_id = t.category_id
WHERE t.user_id = 1
ORDER BY t.transaction_date DESC;

-- 4. GROUP BY + aggregate functions
SELECT sc.category_name,
       COUNT(*) AS transactions,
       SUM(t.amount) AS total_spent,
       ROUND(AVG(t.amount), 2) AS average_spend,
       MAX(t.amount) AS highest_spend
FROM transactions t
JOIN spending_categories sc ON sc.category_id = t.category_id
WHERE t.user_id = 1
GROUP BY sc.category_name
ORDER BY total_spent DESC;

-- 5. HAVING filters grouped output
SELECT user_card_id, COUNT(*) AS txn_count, SUM(amount) AS total_spent
FROM transactions
GROUP BY user_card_id
HAVING COUNT(*) >= 2 AND SUM(amount) > 10000
ORDER BY total_spent DESC;

-- 6. Subquery: highest spend category for the current month
SELECT category_name, total_spent
FROM v_monthly_spending
WHERE user_id = 1
  AND spend_month = DATE_FORMAT(CURDATE(), '%Y-%m')
ORDER BY total_spent DESC
LIMIT 1;

-- 7. Nested subquery: cards with more verified benefits than the average card
SELECT card_id, card_name
FROM credit_cards c
WHERE (
    SELECT COUNT(*)
    FROM card_benefits b
    WHERE b.card_id = c.card_id
      AND LOWER(b.benefit_status) = 'verified'
) > (
    SELECT AVG(benefit_count)
    FROM (
        SELECT COUNT(*) AS benefit_count
        FROM card_benefits
        GROUP BY card_id
    ) counts
);

-- 8. Correlated subquery: catalogue cards with no data source yet
SELECT c.card_id, c.card_name
FROM credit_cards c
WHERE NOT EXISTS (
    SELECT 1
    FROM data_sources ds
    WHERE ds.card_id = c.card_id
);

-- 9. View usage: utilization and upcoming dues
SELECT card_number_masked, card_name, credit_limit,
       available_credit, used_credit, utilization_pct
FROM v_user_card_summary
WHERE user_id = 1
ORDER BY utilization_pct DESC;

SELECT card_name, bank_name, due_date,
       outstanding_amount, days_until_due
FROM v_upcoming_payments
WHERE user_id = 1
ORDER BY due_date ASC;

-- 10. INSERT with uniqueness check
INSERT INTO spending_categories (category_name, description)
SELECT 'Entertainment', 'Movies, games and subscriptions'
WHERE NOT EXISTS (
    SELECT 1 FROM spending_categories WHERE category_name = 'Entertainment'
);

-- 11. UPDATE with rollback-safe wrapper
START TRANSACTION;

UPDATE user_cards
SET available_credit = available_credit - 500
WHERE user_card_id = 1
  AND available_credit >= 500;

-- Inspect the change before committing.
SELECT user_card_id, available_credit FROM user_cards WHERE user_card_id = 1;

ROLLBACK;  -- Replace with COMMIT to keep the change.

-- 12. Real application transaction with COMMIT
START TRANSACTION;

SELECT available_credit
FROM user_cards
WHERE user_card_id = 1
FOR UPDATE;

INSERT INTO transactions (
    user_id, user_card_id, category_id, merchant_name, amount, transaction_date
)
SELECT 1, 1, category_id, 'Demo Book Store', 799, CURDATE()
FROM spending_categories
WHERE category_name = 'Shopping';

UPDATE user_cards
SET available_credit = available_credit - 799
WHERE user_card_id = 1;

COMMIT;

-- 13. DELETE with rollback-safe wrapper
START TRANSACTION;

DELETE FROM transactions
WHERE merchant_name = 'Demo Book Store';

SELECT ROW_COUNT() AS deleted_rows;

ROLLBACK;  -- Replace with COMMIT to actually delete the demo row.

-- 14. Payment effect on statement status
SELECT s.statement_id, s.total_due, s.amount_paid,
       s.total_due - s.amount_paid AS remaining, s.status
FROM statements s
WHERE s.user_card_id = 1;

SELECT p.payment_id, p.amount, p.payment_method, p.payment_date, p.status
FROM payments p
WHERE p.user_card_id = 1
ORDER BY p.payment_date DESC;
