/*==============================================================
  CUSTOMER COLLECTION SUMMARY VIEW

  Project:
      Oracle AI Accounts Receivable Agent

  Purpose:
      Create one trusted, agent-ready row per customer.
==============================================================*/

CREATE OR REPLACE VIEW vw_customer_collection_summary AS
SELECT
    c.customer_id,
    c.customer_name,

    COUNT(i.invoice_id) AS total_invoice_count,

    SUM(
        CASE
            WHEN i.outstanding_amount > 0
                THEN 1
            ELSE 0
        END
    ) AS open_invoice_count,

    ROUND(
        NVL(SUM(i.invoice_amount), 0),
        2
    ) AS total_invoiced,

    ROUND(
        NVL(SUM(i.amount_paid), 0),
        2
    ) AS total_paid,

    ROUND(
        NVL(SUM(i.outstanding_amount), 0),
        2
    ) AS total_outstanding,

    NVL(
        MAX(a.days_past_due),
        0
    ) AS maximum_days_past_due,

    ROUND(
        NVL(
            SUM(
                CASE
                    WHEN a.days_past_due > 0
                        THEN a.outstanding_amount
                    ELSE 0
                END
            ),
            0
        ),
        2
    ) AS overdue_amount,

    ROUND(
        NVL(
            SUM(
                CASE
                    WHEN a.aging_bucket = '90+ DAYS'
                        THEN a.outstanding_amount
                    ELSE 0
                END
            ),
            0
        ),
        2
    ) AS amount_over_90_days,

    SUM(
        CASE
            WHEN i.invoice_status = 'PARTIALLY_PAID'
                THEN 1
            ELSE 0
        END
    ) AS partially_paid_invoice_count,

    LEAST(
        100,

        CASE
            WHEN NVL(SUM(i.outstanding_amount), 0) >= 100000
                THEN 35
            WHEN NVL(SUM(i.outstanding_amount), 0) >= 50000
                THEN 30
            WHEN NVL(SUM(i.outstanding_amount), 0) >= 25000
                THEN 20
            WHEN NVL(SUM(i.outstanding_amount), 0) > 0
                THEN 10
            ELSE 0
        END

        +

        CASE
            WHEN NVL(MAX(a.days_past_due), 0) > 90
                THEN 35
            WHEN NVL(MAX(a.days_past_due), 0) BETWEEN 61 AND 90
                THEN 30
            WHEN NVL(MAX(a.days_past_due), 0) BETWEEN 31 AND 60
                THEN 20
            WHEN NVL(MAX(a.days_past_due), 0) BETWEEN 1 AND 30
                THEN 10
            ELSE 0
        END

        +

        CASE
            WHEN SUM(
                CASE
                    WHEN a.days_past_due > 0
                        THEN 1
                    ELSE 0
                END
            ) >= 10
                THEN 20
            WHEN SUM(
                CASE
                    WHEN a.days_past_due > 0
                        THEN 1
                    ELSE 0
                END
            ) >= 5
                THEN 15
            WHEN SUM(
                CASE
                    WHEN a.days_past_due > 0
                        THEN 1
                    ELSE 0
                END
            ) > 0
                THEN 5
            ELSE 0
        END

        +

        CASE
            WHEN SUM(
                CASE
                    WHEN i.invoice_status = 'PARTIALLY_PAID'
                        THEN 1
                    ELSE 0
                END
            ) >= 3
                THEN 10
            WHEN SUM(
                CASE
                    WHEN i.invoice_status = 'PARTIALLY_PAID'
                        THEN 1
                    ELSE 0
                END
            ) > 0
                THEN 5
            ELSE 0
        END
    ) AS risk_score

FROM customers c

LEFT JOIN invoices i
    ON i.customer_id = c.customer_id

LEFT JOIN vw_ar_aging_detail a
    ON a.invoice_id = i.invoice_id

GROUP BY
    c.customer_id,
    c.customer_name;

CREATE OR REPLACE VIEW vw_customer_risk_summary AS
SELECT
    customer_id,
    customer_name,
    total_invoice_count,
    open_invoice_count,
    total_invoiced,
    total_paid,
    total_outstanding,
    maximum_days_past_due,
    overdue_amount,
    amount_over_90_days,
    partially_paid_invoice_count,
    risk_score,

    CASE
        WHEN risk_score >= 80
            THEN 'CRITICAL'
        WHEN risk_score >= 60
            THEN 'HIGH'
        WHEN risk_score >= 40
            THEN 'MEDIUM'
        WHEN risk_score > 0
            THEN 'LOW'
        ELSE 'NO RISK'
    END AS risk_level,

    CASE
        WHEN risk_score >= 80
            THEN 'ESCALATE ACCOUNT AND REVIEW COLLECTION STRATEGY'
        WHEN risk_score >= 60
            THEN 'PRIORITIZE CUSTOMER FOR COLLECTION CALL'
        WHEN risk_score >= 40
            THEN 'SEND PAYMENT REMINDER AND MONITOR'
        WHEN risk_score > 0
            THEN 'MONITOR OUTSTANDING BALANCE'
        ELSE 'NO COLLECTION ACTION REQUIRED'
    END AS recommended_action

FROM vw_customer_collection_summary;