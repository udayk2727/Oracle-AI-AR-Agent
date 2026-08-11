from __future__ import annotations

from typing import Any

from agent_tool_client import get_connection


# ==============================================================
# GET NEXT RETRYABLE NOTIFICATION
# ==============================================================

def get_next_retryable_notification(
    connection: Any,
) -> dict[str, Any] | None:
    """
    Return the oldest notification that is eligible for processing.

    Eligible notifications:
    - PENDING
    - RETRY where NEXT_RETRY_AT has arrived
    """

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
                created_at
            FROM agent_notification_outbox
            WHERE
                (
                    notification_status = 'PENDING'
                    OR
                    (
                        notification_status = 'RETRY'
                        AND next_retry_at <= SYSTIMESTAMP
                    )
                )
                AND retry_count < max_retry_count
            ORDER BY
                created_at
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
# MARK NOTIFICATION AS PROCESSING
# ==============================================================

def mark_processing(
    connection: Any,
    notification_id: int,
) -> None:
    """
    Change notification status from
    PENDING/RETRY to PROCESSING.
    """

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
              AND notification_status IN ('PENDING', 'RETRY')
            """,
            {
                "notification_id": notification_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Notification could not be moved to PROCESSING."
            )

        connection.commit()

    finally:
        cursor.close()


# ==============================================================
# SIMULATE NOTIFICATION DELIVERY
# ==============================================================

def send_notification(
    notification: dict[str, Any],
) -> None:
    """
    Simulate sending a notification.

    For Day 17, a missing recipient intentionally causes
    a failure so we can test retry handling.
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
        f"Approval ID: "
        f"{notification['APPROVAL_ID']}"
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

    recipient = notification.get(
        "RECIPIENT_ADDRESS"
    )

    # ----------------------------------------------------------
    # DAY 17 FAILURE SIMULATION
    # ----------------------------------------------------------

    if not recipient:
        raise RuntimeError(
            "Recipient address is missing."
        )

    print(
        "Simulation completed successfully."
    )

    print("=" * 72)


# ==============================================================
# MARK NOTIFICATION AS SENT
# ==============================================================

def mark_sent(
    connection: Any,
    notification_id: int,
) -> None:
    """
    Mark a notification as successfully sent.
    """

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE agent_notification_outbox
            SET
                notification_status = 'SENT',
                processed_at = SYSTIMESTAMP,
                updated_at = SYSTIMESTAMP,
                next_retry_at = NULL,
                failure_reason = NULL,
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
# HANDLE FAILED DELIVERY
# ==============================================================

def handle_failure(
    connection: Any,
    notification_id: int,
    error_message: str,
) -> str:
    """
    Handle a failed notification attempt.

    If retries remain:
        PROCESSING -> RETRY

    If maximum retries reached:
        PROCESSING -> DEAD
    """

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                retry_count,
                max_retry_count
            FROM agent_notification_outbox
            WHERE notification_id = :notification_id
            """,
            {
                "notification_id": notification_id,
            },
        )

        row = cursor.fetchone()

        if row is None:
            raise RuntimeError(
                f"Notification {notification_id} was not found."
            )

        current_retry_count = int(
            row[0]
        )

        max_retry_count = int(
            row[1]
        )

        new_retry_count = (
            current_retry_count + 1
        )

        # ======================================================
        # MAXIMUM RETRIES REACHED
        # ======================================================

        if new_retry_count >= max_retry_count:
            cursor.execute(
                """
                UPDATE agent_notification_outbox
                SET
                    notification_status = 'DEAD',
                    retry_count = :retry_count,
                    failure_reason = :failure_reason,
                    error_message = :error_message,
                    dead_at = SYSTIMESTAMP,
                    processed_at = SYSTIMESTAMP,
                    next_retry_at = NULL,
                    updated_at = SYSTIMESTAMP
                WHERE notification_id = :notification_id
                """,
                {
                    "retry_count": new_retry_count,
                    "failure_reason": (
                        "Maximum retry count reached."
                    ),
                    "error_message": (
                        error_message[:4000]
                    ),
                    "notification_id": notification_id,
                },
            )

            connection.commit()

            return "DEAD"

        # ======================================================
        # RETRY LATER
        # ======================================================

        cursor.execute(
            """
            UPDATE agent_notification_outbox
            SET
                notification_status = 'RETRY',
                retry_count = :retry_count,
                failure_reason = :failure_reason,
                error_message = :error_message,
                next_retry_at =
                    SYSTIMESTAMP + INTERVAL '1' MINUTE,
                updated_at = SYSTIMESTAMP
            WHERE notification_id = :notification_id
              AND notification_status = 'PROCESSING'
            """,
            {
                "retry_count": new_retry_count,
                "failure_reason": (
                    "Notification delivery failed."
                ),
                "error_message": (
                    error_message[:4000]
                ),
                "notification_id": notification_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Unable to move notification to RETRY."
            )

        connection.commit()

        return "RETRY"

    finally:
        cursor.close()


# ==============================================================
# DISPLAY RETRY STATUS
# ==============================================================

def show_retry_status(
    connection: Any,
) -> None:
    """
    Display notification retry information.
    """

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                notification_id,
                notification_status,
                retry_count,
                max_retry_count,
                next_retry_at,
                failure_reason,
                error_message,
                dead_at
            FROM agent_notification_outbox
            ORDER BY notification_id
            """
        )

        rows = cursor.fetchall()

        print()
        print("=" * 90)
        print("NOTIFICATION RETRY STATUS")
        print("=" * 90)

        if not rows:
            print(
                "No notification records found."
            )

            print("=" * 90)
            return

        for row in rows:
            print()
            print(
                f"Notification ID : {row[0]}"
            )

            print(
                f"Status          : {row[1]}"
            )

            print(
                f"Retry Count     : "
                f"{row[2]}/{row[3]}"
            )

            print(
                f"Next Retry At   : {row[4]}"
            )

            print(
                f"Failure Reason  : {row[5]}"
            )

            print(
                f"Error Message   : {row[6]}"
            )

            print(
                f"Dead At         : {row[7]}"
            )

            print("-" * 90)

    finally:
        cursor.close()


# ==============================================================
# PROCESS NEXT NOTIFICATION
# ==============================================================

def process_next_notification(
    connection: Any,
) -> bool:
    """
    Process the next eligible notification.
    """

    notification = (
        get_next_retryable_notification(
            connection
        )
    )

    if notification is None:
        print()
        print(
            "Worker: No retryable notifications found."
        )

        return False

    notification_id = int(
        notification["NOTIFICATION_ID"]
    )

    current_status = str(
        notification["NOTIFICATION_STATUS"]
    )

    retry_count = int(
        notification["RETRY_COUNT"]
    )

    max_retry_count = int(
        notification["MAX_RETRY_COUNT"]
    )

    print()
    print("=" * 72)

    print(
        f"Worker: Processing notification "
        f"{notification_id}"
    )

    print(
        f"Current status: {current_status}"
    )

    print(
        f"Retry count: "
        f"{retry_count}/{max_retry_count}"
    )

    print("=" * 72)

    try:
        mark_processing(
            connection,
            notification_id,
        )

        print()
        print(
            "Worker: Status changed "
            f"{current_status} -> PROCESSING"
        )

        send_notification(
            notification
        )

        mark_sent(
            connection,
            notification_id,
        )

        print()
        print(
            f"Worker: Notification "
            f"{notification_id} sent successfully."
        )

        print(
            "Worker: Status changed "
            "PROCESSING -> SENT"
        )

        return True

    except Exception as error:
        new_status = handle_failure(
            connection,
            notification_id,
            str(error),
        )

        print()
        print(
            f"Worker: Notification "
            f"{notification_id} failed."
        )

        print(
            f"Reason: {error}"
        )

        if new_status == "RETRY":
            print()
            print(
                "Worker: Status changed "
                "PROCESSING -> RETRY"
            )

            print(
                "Worker: Retry count increased."
            )

            print(
                "Worker: Next retry will be "
                "available in approximately 1 minute."
            )

        elif new_status == "DEAD":
            print()
            print(
                "Worker: Maximum retry count reached."
            )

            print(
                "Worker: Status changed "
                "PROCESSING -> DEAD"
            )

        return False


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:
    print("=" * 72)
    print("Oracle AI Accounts Receivable Agent")
    print("Day 17 - Notification Retry + Failure Recovery")
    print("=" * 72)

    print(
        "\nCommands:"
        "\n  process    Process next retryable notification"
        "\n  status     Show notification retry status"
        "\n  exit       Close worker"
    )

    connection = get_connection()

    try:
        while True:
            command = input(
                "\nRetry-Worker> "
            ).strip().lower()

            if not command:
                continue

            # ==================================================
            # PROCESS
            # ==================================================

            if command == "process":
                process_next_notification(
                    connection
                )

                continue

            # ==================================================
            # STATUS
            # ==================================================

            if command == "status":
                show_retry_status(
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
                    "Worker: Closing retry worker."
                )

                break

            print()
            print(
                f"Unknown command: {command}"
            )

            print(
                "Available commands: "
                "process, status, exit"
            )

    except KeyboardInterrupt:
        print()
        print()
        print(
            "Worker: Keyboard interruption received."
        )

    finally:
        connection.close()

        print(
            "Worker: Oracle connection closed."
        )


# ==============================================================
# PROGRAM ENTRY POINT
# ==============================================================

if __name__ == "__main__":
    main()