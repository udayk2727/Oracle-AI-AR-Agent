/* ============================================================
   DAY 17: NOTIFICATION RETRY + FAILURE RECOVERY
   ============================================================ */

ALTER TABLE agent_notification_outbox
ADD max_retry_count NUMBER DEFAULT 3 NOT NULL;

ALTER TABLE agent_notification_outbox
ADD next_retry_at TIMESTAMP;

ALTER TABLE agent_notification_outbox
ADD failure_reason VARCHAR2(4000);

ALTER TABLE agent_notification_outbox
ADD dead_at TIMESTAMP;


ALTER TABLE agent_notification_outbox
DROP CONSTRAINT chk_outbox_status;


ALTER TABLE agent_notification_outbox
ADD CONSTRAINT chk_outbox_status
CHECK
(
    notification_status IN
    (
        'PENDING',
        'PROCESSING',
        'SENT',
        'FAILED',
        'RETRY',
        'DEAD'
    )
);


CREATE INDEX idx_notification_retry
ON agent_notification_outbox
(
    notification_status,
    next_retry_at,
    retry_count
);

COMMIT;