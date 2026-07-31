/*==============================================================
  GENERATE SIMULATED AR PAYMENTS

  Rules:
    1. Every fifth invoice is fully paid.
    2. The next invoice receives a 50% partial payment.
    3. Remaining invoices stay unpaid.
    4. Invoice balances and statuses are recalculated.
==============================================================*/

SET SERVEROUTPUT ON;


/*--------------------------------------------------------------
  STEP 1: Clear previously generated payment data
--------------------------------------------------------------*/

DELETE FROM payments;

COMMIT;


/*--------------------------------------------------------------
  STEP 2: Reset invoices before recalculating payments
--------------------------------------------------------------*/

UPDATE invoices
SET
    amount_paid       = 0,
    outstanding_amount = invoice_amount,
    invoice_status     = 'OPEN';

COMMIT;


/*--------------------------------------------------------------
  STEP 3: Generate full and partial payments

  MOD(invoice_id, 5) = 0  → Full payment
  MOD(invoice_id, 5) = 1  → 50% payment
  Other invoices           → No payment
--------------------------------------------------------------*/

INSERT INTO payments
(
    payment_id,
    invoice_id,
    payment_date,
    payment_amount,
    payment_method,
    reference_number,
    created_date
)
SELECT
    ROW_NUMBER() OVER (
        ORDER BY invoice_id
    ) AS payment_id,

    invoice_id,

    invoice_date + MOD(invoice_id, 45) + 1 AS payment_date,

    CASE
        WHEN MOD(invoice_id, 5) = 0
            THEN invoice_amount
        WHEN MOD(invoice_id, 5) = 1
            THEN ROUND(invoice_amount * 0.50, 2)
    END AS payment_amount,

    CASE MOD(invoice_id, 4)
        WHEN 0 THEN 'ACH'
        WHEN 1 THEN 'CREDIT CARD'
        WHEN 2 THEN 'WIRE TRANSFER'
        ELSE 'CHECK'
    END AS payment_method,

    'PAY-' || LPAD(invoice_id, 10, '0') AS reference_number,

    SYSDATE AS created_date

FROM invoices

WHERE MOD(invoice_id, 5) IN (0, 1)
  AND invoice_amount > 0;

COMMIT;


/*--------------------------------------------------------------
  STEP 4: Update invoices using generated payment totals
--------------------------------------------------------------*/

MERGE INTO invoices invoice
USING
(
    SELECT
        invoice_id,
        ROUND(SUM(payment_amount), 2) AS total_paid
    FROM payments
    GROUP BY invoice_id
) payment_summary
ON (invoice.invoice_id = payment_summary.invoice_id)

WHEN MATCHED THEN
    UPDATE SET
        invoice.amount_paid = payment_summary.total_paid,
        invoice.outstanding_amount =
            GREATEST(
                ROUND(
                    invoice.invoice_amount
                    - payment_summary.total_paid,
                    2
                ),
                0
            ),
        invoice.invoice_status =
            CASE
                WHEN payment_summary.total_paid >= invoice.invoice_amount
                    THEN 'PAID'
                WHEN payment_summary.total_paid > 0
                    THEN 'PARTIALLY_PAID'
                ELSE 'OPEN'
            END;

COMMIT;

/*--------------------------------------------------------------
  STEP 5: Update customer balances
--------------------------------------------------------------*/

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
) balance_summary

ON (
    customer.customer_id =
    balance_summary.customer_id
)

WHEN MATCHED THEN
    UPDATE SET
        customer.current_balance =
            balance_summary.current_balance;

COMMIT;


/*--------------------------------------------------------------
  STEP 6: Validation
--------------------------------------------------------------*/

PROMPT ==========================================
PROMPT PAYMENT GENERATION RESULTS
PROMPT ==========================================

SELECT COUNT(*) AS payments_generated
FROM payments;


SELECT
    payment_method,
    COUNT(*) AS payment_count,
    ROUND(SUM(payment_amount), 2) AS total_paid
FROM payments
GROUP BY payment_method
ORDER BY payment_method;


SELECT
    invoice_status,
    COUNT(*) AS invoice_count,
    ROUND(SUM(invoice_amount), 2) AS invoice_amount,
    ROUND(SUM(amount_paid), 2) AS amount_paid,
    ROUND(SUM(outstanding_amount), 2) AS outstanding_amount
FROM invoices
GROUP BY invoice_status
ORDER BY invoice_status;


/*--------------------------------------------------------------
  STEP 7: Financial reconciliation

  Invoice amount must equal:
  Amount paid + Outstanding amount
--------------------------------------------------------------*/

SELECT COUNT(*) AS invalid_invoice_balances
FROM invoices
WHERE ROUND(invoice_amount, 2)
   <> ROUND(
          NVL(amount_paid, 0) +
          NVL(outstanding_amount, 0),
          2
      );


/*--------------------------------------------------------------
  STEP 8: Verify no orphan payments
--------------------------------------------------------------*/

SELECT COUNT(*) AS orphan_payments
FROM payments payment
WHERE NOT EXISTS
(
    SELECT 1
    FROM invoices invoice
    WHERE invoice.invoice_id =
          payment.invoice_id
);


/*--------------------------------------------------------------
  STEP 9: Sample payment report
--------------------------------------------------------------*/

SELECT *
FROM
(
    SELECT
        payment.payment_id,
        invoice.invoice_number,
        customer.customer_name,
        payment.payment_date,
        payment.payment_amount,
        payment.payment_method,
        payment.reference_number,
        invoice.invoice_status,
        invoice.outstanding_amount
    FROM payments payment

    JOIN invoices invoice
        ON invoice.invoice_id =
           payment.invoice_id

    JOIN customers customer
        ON customer.customer_id =
           invoice.customer_id

    ORDER BY
        payment.payment_amount DESC
)
WHERE ROWNUM <= 20;