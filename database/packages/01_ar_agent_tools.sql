CREATE OR REPLACE PACKAGE ar_agent_tools AS

    PROCEDURE get_customer_summary
    (
        p_customer_id IN customers.customer_id%TYPE,
        p_results     OUT SYS_REFCURSOR
    );

    PROCEDURE get_overdue_invoices
    (
        p_customer_id IN customers.customer_id%TYPE,
        p_results     OUT SYS_REFCURSOR
    );

    PROCEDURE get_collection_queue
    (
        p_priority IN VARCHAR2 DEFAULT NULL,
        p_results  OUT SYS_REFCURSOR
    );

    PROCEDURE get_invoice_details
    (
        p_invoice_number IN invoices.invoice_number%TYPE,
        p_results        OUT SYS_REFCURSOR
    );

END ar_agent_tools;
/

CREATE OR REPLACE PACKAGE BODY ar_agent_tools AS

    PROCEDURE validate_customer
    (
        p_customer_id IN customers.customer_id%TYPE
    )
    IS
        l_customer_count NUMBER;
    BEGIN
        SELECT COUNT(*)
        INTO l_customer_count
        FROM customers
        WHERE customer_id = p_customer_id;

        IF l_customer_count = 0 THEN
            RAISE_APPLICATION_ERROR(
                -20001,
                'Customer does not exist: ' || p_customer_id
            );
        END IF;
    END validate_customer;


    PROCEDURE get_customer_summary
    (
        p_customer_id IN customers.customer_id%TYPE,
        p_results     OUT SYS_REFCURSOR
    )
    IS
    BEGIN
        validate_customer(p_customer_id);

        OPEN p_results FOR
            SELECT *
            FROM vw_customer_risk_summary
            WHERE customer_id = p_customer_id;
    END get_customer_summary;


    PROCEDURE get_overdue_invoices
    (
        p_customer_id IN customers.customer_id%TYPE,
        p_results     OUT SYS_REFCURSOR
    )
    IS
    BEGIN
        validate_customer(p_customer_id);

        OPEN p_results FOR
            SELECT
                invoice_id,
                invoice_number,
                invoice_date,
                due_date,
                outstanding_amount,
                days_past_due,
                aging_bucket,
                collection_priority,
                recommended_action
            FROM vw_ar_aging_detail
            WHERE customer_id = p_customer_id
              AND days_past_due > 0
            ORDER BY
                days_past_due DESC,
                outstanding_amount DESC;
    END get_overdue_invoices;


    PROCEDURE get_collection_queue
    (
        p_priority IN VARCHAR2 DEFAULT NULL,
        p_results  OUT SYS_REFCURSOR
    )
    IS
    BEGIN
        OPEN p_results FOR
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
            WHERE p_priority IS NULL
               OR collection_priority = UPPER(p_priority)
            ORDER BY
                CASE collection_priority
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    WHEN 'LOW' THEN 4
                    ELSE 5
                END,
                outstanding_amount DESC;
    END get_collection_queue;


    PROCEDURE get_invoice_details
    (
        p_invoice_number IN invoices.invoice_number%TYPE,
        p_results        OUT SYS_REFCURSOR
    )
    IS
        l_invoice_count NUMBER;
    BEGIN
        SELECT COUNT(*)
        INTO l_invoice_count
        FROM invoices
        WHERE invoice_number = p_invoice_number;

        IF l_invoice_count = 0 THEN
            RAISE_APPLICATION_ERROR(
                -20002,
                'Invoice does not exist: ' || p_invoice_number
            );
        END IF;

        OPEN p_results FOR
            SELECT
                i.invoice_id,
                i.invoice_number,
                i.invoice_date,
                i.due_date,
                i.invoice_amount,
                i.amount_paid,
                i.outstanding_amount,
                i.invoice_status,
                c.customer_id,
                c.customer_name,
                a.days_past_due,
                a.aging_bucket,
                a.collection_priority,
                a.recommended_action
            FROM invoices i

            JOIN customers c
                ON c.customer_id = i.customer_id

            LEFT JOIN vw_ar_aging_detail a
                ON a.invoice_id = i.invoice_id

            WHERE i.invoice_number = p_invoice_number;
    END get_invoice_details;

END ar_agent_tools;
/