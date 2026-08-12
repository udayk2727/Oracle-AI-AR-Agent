from __future__ import annotations

from typing import Any

from agent_tool_client import get_connection


# ==============================================================
# HELPERS
# ==============================================================

def fetch_one_as_dict(
    cursor: Any,
) -> dict[str, Any] | None:
    """Convert one cursor row into a dictionary."""

    row = cursor.fetchone()

    if row is None:
        return None

    columns = [
        column[0]
        for column in cursor.description
    ]

    return dict(
        zip(columns, row)
    )


def fetch_all_as_dicts(
    cursor: Any,
) -> list[dict[str, Any]]:
    """Convert all cursor rows into dictionaries."""

    columns = [
        column[0]
        for column in cursor.description
    ]

    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


# ==============================================================
# NOTIFICATION SUMMARY
# ==============================================================

def get_notification_summary(
    connection: Any,
) -> dict[str, Any]:
    """Return overall notification metrics."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
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
                ) AS dead_count,

                SUM(
                    CASE
                        WHEN notification_status = 'FAILED'
                        THEN 1
                        ELSE 0
                    END
                ) AS failed_count

            FROM agent_notification_outbox
            """
        )

        result = fetch_one_as_dict(
            cursor
        )

        if result is None:
            return {
                "TOTAL_NOTIFICATIONS": 0,
                "PENDING_COUNT": 0,
                "PROCESSING_COUNT": 0,
                "SENT_COUNT": 0,
                "RETRY_COUNT": 0,
                "DEAD_COUNT": 0,
                "FAILED_COUNT": 0,
            }

        return result

    finally:
        cursor.close()


# ==============================================================
# APPROVAL SUMMARY
# ==============================================================

def get_approval_summary(
    connection: Any,
) -> list[dict[str, Any]]:
    """Return approval counts grouped by status."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                approval_status,
                COUNT(*) AS approval_count
            FROM agent_approval_requests
            GROUP BY approval_status
            ORDER BY approval_status
            """
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# RECENT NOTIFICATIONS
# ==============================================================

def get_recent_notifications(
    connection: Any,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return recent notification activity."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
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
            FETCH FIRST :limit ROWS ONLY
            """,
            {
                "limit": limit,
            },
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# FAILURE LIST
# ==============================================================

def get_failures(
    connection: Any,
) -> list[dict[str, Any]]:
    """Return RETRY, DEAD, and FAILED notifications."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
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
            ORDER BY updated_at DESC
            """
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# RECOVERY HISTORY
# ==============================================================

def get_recovery_history(
    connection: Any,
) -> list[dict[str, Any]]:
    """Return notification recovery history."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
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
            FETCH FIRST 20 ROWS ONLY
            """
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# RECENT APPROVALS
# ==============================================================

def get_recent_approvals(
    connection: Any,
) -> list[dict[str, Any]]:
    """Return recent approval activity."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                approval_id,
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
            FETCH FIRST 20 ROWS ONLY
            """
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# END-TO-END OPERATIONS VIEW
# ==============================================================

def get_operations_view(
    connection: Any,
) -> list[dict[str, Any]]:
    """Return combined approval + notification lifecycle."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
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

            ORDER BY a.approval_id DESC
            FETCH FIRST 20 ROWS ONLY
            """
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# DISPLAY SUMMARY
# ==============================================================

def show_summary(
    connection: Any,
) -> None:
    """Display top-level operations metrics."""

    summary = get_notification_summary(
        connection
    )

    approvals = get_approval_summary(
        connection
    )

    print()
    print("=" * 72)
    print("ORACLE AI AR AGENT - OPERATIONS SUMMARY")
    print("=" * 72)

    print(
        f"Total Notifications : "
        f"{summary['TOTAL_NOTIFICATIONS'] or 0}"
    )

    print(
        f"Pending             : "
        f"{summary['PENDING_COUNT'] or 0}"
    )

    print(
        f"Processing          : "
        f"{summary['PROCESSING_COUNT'] or 0}"
    )

    print(
        f"Sent                : "
        f"{summary['SENT_COUNT'] or 0}"
    )

    print(
        f"Retry               : "
        f"{summary['RETRY_COUNT'] or 0}"
    )

    print(
        f"Dead                : "
        f"{summary['DEAD_COUNT'] or 0}"
    )

    print(
        f"Failed              : "
        f"{summary['FAILED_COUNT'] or 0}"
    )

    print()
    print("Approval Summary")
    print("-" * 72)

    if not approvals:
        print(
            "No approval records found."
        )

    else:
        for approval in approvals:
            print(
                f"{approval['APPROVAL_STATUS']:<15}"
                f": {approval['APPROVAL_COUNT']}"
            )

    print("=" * 72)


# ==============================================================
# DISPLAY RECENT NOTIFICATIONS
# ==============================================================

def show_recent(
    connection: Any,
) -> None:
    """Display recent notifications."""

    rows = get_recent_notifications(
        connection
    )

    print()
    print("=" * 90)
    print("RECENT NOTIFICATIONS")
    print("=" * 90)

    if not rows:
        print(
            "No notification records found."
        )
        return

    for row in rows:
        print()

        print(
            f"Notification ID : "
            f"{row['NOTIFICATION_ID']}"
        )

        print(
            f"Approval ID     : "
            f"{row['APPROVAL_ID']}"
        )

        print(
            f"Type            : "
            f"{row['NOTIFICATION_TYPE']}"
        )

        print(
            f"Recipient       : "
            f"{row['RECIPIENT_ADDRESS']}"
        )

        print(
            f"Subject         : "
            f"{row['SUBJECT_TEXT']}"
        )

        print(
            f"Status          : "
            f"{row['NOTIFICATION_STATUS']}"
        )

        print(
            f"Retry Count     : "
            f"{row['RETRY_COUNT']}"
        )

        print(
            f"Created At      : "
            f"{row['CREATED_AT']}"
        )

        print(
            f"Processed At    : "
            f"{row['PROCESSED_AT']}"
        )

        print("-" * 90)


# ==============================================================
# DISPLAY FAILURES
# ==============================================================

def show_failures(
    connection: Any,
) -> None:
    """Display retry/dead/failed notifications."""

    rows = get_failures(
        connection
    )

    print()
    print("=" * 90)
    print("NOTIFICATION FAILURES")
    print("=" * 90)

    if not rows:
        print(
            "No RETRY, DEAD, or FAILED "
            "notifications found."
        )
        return

    for row in rows:
        print()

        print(
            f"Notification ID : "
            f"{row['NOTIFICATION_ID']}"
        )

        print(
            f"Approval ID     : "
            f"{row['APPROVAL_ID']}"
        )

        print(
            f"Recipient       : "
            f"{row['RECIPIENT_ADDRESS']}"
        )

        print(
            f"Status          : "
            f"{row['NOTIFICATION_STATUS']}"
        )

        print(
            f"Retry Count     : "
            f"{row['RETRY_COUNT']}/"
            f"{row['MAX_RETRY_COUNT']}"
        )

        print(
            f"Failure Reason  : "
            f"{row['FAILURE_REASON']}"
        )

        print(
            f"Error Message   : "
            f"{row['ERROR_MESSAGE']}"
        )

        print(
            f"Next Retry At   : "
            f"{row['NEXT_RETRY_AT']}"
        )

        print(
            f"Dead At         : "
            f"{row['DEAD_AT']}"
        )

        print("-" * 90)


# ==============================================================
# DISPLAY RECOVERIES
# ==============================================================

def show_recoveries(
    connection: Any,
) -> None:
    """Display notification recovery history."""

    rows = get_recovery_history(
        connection
    )

    print()
    print("=" * 90)
    print("RECOVERY HISTORY")
    print("=" * 90)

    if not rows:
        print(
            "No recovery history found."
        )
        return

    for row in rows:
        print()

        print(
            f"Recovery ID     : "
            f"{row['RECOVERY_ID']}"
        )

        print(
            f"Notification ID : "
            f"{row['NOTIFICATION_ID']}"
        )

        print(
            f"Previous Status : "
            f"{row['PREVIOUS_STATUS']}"
        )

        print(
            f"New Status      : "
            f"{row['NEW_STATUS']}"
        )

        print(
            f"Recovered By    : "
            f"{row['RECOVERED_BY']}"
        )

        print(
            f"Reason          : "
            f"{row['RECOVERY_REASON']}"
        )

        print(
            f"Recovered At    : "
            f"{row['RECOVERED_AT']}"
        )

        print("-" * 90)


# ==============================================================
# DISPLAY APPROVALS
# ==============================================================

def show_approvals(
    connection: Any,
) -> None:
    """Display recent approval activity."""

    rows = get_recent_approvals(
        connection
    )

    print()
    print("=" * 90)
    print("RECENT APPROVAL ACTIVITY")
    print("=" * 90)

    if not rows:
        print(
            "No approval records found."
        )
        return

    for row in rows:
        print()

        print(
            f"Approval ID      : "
            f"{row['APPROVAL_ID']}"
        )

        print(
            f"Action           : "
            f"{row['ACTION_TYPE']}"
        )

        print(
            f"Description      : "
            f"{row['ACTION_DESCRIPTION']}"
        )

        print(
            f"Status           : "
            f"{row['APPROVAL_STATUS']}"
        )

        print(
            f"Requested At     : "
            f"{row['REQUESTED_AT']}"
        )

        print(
            f"Reviewed At      : "
            f"{row['REVIEWED_AT']}"
        )

        print(
            f"Reviewed By      : "
            f"{row['REVIEWED_BY']}"
        )

        print(
            f"Executed At      : "
            f"{row['EXECUTED_AT']}"
        )

        print(
            f"Execution Status : "
            f"{row['EXECUTION_STATUS']}"
        )

        print("-" * 90)


# ==============================================================
# DISPLAY END-TO-END VIEW
# ==============================================================

def show_operations_view(
    connection: Any,
) -> None:
    """Display approval and notification lifecycle."""

    rows = get_operations_view(
        connection
    )

    print()
    print("=" * 90)
    print("END-TO-END OPERATIONS VIEW")
    print("=" * 90)

    if not rows:
        print(
            "No operations records found."
        )
        return

    for row in rows:
        print()

        print(
            f"Approval ID         : "
            f"{row['APPROVAL_ID']}"
        )

        print(
            f"Action              : "
            f"{row['ACTION_TYPE']}"
        )

        print(
            f"Approval Status     : "
            f"{row['APPROVAL_STATUS']}"
        )

        print(
            f"Notification ID     : "
            f"{row['NOTIFICATION_ID']}"
        )

        print(
            f"Notification Type   : "
            f"{row['NOTIFICATION_TYPE']}"
        )

        print(
            f"Recipient           : "
            f"{row['RECIPIENT_ADDRESS']}"
        )

        print(
            f"Notification Status : "
            f"{row['NOTIFICATION_STATUS']}"
        )

        print(
            f"Retry Count         : "
            f"{row['RETRY_COUNT']}"
        )

        print(
            f"Max Retry Count     : "
            f"{row['MAX_RETRY_COUNT']}"
        )

        print(
            f"Failure Reason      : "
            f"{row['FAILURE_REASON']}"
        )

        print(
            f"Created At          : "
            f"{row['CREATED_AT']}"
        )

        print(
            f"Processed At        : "
            f"{row['PROCESSED_AT']}"
        )

        print("-" * 90)


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:
    print("=" * 72)
    print("Oracle AI Accounts Receivable Agent")
    print("Day 20 - Operations Dashboard")
    print("=" * 72)

    print(
        "\nCommands:"
        "\n  summary       Show overall operations summary"
        "\n  recent        Show recent notifications"
        "\n  failures      Show retry/dead/failed notifications"
        "\n  recoveries    Show notification recovery history"
        "\n  approvals     Show recent approval activity"
        "\n  operations    Show end-to-end lifecycle"
        "\n  refresh       Refresh summary"
        "\n  exit          Close dashboard"
    )

    connection = get_connection()

    try:
        while True:
            command = input(
                "\nDashboard> "
            ).strip().lower()

            if not command:
                continue

            # ==================================================
            # SUMMARY
            # ==================================================

            if command == "summary":
                show_summary(
                    connection
                )
                continue

            # ==================================================
            # RECENT
            # ==================================================

            if command == "recent":
                show_recent(
                    connection
                )
                continue

            # ==================================================
            # FAILURES
            # ==================================================

            if command == "failures":
                show_failures(
                    connection
                )
                continue

            # ==================================================
            # RECOVERIES
            # ==================================================

            if command == "recoveries":
                show_recoveries(
                    connection
                )
                continue

            # ==================================================
            # APPROVALS
            # ==================================================

            if command == "approvals":
                show_approvals(
                    connection
                )
                continue

            # ==================================================
            # OPERATIONS
            # ==================================================

            if command == "operations":
                show_operations_view(
                    connection
                )
                continue

            # ==================================================
            # REFRESH
            # ==================================================

            if command == "refresh":
                print()
                print(
                    "Dashboard refreshed."
                )

                show_summary(
                    connection
                )
                continue

            # ==================================================
            # EXIT
            # ==================================================

            if command in {
                "exit",
                "quit",
            }:
                print()
                print(
                    "Operations dashboard closed."
                )
                break

            print()
            print(
                f"Unknown command: {command}"
            )

            print(
                "Available commands: "
                "summary, recent, failures, "
                "recoveries, approvals, "
                "operations, refresh, exit"
            )

    except KeyboardInterrupt:
        print()
        print(
            "Dashboard interrupted."
        )

    finally:
        connection.close()

        print(
            "Oracle connection closed."
        )


# ==============================================================
# PROGRAM ENTRY POINT
# ==============================================================

if __name__ == "__main__":
    main()