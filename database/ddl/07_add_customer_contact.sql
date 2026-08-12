/* ============================================================
   RECIPIENT RESOLUTION SUPPORT
   ============================================================

   Existing schema already contains:

       CUSTOMERS.CUSTOMER_ID
       CUSTOMERS.EMAIL

       INVOICES.INVOICE_NUMBER
       INVOICES.CUSTOMER_ID

   No new customer email column is required.

   validates that invoice -> customer -> email
   recipient resolution is available.
   ============================================================ */


-- ============================================================
-- VERIFY CUSTOMER EMAIL DATA
-- ============================================================

SELECT
    customer_id,
    customer_name,
    email,
    status
FROM customers
ORDER BY customer_id;


-- ============================================================
-- VERIFY INVOICE TO CUSTOMER RELATIONSHIP
-- ============================================================

SELECT
    i.invoice_number,
    i.customer_id,
    c.customer_name,
    c.email
FROM invoices i
JOIN customers c
    ON c.customer_id = i.customer_id
FETCH FIRST 20 ROWS ONLY;


-- ============================================================
-- VERIFY ACTIVE CUSTOMERS WITH VALID RECIPIENTS
-- ============================================================

SELECT
    i.invoice_number,
    i.customer_id,
    c.customer_name,
    c.email AS recipient_address
FROM invoices i
JOIN customers c
    ON c.customer_id = i.customer_id
WHERE c.email IS NOT NULL
ORDER BY i.invoice_number
FETCH FIRST 20 ROWS ONLY;