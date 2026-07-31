/*==============================================================
  TRANSFORM STAGING DATA INTO AR BUSINESS TABLES

  Source:
      STG_RETAIL_TRANSACTIONS

  Targets:
      PAYMENT_TERMS
      CUSTOMERS
      INVOICES
      INVOICE_LINES

  Business rules:
      1. Customer ID must be present.
      2. Cancelled invoices beginning with C are excluded.
      3. Quantity must be greater than zero.
      4. Unit price must be zero or greater.
      5. Default payment term is NET 30.
==============================================================*/

SET SERVEROUTPUT ON;


/*==============================================================
  STEP 1: CLEAR PREVIOUS NORMALIZED TEST DATA

  Child tables must be cleared before parent tables because of
  foreign-key relationships.
==============================================================*/

DELETE FROM payments;

DELETE FROM invoice_lines;

DELETE FROM invoices;

DELETE FROM customers;

COMMIT;


/*==============================================================
  STEP 2: CREATE OR UPDATE THE DEFAULT PAYMENT TERM
==============================================================*/

MERGE INTO payment_terms target
USING
(
    SELECT
        1        AS payment_term_id,
        'NET 30' AS term_name,
        30       AS due_days,
        'Payment is due within 30 days' AS description
    FROM dual
) source
ON (target.payment_term_id = source.payment_term_id)

WHEN MATCHED THEN
    UPDATE SET
        target.term_name   = source.term_name,
        target.due_days    = source.due_days,
        target.description = source.description

WHEN NOT MATCHED THEN
    INSERT
    (
        payment_term_id,
        term_name,
        due_days,
        description
    )
    VALUES
    (
        source.payment_term_id,
        source.term_name,
        source.due_days,
        source.description
    );

COMMIT;


/*==============================================================
  STEP 3: LOAD UNIQUE CUSTOMERS

  The source dataset does not contain customer names, email
  addresses, phone numbers, or industries. Therefore, we create
  a business-friendly generated customer name.
==============================================================*/

INSERT INTO customers
(
    customer_id,
    customer_name,
    customer_type,
    industry,
    email,
    phone,
    credit_limit,
    current_balance,
    risk_category
)
SELECT
    customer_id,
    'Retail Customer ' || TO_CHAR(customer_id) AS customer_name,
    'RETAIL'                                AS customer_type,
    'RETAIL'                                AS industry,
    NULL                                    AS email,
    NULL                                    AS phone,
    10000                                   AS credit_limit,
    0                                       AS current_balance,
    'LOW'                                   AS risk_category
FROM
(
    SELECT DISTINCT customer_id
    FROM stg_retail_transactions
    WHERE customer_id IS NOT NULL
);

COMMIT;


/*==============================================================
  STEP 4: LOAD ONE HEADER PER VALID INVOICE

  Invoice amount is calculated from all eligible lines belonging
  to the same invoice.
==============================================================*/

INSERT INTO invoices
(
    invoice_id,
    invoice_number,
    customer_id,
    payment_term_id,
    invoice_date,
    due_date,
    invoice_amount,
    amount_paid,
    outstanding_amount,
    invoice_status,
    dispute_flag,
    created_date
)
SELECT
    ROW_NUMBER() OVER
    (
        ORDER BY invoice_no
    ) AS invoice_id,

    invoice_no AS invoice_number,

    customer_id,

    1 AS payment_term_id,

    invoice_date,

    invoice_date + 30 AS due_date,

    invoice_amount,

    0 AS amount_paid,

    invoice_amount AS outstanding_amount,

    'OPEN' AS invoice_status,

    'N' AS dispute_flag,

    SYSDATE AS created_date
FROM
(
    SELECT
        invoice_no,
        customer_id,
        MIN(invoice_date) AS invoice_date,
        ROUND(
            SUM(quantity * unit_price),
            2
        ) AS invoice_amount
    FROM stg_retail_transactions
    WHERE customer_id IS NOT NULL
      AND invoice_no IS NOT NULL
      AND invoice_no NOT LIKE 'C%'
      AND quantity > 0
      AND unit_price >= 0
      AND invoice_date IS NOT NULL
    GROUP BY
        invoice_no,
        customer_id
)
WHERE invoice_amount >= 0;

COMMIT;


/*==============================================================
  STEP 5: LOAD VALID INVOICE LINES

  The join to INVOICES retrieves the generated invoice ID for
  each staging transaction.
==============================================================*/

INSERT INTO invoice_lines
(
    invoice_line_id,
    invoice_id,
    product_code,
    description,
    quantity,
    unit_price,
    line_amount
)
SELECT
    s.transaction_id AS invoice_line_id,

    i.invoice_id,

    SUBSTR(s.stock_code, 1, 50) AS product_code,

    SUBSTR(s.description, 1, 500) AS description,

    s.quantity,

    s.unit_price,

    ROUND(
        s.quantity * s.unit_price,
        2
    ) AS line_amount
FROM stg_retail_transactions s

JOIN invoices i
    ON i.invoice_number = s.invoice_no
   AND i.customer_id = s.customer_id

WHERE s.customer_id IS NOT NULL
  AND s.invoice_no IS NOT NULL
  AND s.invoice_no NOT LIKE 'C%'
  AND s.quantity > 0
  AND s.unit_price >= 0
  AND s.invoice_date IS NOT NULL;

COMMIT;


/*==============================================================
  STEP 6: UPDATE CUSTOMER CURRENT BALANCES

  Current balance equals the total outstanding invoice balance
  for each customer.
==============================================================*/

MERGE INTO customers customer
USING
(
    SELECT
        customer_id,
        ROUND(
            SUM(outstanding_amount),
            2
        ) AS current_balance
    FROM invoices
    GROUP BY customer_id
) invoice_totals

ON (customer.customer_id = invoice_totals.customer_id)

WHEN MATCHED THEN
    UPDATE SET
        customer.current_balance =
            invoice_totals.current_balance;

COMMIT;


/*==============================================================
  STEP 7: VALIDATION RESULTS
==============================================================*/

PROMPT ==========================================
PROMPT DAY 5 TRANSFORMATION RESULTS
PROMPT ==========================================

SELECT COUNT(*) AS customers_loaded
FROM customers;

SELECT COUNT(*) AS payment_terms_loaded
FROM payment_terms;

SELECT COUNT(*) AS invoices_loaded
FROM invoices;

SELECT COUNT(*) AS invoice_lines_loaded
FROM invoice_lines;

SELECT
    ROUND(
        SUM(invoice_amount),
        2
    ) AS total_invoice_amount
FROM invoices;

SELECT
    ROUND(
        SUM(line_amount),
        2
    ) AS total_line_amount
FROM invoice_lines;


/*==============================================================
  STEP 8: RECONCILIATION

  Invoice header total and invoice line total should match.
==============================================================*/

SELECT
    header_total,
    line_total,
    ROUND(
        header_total - line_total,
        2
    ) AS difference
FROM
(
    SELECT
        (
            SELECT NVL(SUM(invoice_amount), 0)
            FROM invoices
        ) AS header_total,

        (
            SELECT NVL(SUM(line_amount), 0)
            FROM invoice_lines
        ) AS line_total
    FROM dual
);


/*==============================================================
  STEP 9: SAMPLE BUSINESS REPORT
==============================================================*/

SELECT *
FROM
(
    SELECT
        c.customer_id,
        c.customer_name,
        COUNT(i.invoice_id) AS invoice_count,
        ROUND(
            SUM(i.invoice_amount),
            2
        ) AS total_invoice_amount,
        ROUND(
            SUM(i.outstanding_amount),
            2
        ) AS outstanding_amount
    FROM customers c

    JOIN invoices i
        ON i.customer_id = c.customer_id

    GROUP BY
        c.customer_id,
        c.customer_name

    ORDER BY
        outstanding_amount DESC
)
WHERE ROWNUM <= 10;