from __future__ import annotations

from typing import Any

from agent_tool_client import get_connection


# ==============================================================
# GET NEXT PENDING NOTIFICATION
# ==============================================================

def get_next_pending_notification(
    connection: Any,
) -> dict[str, Any] | None:
    """Return the oldest pending notification."""

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
                created_at
            FROM agent_notification_outbox
            WHERE notification_status = 'PENDING'
            ORDER BY created_at
            FETCH FIRST 1 ROW ONLY
            """
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
# MARK PROCESSING
# ==============================================================

def mark_processing(
    connection: Any,
    notification_id: int,
) -> None:
    """Move notification from PENDING to PROCESSING."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE agent_notification_outbox
            SET
                notification_status = 'PROCESSING',
                updated_at = SYSTIMESTAMP,
                error_message = NULL
            WHERE notification_id = :notification_id
              AND notification_status = 'PENDING'
            """,
            {
                "notification_id": notification_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Notification is no longer PENDING."
            )

        connection.commit()

    finally:
        cursor.close()


# ==============================================================
# SIMULATE SENDING
# ==============================================================

def send_notification(
    notification: dict[str, Any],
) -> None:
    """
    Simulate sending the notification.

    A real email/SMS provider will be added later.
    """

    print()
    print("=" * 72)
    print("SIMULATED NOTIFICATION DELIVERY")
    print("=" * 72)

    print(
        f"Notification ID: "
        f"{notification['NOTIFICATION_ID']}"
    )

    print(
        f"Type: "
        f"{notification['NOTIFICATION_TYPE']}"
    )

    print(
        f"Recipient: "
        f"{notification['RECIPIENT_ADDRESS']}"
    )

    print(
        f"Subject: "
        f"{notification['SUBJECT_TEXT']}"
    )

    print()
    print("Message:")
    print(notification["MESSAGE_BODY"])

    print()
    print("Simulation completed successfully.")

    print("=" * 72)


# ==============================================================
# MARK SENT
# ==============================================================

def mark_sent(
    connection: Any,
    notification_id: int,
) -> None:
    """Mark a processed notification as SENT."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE agent_notification_outbox
            SET
                notification_status = 'SENT',
                processed_at = SYSTIMESTAMP,
                updated_at = SYSTIMESTAMP,
                error_message = NULL
            WHERE notification_id = :notification_id
              AND notification_status = 'PROCESSING'
            """,
            {
                "notification_id": notification_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Unable to mark notification as SENT."
            )

        connection.commit()

    finally:
        cursor.close()


# ==============================================================
# MARK FAILED
# ==============================================================

def mark_failed(
    connection: Any,
    notification_id: int,
    error_message: str,
) -> None:
    """Mark notification as FAILED and increment retry count."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE agent_notification_outbox
            SET
                notification_status = 'FAILED',
                retry_count = retry_count + 1,
                error_message = :error_message,
                processed_at = SYSTIMESTAMP,
                updated_at = SYSTIMESTAMP
            WHERE notification_id = :notification_id
            """,
            {
                "notification_id": notification_id,
                "error_message": error_message[:4000],
            },
        )

        connection.commit()

    finally:
        cursor.close()


# ==============================================================
# PROCESS ONE NOTIFICATION
# ==============================================================

def process_next_notification(
    connection: Any,
) -> bool:
    """Process the next pending notification."""

    notification = get_next_pending_notification(
        connection
    )

    if notification is None:
        print(
            "\nWorker: No PENDING notifications found."
        )
        return False

    notification_id = int(
        notification["NOTIFICATION_ID"]
    )

    print(
        f"\nWorker: Processing notification "
        f"{notification_id}..."
    )

    try:
        mark_processing(
            connection,
            notification_id,
        )

        print(
            "Worker: Status changed "
            "PENDING -> PROCESSING"
        )

        send_notification(
            notification
        )

        mark_sent(
            connection,
            notification_id,
        )

        print(
            f"\nWorker: Notification "
            f"{notification_id} sent successfully."
        )

        print(
            "Worker: Status changed "
            "PROCESSING -> SENT"
        )

        return True

    except Exception as error:
        mark_failed(
            connection,
            notification_id,
            str(error),
        )

        print(
            f"\nWorker: Notification "
            f"{notification_id} failed."
        )

        print(
            f"Error: {error}"
        )

        return False


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:
    print("=" * 72)
    print("Oracle AI Accounts Receivable Agent")
    print("Day 16 - Notification Worker")
    print("=" * 72)

    connection = get_connection()

    try:
        process_next_notification(
            connection
        )

    finally:
        connection.close()

        print(
            "\nWorker: Oracle connection closed."
        )


if __name__ == "__main__":
    main()