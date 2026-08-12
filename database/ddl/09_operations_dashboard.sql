/* ============================================================
    OPERATIONS DASHBOARD
   ============================================================ */


/* ============================================================
   1. NOTIFICATION STATUS SUMMARY
   ============================================================ */

SELECT
    notification_status,
    COUNT(*) AS notification_count
FROM agent_notification_outbox
GROUP BY notification_status
ORDER BY notification_status;


/* ============================================================
   2. OVERALL NOTIFICATION METRICS
   ============================================================ */

SELECT
    COUNT(*) AS total_notifications,

    SUM(
        CASE
            WHEN notification_status = 'PENDING'
            THEN 1
            ELSE 0
        END
    ) AS pending_count,

    SUM(
        CASE
            WHEN notification_status = 'PROCESSING'
            THEN 1
            ELSE 0
        END
    ) AS processing_count,

    SUM(
        CASE
            WHEN notification_status = 'SENT'
            THEN 1
            ELSE 0
        END
    ) AS sent_count,

    SUM(
        CASE
            WHEN notification_status = 'RETRY'
            THEN 1
            ELSE 0
        END
    ) AS retry_count,

    SUM(
        CASE
            WHEN notification_status = 'DEAD'
            THEN 1
            ELSE 0
        END
    ) AS dead_count

FROM agent_notification_outbox;


/* ============================================================
   3. RECENT NOTIFICATIONS
   ============================================================ */

SELECT
    notification_id,
    approval_id,
    notification_type,
    recipient_address,
    subject_text,
    notification_status,
    retry_count,
    created_at,
    processed_at
FROM agent_notification_outbox
ORDER BY created_at DESC
FETCH FIRST 20 ROWS ONLY;


/* ============================================================
   4. RECENT FAILURES
   ============================================================ */

SELECT
    notification_id,
    approval_id,
    recipient_address,
    notification_status,
    retry_count,
    max_retry_count,
    failure_reason,
    error_message,
    next_retry_at,
    dead_at,
    updated_at
FROM agent_notification_outbox
WHERE notification_status IN
(
    'RETRY',
    'DEAD',
    'FAILED'
)
ORDER BY updated_at DESC;


/* ============================================================
   5. RECOVERY HISTORY
   ============================================================ */

SELECT
    recovery_id,
    notification_id,
    previous_status,
    new_status,
    recovered_by,
    recovery_reason,
    recovered_at
FROM agent_notification_recovery_log
ORDER BY recovered_at DESC
FETCH FIRST 20 ROWS ONLY;


/* ============================================================
   6. APPROVAL STATUS SUMMARY
   ============================================================ */

SELECT
    approval_status,
    COUNT(*) AS approval_count
FROM agent_approval_requests
GROUP BY approval_status
ORDER BY approval_status;


/* ============================================================
   7. RECENT APPROVAL ACTIVITY
   ============================================================ */

SELECT
    approval_id,
    conversation_id,
    action_type,
    action_description,
    approval_status,
    requested_at,
    reviewed_at,
    reviewed_by,
    executed_at,
    execution_status
FROM agent_approval_requests
ORDER BY requested_at DESC
FETCH FIRST 20 ROWS ONLY;


/* ============================================================
   8. END-TO-END OPERATIONS VIEW
   ============================================================ */

SELECT
    a.approval_id,
    a.action_type,
    a.approval_status,

    n.notification_id,
    n.notification_type,
    n.recipient_address,
    n.notification_status,
    n.retry_count,
    n.max_retry_count,
    n.failure_reason,
    n.created_at,
    n.processed_at

FROM agent_approval_requests a

LEFT JOIN agent_notification_outbox n
    ON n.approval_id = a.approval_id

ORDER BY a.approval_id DESC;


/* ============================================================
   DAY 20 COMPLETE
   ============================================================ */

COMMIT;