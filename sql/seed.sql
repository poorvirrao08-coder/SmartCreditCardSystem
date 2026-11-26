-- ============================================================
-- Sample data for the Smart Credit Card Management System
-- Re-runnable: every INSERT is guarded by a NOT EXISTS check.
-- Demo login: demo@smartcard.local / Demo@12345
-- ============================================================

INSERT INTO issuers (issuer_name, issuer_code, country)
SELECT 'Demo Card Issuer', 'DEMO', 'India'
WHERE NOT EXISTS (SELECT 1 FROM issuers WHERE issuer_name = 'Demo Card Issuer');

INSERT INTO banks (bank_name, bank_code, country)
SELECT 'Demo Bank', 'DEMO', 'India'
WHERE NOT EXISTS (SELECT 1 FROM banks WHERE bank_name = 'Demo Bank');

INSERT INTO users (full_name, email, password_hash, phone, monthly_income)
SELECT 'Demo User', 'demo@smartcard.local', '{{DEMO_PASSWORD_HASH}}', '9876543210', 85000
WHERE NOT EXISTS (SELECT 1 FROM users WHERE email = 'demo@smartcard.local');

INSERT INTO spending_categories (category_name, description) SELECT 'Shopping', 'Retail and online purchases' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Shopping');
INSERT INTO spending_categories (category_name, description) SELECT 'Dining', 'Restaurants, cafes and food delivery' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Dining');
INSERT INTO spending_categories (category_name, description) SELECT 'Travel', 'Flights, hotels and transport' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Travel');
INSERT INTO spending_categories (category_name, description) SELECT 'Fuel', 'Petrol, diesel and EV charging' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Fuel');
INSERT INTO spending_categories (category_name, description) SELECT 'Groceries', 'Supermarkets and grocery stores' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Groceries');
INSERT INTO spending_categories (category_name, description) SELECT 'Entertainment', 'Movies, streaming and events' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Entertainment');
INSERT INTO spending_categories (category_name, description) SELECT 'Healthcare', 'Medicines and hospital bills' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Healthcare');
INSERT INTO spending_categories (category_name, description) SELECT 'Bills', 'Utilities and recurring bills' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Bills');
INSERT INTO spending_categories (category_name, description) SELECT 'Other', 'Miscellaneous spending' WHERE NOT EXISTS (SELECT 1 FROM spending_categories WHERE category_name='Other');

INSERT INTO benefit_categories (category_name, description) SELECT category_name, description FROM spending_categories WHERE NOT EXISTS (SELECT 1 FROM benefit_categories bc WHERE bc.category_name = spending_categories.category_name);

INSERT INTO credit_cards (bank_name, card_name, card_type, annual_fee, joining_fee, reward_rate, minimum_income, description, issuer_id, card_status)
SELECT 'Demo Bank', 'SC Demo Cashback Plus', 'Cashback', 999, 0, 5.00, 300000,
       'Demo card with 5% shopping cashback capped at Rs 500 per month.', i.issuer_id, 'Active'
FROM issuers i WHERE i.issuer_name='Demo Card Issuer'
  AND NOT EXISTS (SELECT 1 FROM credit_cards c WHERE c.card_name='SC Demo Cashback Plus');

INSERT INTO credit_cards (bank_name, card_name, card_type, annual_fee, joining_fee, reward_rate, minimum_income, description, issuer_id, card_status)
SELECT 'Demo Bank', 'SC Demo Travel Elite', 'Travel', 1999, 499, 3.00, 600000,
       'Demo travel card with capped cashback and convertible reward points.', i.issuer_id, 'Active'
FROM issuers i WHERE i.issuer_name='Demo Card Issuer'
  AND NOT EXISTS (SELECT 1 FROM credit_cards c WHERE c.card_name='SC Demo Travel Elite');

INSERT INTO credit_cards (bank_name, card_name, card_type, annual_fee, joining_fee, reward_rate, minimum_income, description, issuer_id, card_status)
SELECT 'Demo Bank', 'SC Demo Dining Rewards', 'Rewards', 499, 0, 4.00, 250000,
       'Demo dining card with 4% dining cashback and a monthly cap.', i.issuer_id, 'Active'
FROM issuers i WHERE i.issuer_name='Demo Card Issuer'
  AND NOT EXISTS (SELECT 1 FROM credit_cards c WHERE c.card_name='SC Demo Dining Rewards');

INSERT INTO credit_cards (bank_name, card_name, card_type, annual_fee, joining_fee, reward_rate, minimum_income, description, issuer_id, card_status)
SELECT 'Demo Bank', 'SC Demo Fuel Saver', 'Fuel', 299, 0, 2.00, 200000,
       'Demo fuel card with 2% cashback and merchant exclusions.', i.issuer_id, 'Active'
FROM issuers i WHERE i.issuer_name='Demo Card Issuer'
  AND NOT EXISTS (SELECT 1 FROM credit_cards c WHERE c.card_name='SC Demo Fuel Saver');

INSERT INTO card_benefits (card_id, benefit_category, cashback_percentage, reward_type, reward_value, reward_unit, benefit_description, benefit_status)
SELECT c.card_id, 'Shopping', 5.00, 'Cashback', NULL, 'INR', '5% cashback on eligible shopping, capped monthly.', 'Verified'
FROM credit_cards c WHERE c.card_name='SC Demo Cashback Plus'
  AND NOT EXISTS (SELECT 1 FROM card_benefits b WHERE b.card_id=c.card_id AND b.benefit_category='Shopping');

INSERT INTO card_benefits (card_id, benefit_category, cashback_percentage, reward_type, reward_value, reward_unit, benefit_description, benefit_status)
SELECT c.card_id, 'Dining', 2.00, 'Cashback', NULL, 'INR', '2% cashback on dining.', 'Verified'
FROM credit_cards c WHERE c.card_name='SC Demo Cashback Plus'
  AND NOT EXISTS (SELECT 1 FROM card_benefits b WHERE b.card_id=c.card_id AND b.benefit_category='Dining');

INSERT INTO card_benefits (card_id, benefit_category, cashback_percentage, reward_type, reward_value, reward_unit, benefit_description, benefit_status)
SELECT c.card_id, 'Travel', 3.00, 'Cashback', NULL, 'INR', '3% cashback on travel bookings.', 'Verified'
FROM credit_cards c WHERE c.card_name='SC Demo Travel Elite'
  AND NOT EXISTS (SELECT 1 FROM card_benefits b WHERE b.card_id=c.card_id AND b.benefit_category='Travel');

INSERT INTO card_benefits (card_id, benefit_category, cashback_percentage, reward_type, reward_value, reward_unit, benefit_description, benefit_status)
SELECT c.card_id, 'Shopping', NULL, 'Reward Points', 10, 'points', '10 reward points per Rs 100 on shopping.', 'Verified'
FROM credit_cards c WHERE c.card_name='SC Demo Travel Elite'
  AND NOT EXISTS (SELECT 1 FROM card_benefits b WHERE b.card_id=c.card_id AND b.benefit_category='Shopping');

INSERT INTO card_benefits (card_id, benefit_category, cashback_percentage, reward_type, reward_value, reward_unit, benefit_description, benefit_status)
SELECT c.card_id, 'Dining', 4.00, 'Cashback', NULL, 'INR', '4% cashback on restaurant dining.', 'Verified'
FROM credit_cards c WHERE c.card_name='SC Demo Dining Rewards'
  AND NOT EXISTS (SELECT 1 FROM card_benefits b WHERE b.card_id=c.card_id AND b.benefit_category='Dining');

INSERT INTO card_benefits (card_id, benefit_category, cashback_percentage, reward_type, reward_value, reward_unit, benefit_description, benefit_status)
SELECT c.card_id, 'Fuel', 2.00, 'Cashback', NULL, 'INR', '2% cashback at fuel stations.', 'Verified'
FROM credit_cards c WHERE c.card_name='SC Demo Fuel Saver'
  AND NOT EXISTS (SELECT 1 FROM card_benefits b WHERE b.card_id=c.card_id AND b.benefit_category='Fuel');

UPDATE card_benefits b
JOIN credit_cards c ON c.card_id = b.card_id
SET b.point_value = 0.25
WHERE c.card_name = 'SC Demo Travel Elite'
  AND b.reward_type = 'Reward Points';

INSERT INTO reward_conditions (benefit_id, reward_cap, minimum_spend, spending_condition, exclusions)
SELECT b.benefit_id, 500, 1000, 'Cashback capped per calendar month.', 'Gift cards, fuel, cash withdrawals'
FROM card_benefits b JOIN credit_cards c ON c.card_id=b.card_id
WHERE c.card_name='SC Demo Cashback Plus' AND b.benefit_category='Shopping'
  AND NOT EXISTS (SELECT 1 FROM reward_conditions rc WHERE rc.benefit_id=b.benefit_id);

INSERT INTO reward_conditions (benefit_id, reward_cap, minimum_spend, spending_condition, exclusions)
SELECT b.benefit_id, NULL, 500, 'No monthly cap.', 'Alcohol, gift cards'
FROM card_benefits b JOIN credit_cards c ON c.card_id=b.card_id
WHERE c.card_name='SC Demo Cashback Plus' AND b.benefit_category='Dining'
  AND NOT EXISTS (SELECT 1 FROM reward_conditions rc WHERE rc.benefit_id=b.benefit_id);

INSERT INTO reward_conditions (benefit_id, reward_cap, minimum_spend, spending_condition, exclusions)
SELECT b.benefit_id, 1000, 2000, 'Cashback capped per calendar month.', 'Gift cards, wallet loads'
FROM card_benefits b JOIN credit_cards c ON c.card_id=b.card_id
WHERE c.card_name='SC Demo Travel Elite' AND b.benefit_category='Travel'
  AND NOT EXISTS (SELECT 1 FROM reward_conditions rc WHERE rc.benefit_id=b.benefit_id);

INSERT INTO reward_conditions (benefit_id, reward_cap, minimum_spend, spending_condition, exclusions)
SELECT b.benefit_id, 1000, NULL, 'Points capped per calendar month.', 'Fuel, utilities'
FROM card_benefits b JOIN credit_cards c ON c.card_id=b.card_id
WHERE c.card_name='SC Demo Travel Elite' AND b.benefit_category='Shopping'
  AND NOT EXISTS (SELECT 1 FROM reward_conditions rc WHERE rc.benefit_id=b.benefit_id);

INSERT INTO reward_conditions (benefit_id, reward_cap, minimum_spend, spending_condition, exclusions)
SELECT b.benefit_id, 300, 500, 'Cashback capped per calendar month.', 'Food delivery apps'
FROM card_benefits b JOIN credit_cards c ON c.card_id=b.card_id
WHERE c.card_name='SC Demo Dining Rewards' AND b.benefit_category='Dining'
  AND NOT EXISTS (SELECT 1 FROM reward_conditions rc WHERE rc.benefit_id=b.benefit_id);

INSERT INTO reward_conditions (benefit_id, reward_cap, minimum_spend, spending_condition, exclusions)
SELECT b.benefit_id, 250, 300, 'Cashback capped per calendar month.', 'Amazon, groceries'
FROM card_benefits b JOIN credit_cards c ON c.card_id=b.card_id
WHERE c.card_name='SC Demo Fuel Saver' AND b.benefit_category='Fuel'
  AND NOT EXISTS (SELECT 1 FROM reward_conditions rc WHERE rc.benefit_id=b.benefit_id);

INSERT INTO user_cards (user_id, card_id, card_number_masked, cardholder_name, credit_limit, available_credit, billing_day, due_day, status)
SELECT u.user_id, c.card_id, '**** **** **** 4821', 'DEMO USER', 150000, 112500, 5, 25, 'active'
FROM users u JOIN credit_cards c ON c.card_name='SC Demo Cashback Plus'
WHERE u.email='demo@smartcard.local'
  AND NOT EXISTS (SELECT 1 FROM user_cards uc WHERE uc.user_id=u.user_id AND uc.card_number_masked='**** **** **** 4821');

INSERT INTO user_cards (user_id, card_id, card_number_masked, cardholder_name, credit_limit, available_credit, billing_day, due_day, status)
SELECT u.user_id, c.card_id, '**** **** **** 9007', 'DEMO USER', 200000, 180000, 12, 30, 'active'
FROM users u JOIN credit_cards c ON c.card_name='SC Demo Travel Elite'
WHERE u.email='demo@smartcard.local'
  AND NOT EXISTS (SELECT 1 FROM user_cards uc WHERE uc.user_id=u.user_id AND uc.card_number_masked='**** **** **** 9007');

INSERT INTO statements (user_card_id, statement_month, billing_date, due_date, total_due, amount_paid, status)
SELECT uc.user_card_id, DATE_FORMAT(CURDATE(), '%Y-%m-01'), DATE_FORMAT(CURDATE(), '%Y-%m-05'),
       DATE_FORMAT(CURDATE(), '%Y-%m-25'), 37500, 5000, 'open'
FROM user_cards uc JOIN users u ON u.user_id=uc.user_id
WHERE u.email='demo@smartcard.local' AND uc.card_number_masked='**** **** **** 4821'
  AND NOT EXISTS (SELECT 1 FROM statements s WHERE s.user_card_id=uc.user_card_id AND s.statement_month=DATE_FORMAT(CURDATE(), '%Y-%m-01'));

INSERT INTO transactions (user_id, user_card_id, category_id, merchant_name, amount, transaction_date, description, status)
SELECT u.user_id, uc.user_card_id, sc.category_id, 'Amazon India', 8499, DATE_SUB(CURDATE(), INTERVAL 2 DAY), 'Electronics purchase', 'posted'
FROM users u JOIN user_cards uc ON uc.user_id=u.user_id JOIN spending_categories sc ON sc.category_name='Shopping'
WHERE u.email='demo@smartcard.local' AND uc.card_number_masked='**** **** **** 4821'
  AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.user_id=u.user_id AND t.merchant_name='Amazon India' AND t.amount=8499);

INSERT INTO transactions (user_id, user_card_id, category_id, merchant_name, amount, transaction_date, description, status)
SELECT u.user_id, uc.user_card_id, sc.category_id, 'Blue Tokai Cafe', 1250, DATE_SUB(CURDATE(), INTERVAL 4 DAY), 'Coffee with team', 'posted'
FROM users u JOIN user_cards uc ON uc.user_id=u.user_id JOIN spending_categories sc ON sc.category_name='Dining'
WHERE u.email='demo@smartcard.local' AND uc.card_number_masked='**** **** **** 4821'
  AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.user_id=u.user_id AND t.merchant_name='Blue Tokai Cafe' AND t.amount=1250);

INSERT INTO transactions (user_id, user_card_id, category_id, merchant_name, amount, transaction_date, description, status)
SELECT u.user_id, uc.user_card_id, sc.category_id, 'Indigo Airlines', 15200, DATE_SUB(CURDATE(), INTERVAL 8 DAY), 'Flight to Delhi', 'posted'
FROM users u JOIN user_cards uc ON uc.user_id=u.user_id JOIN spending_categories sc ON sc.category_name='Travel'
WHERE u.email='demo@smartcard.local' AND uc.card_number_masked='**** **** **** 9007'
  AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.user_id=u.user_id AND t.merchant_name='Indigo Airlines' AND t.amount=15200);

INSERT INTO transactions (user_id, user_card_id, category_id, merchant_name, amount, transaction_date, description, status)
SELECT u.user_id, uc.user_card_id, sc.category_id, 'HP Petrol Pump', 3200, DATE_SUB(CURDATE(), INTERVAL 10 DAY), 'Fuel refill', 'posted'
FROM users u JOIN user_cards uc ON uc.user_id=u.user_id JOIN spending_categories sc ON sc.category_name='Fuel'
WHERE u.email='demo@smartcard.local' AND uc.card_number_masked='**** **** **** 4821'
  AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.user_id=u.user_id AND t.merchant_name='HP Petrol Pump' AND t.amount=3200);

INSERT INTO payments (user_card_id, statement_id, amount, payment_date, payment_method, reference_number, status, notes)
SELECT uc.user_card_id, s.statement_id, 5000, CURDATE(), 'upi', 'DEMOPAY0001', 'completed', 'Partial payment towards current statement'
FROM user_cards uc JOIN users u ON u.user_id=uc.user_id
JOIN statements s ON s.user_card_id=uc.user_card_id
WHERE u.email='demo@smartcard.local' AND uc.card_number_masked='**** **** **** 4821'
  AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.reference_number='DEMOPAY0001');

INSERT INTO payments (user_card_id, statement_id, amount, payment_date, payment_method, reference_number, status, notes)
SELECT uc.user_card_id, s.statement_id, 8000, DATE_ADD(CURDATE(), INTERVAL 2 DAY), 'net_banking', 'DEMOPAY0002', 'pending', 'Scheduled payment'
FROM user_cards uc JOIN users u ON u.user_id=uc.user_id
JOIN statements s ON s.user_card_id=uc.user_card_id
WHERE u.email='demo@smartcard.local' AND uc.card_number_masked='**** **** **** 4821'
  AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.reference_number='DEMOPAY0002');
