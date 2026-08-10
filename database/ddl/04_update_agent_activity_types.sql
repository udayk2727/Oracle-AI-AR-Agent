ALTER TABLE agent_activity_log
DROP CONSTRAINT chk_agent_activity_type;


ALTER TABLE agent_activity_log
ADD CONSTRAINT chk_agent_activity_type
CHECK
(
    activity_type IN
    (
        'USER_MESSAGE',
        'TOOL_CALL',
        'AGENT_RESPONSE',
        'ERROR',
        'MEMORY_CLEAR',
        'SESSION_END',
        'APPROVAL_REQUEST',
        'APPROVAL_DECISION',
        'ACTION_EXECUTION'
    )
);