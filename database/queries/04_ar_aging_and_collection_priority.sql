/*==============================================================
  AR AGING AND COLLECTION PRIORITY

  Project:
      Oracle AI Accounts Receivable Agent

  Purpose:
      1. Calculate days past due.
      2. Assign AR aging buckets.
      3. Assign collection priorities.
      4. Recommend collection actions.
      5. Prepare agent-ready financial information.

  Note:
      The source dataset is historical, so the reporting date is
      based on the maximum invoice date plus 45 days.
==============================================================*/


/*==============================================================
  STEP 1: CREATE AN AGENT-READY AR AGING VIEW
==============================================================*/

CREATE OR REPLACE VIEW vw_ar_aging_detail AS
WITH reporting_parameters AS
(
    SELECT
        TRUNC(MAX(invoice_date)) + 45 AS as_of_date
    FROM invoices
),
aging_base AS
(
    SELECT
        i.invoice_id,
        i.invoice_number,
        i.customer_id,
        c.customer_name,
        i.invoice_date,
        i.due_date,
        i.invoice_amount,
        i.amount_paid,
        i.outstanding_amount,
        i.invoice_status,
        p.as_of_date,

        TRUNC(p.as_of_date) - TRUNC(i.due_date)
            AS raw_days_past_due

    FROM invoices i

    JOIN customers c
        ON c.customer_id = i.customer_id

    CROSS JOIN reporting_parameters p

    WHERE i.outstanding_amount > 0
),
aging_classification AS
(
    SELECT
        invoice_id,
        invoice_number,
        customer_id,
        customer_name,
        invoice_date,
        due_date,
        invoice_amount,
        amount_paid,
        outstanding_amount,
        invoice_status,
        as_of_date,

        GREATEST(raw_days_past_due, 0)
            AS days_past_due,

        CASE
            WHEN raw_days_past_due <= 0
                THEN 'CURRENT'

            WHEN raw_days_past_due BETWEEN 1 AND 30
                THEN '1-30 DAYS'

            WHEN raw_days_past_due BETWEEN 31 AND 60
                THEN '31-60 DAYS'

            WHEN raw_days_past_due BETWEEN 61 AND 90
                THEN '61-90 DAYS'

            ELSE '90+ DAYS'
        END AS aging_bucket

    FROM aging_base
)
SELECT
    invoice_id,
    invoice_number,
    customer_id,
    customer_name,
    invoice_date,
    due_date,
    as_of_date,
    invoice_amount,
    amount_paid,
    outstanding_amount,
    invoice_status,
    days_past_due,
    aging_bucket,

    CASE
        WHEN days_past_due > 90
             AND outstanding_amount >= 10000
            THEN 'CRITICAL'

        WHEN days_past_due > 90
            THEN 'HIGH'

        WHEN days_past_due BETWEEN 61 AND 90
            THEN 'HIGH'

        WHEN days_past_due BETWEEN 31 AND 60
            THEN 'MEDIUM'

        WHEN days_past_due BETWEEN 1 AND 30
            THEN 'LOW'

        ELSE 'MONITOR'
    END AS collection_priority,

    CASE
        WHEN days_past_due > 90
             AND outstanding_amount >= 10000
            THEN 'ESCALATE TO COLLECTIONS MANAGER'

        WHEN days_past_due > 90
            THEN 'CALL CUSTOMER AND REQUEST PAYMENT COMMITMENT'

        WHEN days_past_due BETWEEN 61 AND 90
            THEN 'MAKE COLLECTION CALL'

        WHEN days_past_due BETWEEN 31 AND 60
            THEN 'SEND SECOND PAYMENT REMINDER'

        WHEN days_past_due BETWEEN 1 AND 30
            THEN 'SEND FIRST PAYMENT REMINDER'

        ELSE 'MONITOR UNTIL DUE DATE'
    END AS recommended_action

FROM aging_classification;
/*==============================================================
  STEP 2: AGING BUCKET SUMMARY
==============================================================*/

SELECT
    aging_bucket,
    COUNT(*) AS invoice_count,
    ROUND(SUM(invoice_amount), 2) AS total_invoice_amount,
    ROUND(SUM(amount_paid), 2) AS total_paid,
    ROUND(SUM(outstanding_amount), 2) AS outstanding_amount
FROM vw_ar_aging_detail
GROUP BY aging_bucket
ORDER BY
    CASE aging_bucket
        WHEN 'CURRENT' THEN 1
        WHEN '1-30 DAYS' THEN 2
        WHEN '31-60 DAYS' THEN 3
        WHEN '61-90 DAYS' THEN 4
        WHEN '90+ DAYS' THEN 5
    END;
/*==============================================================
  STEP 3: TOP CUSTOMERS BY OVERDUE BALANCE
==============================================================*/

SELECT *
FROM
(
    SELECT
        customer_id,
        customer_name,
        COUNT(invoice_id) AS open_invoice_count,
        MAX(days_past_due) AS maximum_days_past_due,
        ROUND(SUM(outstanding_amount), 2)
            AS total_outstanding_amount,

        SUM(
            CASE
                WHEN aging_bucket = '90+ DAYS'
                    THEN outstanding_amount
                ELSE 0
            END
        ) AS amount_over_90_days

    FROM vw_ar_aging_detail

    GROUP BY
        customer_id,
        customer_name

    ORDER BY
        total_outstanding_amount DESC
)
WHERE ROWNUM <= 10;
/*==============================================================
  STEP 4: AI AGENT COLLECTION QUEUE
==============================================================*/

SELECT *
FROM
(
    SELECT
        invoice_id,
        invoice_number,
        customer_id,
        customer_name,
        outstanding_amount,
        days_past_due,
        aging_bucket,
        collection_priority,
        recommended_action
    FROM vw_ar_aging_detail
    ORDER BY
        CASE collection_priority
            WHEN 'CRITICAL' THEN 1
            WHEN 'HIGH' THEN 2
            WHEN 'MEDIUM' THEN 3
            WHEN 'LOW' THEN 4
            ELSE 5
        END,
        outstanding_amount DESC
)
WHERE ROWNUM <= 20;

/*==============================================================
  STEP 5: VALIDATION
==============================================================*/

SELECT COUNT(*) AS aging_invoice_count
FROM vw_ar_aging_detail;


SELECT COUNT(*) AS invalid_aging_rows
FROM vw_ar_aging_detail
WHERE outstanding_amount <= 0;


SELECT COUNT(*) AS missing_recommended_actions
FROM vw_ar_aging_detail
WHERE recommended_action IS NULL;


SELECT
    ROUND(SUM(outstanding_amount), 2)
        AS aging_view_outstanding
FROM vw_ar_aging_detail;


SELECT
    ROUND(SUM(outstanding_amount), 2)
        AS invoice_table_outstanding
FROM invoices
WHERE outstanding_amount > 0;