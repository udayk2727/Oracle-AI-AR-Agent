from __future__ import annotations

from typing import Any

from agent_tool_client import get_connection


# ==============================================================
# GET DEAD NOTIFICATIONS
# ==============================================================

def get_dead_notifications(
    connection: Any,
) -> list[dict[str, Any]]:
    """Return all DEAD notifications."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                notification_id,
                approval_id,
                conversation_id,
                notification_type,
                recipient_address,
                subject_text,
                notification_status,
                retry_count,
                max_retry_count,
                failure_reason,
                error_message,
                dead_at
            FROM agent_notification_outbox
            WHERE notification_status = 'DEAD'
            ORDER BY dead_at
            """
        )

        columns = [
            column[0]
            for column in cursor.description
        ]

        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

    finally:
        cursor.close()


# ==============================================================
# GET ONE NOTIFICATION
# ==============================================================

def get_notification(
    connection: Any,
    notification_id: int,
) -> dict[str, Any] | None:
    """Return one notification by ID."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                notification_id,
                approval_id,
                conversation_id,
                notification_type,
                recipient_address,
                subject_text,
                message_body,
                notification_status,
                retry_count,
                max_retry_count,
                next_retry_at,
                failure_reason,
                error_message,
                dead_at,
                processed_at,
                created_at,
                updated_at
            FROM agent_notification_outbox
            WHERE notification_id = :notification_id
            """,
            {
                "notification_id": notification_id,
            },
        )

        row = cursor.fetchone()

        if row is None:
            return None

        columns = [
            column[0]
            for column in cursor.description
        ]

        notification = dict(
            zip(columns, row)
        )

        message_body = notification.get(
            "MESSAGE_BODY"
        )

        if hasattr(message_body, "read"):
            notification["MESSAGE_BODY"] = (
                message_body.read()
            )

        return notification

    finally:
        cursor.close()


# ==============================================================
# DISPLAY DEAD NOTIFICATIONS
# ==============================================================

def show_dead_notifications(
    connection: Any,
) -> None:
    """Display all DEAD notifications."""

    notifications = get_dead_notifications(
        connection
    )

    print()
    print("=" * 90)
    print("DEAD NOTIFICATIONS")
    print("=" * 90)

    if not notifications:
        print(
            "No DEAD notifications found."
        )
        print("=" * 90)
        return

    for notification in notifications:
        print()

        print(
            f"Notification ID : "
            f"{notification['NOTIFICATION_ID']}"
        )

        print(
            f"Approval ID     : "
            f"{notification['APPROVAL_ID']}"
        )

        print(
            f"Type            : "
            f"{notification['NOTIFICATION_TYPE']}"
        )

        print(
            f"Recipient       : "
            f"{notification['RECIPIENT_ADDRESS']}"
        )

        print(
            f"Subject         : "
            f"{notification['SUBJECT_TEXT']}"
        )

        print(
            f"Status          : "
            f"{notification['NOTIFICATION_STATUS']}"
        )

        print(
            f"Retry Count     : "
            f"{notification['RETRY_COUNT']}/"
            f"{notification['MAX_RETRY_COUNT']}"
        )

        print(
            f"Failure Reason  : "
            f"{notification['FAILURE_REASON']}"
        )

        print(
            f"Error Message   : "
            f"{notification['ERROR_MESSAGE']}"
        )

        print(
            f"Dead At         : "
            f"{notification['DEAD_AT']}"
        )

        print("-" * 90)


# ==============================================================
# INSPECT NOTIFICATION
# ==============================================================

def inspect_notification(
    connection: Any,
    notification_id: int,
) -> None:
    """Display full details for one notification."""

    notification = get_notification(
        connection,
        notification_id,
    )

    if notification is None:
        print()
        print(
            f"Notification {notification_id} "
            "was not found."
        )
        return

    print()
    print("=" * 90)
    print("NOTIFICATION INSPECTION")
    print("=" * 90)

    for key, value in notification.items():
        print(
            f"{key:<22}: {value}"
        )

    print("=" * 90)


# ==============================================================
# REQUEUE NOTIFICATION
# ==============================================================

def requeue_notification(
    connection: Any,
    notification_id: int,
    recovered_by: str = "AR_MANAGER",
    recovery_reason: str = (
        "Manual recovery from notification console."
    ),
) -> str:
    """
    Requeue a DEAD/FAILED/RETRY notification.

    The action is recorded in
    AGENT_NOTIFICATION_RECOVERY_LOG.
    """

    notification = get_notification(
        connection,
        notification_id,
    )

    if notification is None:
        raise ValueError(
            f"Notification {notification_id} "
            "was not found."
        )

    previous_status = str(
        notification["NOTIFICATION_STATUS"]
    ).upper()

    allowed_statuses = {
        "DEAD",
        "FAILED",
        "RETRY",
    }

    if previous_status not in allowed_statuses:
        raise ValueError(
            f"Notification {notification_id} is "
            f"{previous_status}. Only DEAD, FAILED, "
            "or RETRY notifications can be requeued."
        )

    cursor = connection.cursor()

    try:
        # ------------------------------------------------------
        # RESET NOTIFICATION
        # ------------------------------------------------------

        cursor.execute(
            """
            UPDATE agent_notification_outbox
            SET
                notification_status = 'PENDING',
                retry_count = 0,
                next_retry_at = NULL,
                failure_reason = NULL,
                error_message = NULL,
                dead_at = NULL,
                processed_at = NULL,
                updated_at = SYSTIMESTAMP
            WHERE notification_id = :notification_id
              AND notification_status = :previous_status
            """,
            {
                "notification_id": notification_id,
                "previous_status": previous_status,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Notification status changed "
                "before recovery."
            )

        # ------------------------------------------------------
        # AUDIT RECOVERY ACTION
        # ------------------------------------------------------

        recovery_id = cursor.var(
            int
        )

        cursor.execute(
            """
            INSERT INTO agent_notification_recovery_log
            (
                notification_id,
                previous_status,
                new_status,
                recovered_by,
                recovery_reason,
                recovered_at
            )
            VALUES
            (
                :notification_id,
                :previous_status,
                'PENDING',
                :recovered_by,
                :recovery_reason,
                SYSTIMESTAMP
            )
            RETURNING recovery_id INTO :recovery_id
            """,
            {
                "notification_id": notification_id,
                "previous_status": previous_status,
                "recovered_by": recovered_by,
                "recovery_reason": recovery_reason,
                "recovery_id": recovery_id,
            },
        )

        generated_recovery_id = int(
            recovery_id.getvalue()[0]
        )

        connection.commit()

        return (
            f"Notification {notification_id} "
            f"was requeued successfully. "
            f"{previous_status} -> PENDING. "
            f"Recovery ID: {generated_recovery_id}."
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()


# ==============================================================
# SHOW RECOVERY HISTORY
# ==============================================================

def show_recovery_history(
    connection: Any,
) -> None:
    """Display recovery audit history."""

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
            ORDER BY recovery_id
            """
        )

        rows = cursor.fetchall()

        print()
        print("=" * 90)
        print("NOTIFICATION RECOVERY HISTORY")
        print("=" * 90)

        if not rows:
            print(
                "No recovery history found."
            )
            print("=" * 90)
            return

        for row in rows:
            print()

            print(
                f"Recovery ID      : {row[0]}"
            )

            print(
                f"Notification ID  : {row[1]}"
            )

            print(
                f"Previous Status  : {row[2]}"
            )

            print(
                f"New Status       : {row[3]}"
            )

            print(
                f"Recovered By     : {row[4]}"
            )

            print(
                f"Recovery Reason  : {row[5]}"
            )

            print(
                f"Recovered At     : {row[6]}"
            )

            print("-" * 90)

    finally:
        cursor.close()


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:
    print("=" * 72)
    print("Oracle AI Accounts Receivable Agent")
    print("Day 19 - Notification Recovery Console")
    print("=" * 72)

    print(
        "\nCommands:"
        "\n  dead                         Show DEAD notifications"
        "\n  inspect <notification_id>    Inspect notification"
        "\n  requeue <notification_id>    Requeue failed notification"
        "\n  history                      Show recovery history"
        "\n  exit                         Close recovery console"
    )

    connection = get_connection()

    try:
        while True:
            command = input(
                "\nRecovery-Agent> "
            ).strip()

            if not command:
                continue

            command_lower = (
                command.lower()
            )

            # ==================================================
            # DEAD
            # ==================================================

            if command_lower == "dead":
                show_dead_notifications(
                    connection
                )
                continue

            # ==================================================
            # INSPECT
            # ==================================================

            if command_lower.startswith(
                "inspect "
            ):
                parts = command.split(
                    maxsplit=1
                )

                if len(parts) != 2:
                    print(
                        "\nUsage: inspect "
                        "<notification_id>"
                    )
                    continue

                try:
                    notification_id = int(
                        parts[1]
                    )

                except ValueError:
                    print(
                        "\nNotification ID "
                        "must be a number."
                    )
                    continue

                inspect_notification(
                    connection,
                    notification_id,
                )

                continue

            # ==================================================
            # REQUEUE
            # ==================================================

            if command_lower.startswith(
                "requeue "
            ):
                parts = command.split(
                    maxsplit=1
                )

                if len(parts) != 2:
                    print(
                        "\nUsage: requeue "
                        "<notification_id>"
                    )
                    continue

                try:
                    notification_id = int(
                        parts[1]
                    )

                except ValueError:
                    print(
                        "\nNotification ID "
                        "must be a number."
                    )
                    continue

                try:
                    result = requeue_notification(
                        connection,
                        notification_id,
                    )

                    print()
                    print(
                        "Agent:"
                    )

                    print(
                        result
                    )

                except Exception as error:
                    print()
                    print(
                        f"Recovery failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # HISTORY
            # ==================================================

            if command_lower == "history":
                show_recovery_history(
                    connection
                )
                continue

            # ==================================================
            # EXIT
            # ==================================================

            if command_lower in {
                "exit",
                "quit",
            }:
                print()
                print(
                    "Recovery console closed."
                )
                break

            print()
            print(
                f"Unknown command: "
                f"{command}"
            )

            print(
                "Available commands: "
                "dead, inspect, requeue, "
                "history, exit"
            )

    except KeyboardInterrupt:
        print()
        print(
            "Recovery console interrupted."
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