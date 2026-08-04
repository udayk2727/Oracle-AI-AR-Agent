SELECT
    c.customer_name,
    i.invoice_number,
    pt.term_name,
    i.invoice_date,
    i.due_date,
    il.product_code,
    il.description,
    il.quantity,
    il.unit_price,
    il.line_amount,
    p.payment_date,
    p.payment_amount
FROM customers c
JOIN invoices i
    ON c.customer_id = i.customer_id
JOIN payment_terms pt
    ON i.payment_term_id = pt.payment_term_id
JOIN invoice_lines il
    ON i.invoice_id = il.invoice_id
LEFT JOIN payments p
    ON i.invoice_id = p.invoice_id
WHERE i.invoice_number = 'TEST-INV-1001';
