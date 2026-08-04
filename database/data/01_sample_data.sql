INSERT INTO customers
(
    customer_name,
    customer_type,
    industry,
    email,
    phone,
    credit_limit,
    risk_category
)
VALUES
(
    'Apex Manufacturing',
    'ENTERPRISE',
    'Manufacturing',
    'ar@apex.example',
    '713-555-0101',
    100000,
    'LOW'
);

COMMIT;

SELECT customer_id,
       customer_name
FROM customers;

SELECT *
FROM payment_terms;

INSERT INTO invoices
(
    invoice_number,
    customer_id,
    payment_term_id,
    invoice_date,
    due_date,
    invoice_amount,
    amount_paid,
    outstanding_amount
)
VALUES
(
    'TEST-INV-1001',
    1,
    1,
    DATE '2026-07-01',
    DATE '2026-07-31',
    1500,
    0,
    1500
);

COMMIT;

SELECT *
FROM invoices;

INSERT INTO invoice_lines
(
    invoice_id,
    product_code,
    description,
    quantity,
    unit_price,
    line_amount
)
VALUES
(
    1,
    'LAPTOP-001',
    'Business Laptop',
    1,
    1000,
    1000
);
INSERT INTO invoice_lines
(
    invoice_id,
    product_code,
    description,
    quantity,
    unit_price,
    line_amount
)
VALUES
(
    1,
    'MONITOR-001',
    'Office Monitor',
    2,
    250,
    500
);

COMMIT;

INSERT INTO payments
(
    invoice_id,
    payment_date,
    payment_amount,
    payment_method,
    reference_number
)
VALUES
(
    1,
    DATE '2026-07-20',
    500,
    'ACH',
    'TEST-PAY-1001'
);

COMMIT;