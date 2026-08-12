from __future__ import annotations

import json
from typing import Any

from agent_tool_client import get_connection
from uuid import uuid4

# ==============================================================
# HELPERS
# ==============================================================

def fetch_one_as_dict(
    cursor: Any,
) -> dict[str, Any] | None:
    row = cursor.fetchone()

    if row is None:
        return None

    columns = [
        column[0]
        for column in cursor.description
    ]

    return dict(zip(columns, row))


def fetch_all_as_dicts(
    cursor: Any,
) -> list[dict[str, Any]]:
    columns = [
        column[0]
        for column in cursor.description
    ]

    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


# ==============================================================
# ORCHESTRATION AUDIT
# ==============================================================

def create_orchestration_run(
    connection: Any,
    invoice_number: str,
) -> int:
    cursor = connection.cursor()

    try:
        orchestration_id = cursor.var(int)

        cursor.execute(
            """
            INSERT INTO agent_orchestration_runs
            (
                invoice_number,
                orchestration_status,
                current_step
            )
            VALUES
            (
                :invoice_number,
                'STARTED',
                'VALIDATE_INVOICE'
            )
            RETURNING orchestration_id
            INTO :orchestration_id
            """,
            {
                "invoice_number": invoice_number,
                "orchestration_id": orchestration_id,
            },
        )

        connection.commit()

        return int(
            orchestration_id.getvalue()[0]
        )

    finally:
        cursor.close()


def update_orchestration(
    connection: Any,
    orchestration_id: int,
    *,
    status: str,
    current_step: str,
    approval_id: int | None = None,
    notification_id: int | None = None,
    error_message: str | None = None,
    completed: bool = False,
) -> None:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE agent_orchestration_runs
            SET
                orchestration_status = :status,
                current_step = :current_step,

                approval_id =
                    COALESCE(
                        CAST(:approval_id AS NUMBER),                        
                        approval_id
                    ),

                notification_id =
                    COALESCE(
                        CAST(:notification_id AS NUMBER),
                        notification_id
                    ),

                error_message = :error_message,

                completed_at =
                    CASE
                        WHEN :completed_flag = 1
                        THEN SYSTIMESTAMP
                        ELSE completed_at
                    END

            WHERE orchestration_id = :orchestration_id
            """,
            {
                "status": status,
                "current_step": current_step,
                "approval_id": approval_id,
                "notification_id": notification_id,
                "error_message": error_message,
                "completed_flag": (
                    1 if completed else 0
                ),
                "orchestration_id": orchestration_id,
            },
        )

        connection.commit()

    finally:
        cursor.close()


# ==============================================================
# INVOICE + RECIPIENT RESOLUTION
# ==============================================================

def resolve_invoice_recipient(
    connection: Any,
    invoice_number: str,
) -> dict[str, Any]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                i.invoice_number,
                i.customer_id,
                c.customer_name,
                c.email,
                c.status
            FROM invoices i
            JOIN customers c
                ON c.customer_id = i.customer_id
            WHERE i.invoice_number = :invoice_number
            """,
            {
                "invoice_number": invoice_number,
            },
        )

        result = fetch_one_as_dict(
            cursor
        )

        if result is None:
            raise ValueError(
                f"Invoice {invoice_number} "
                "was not found."
            )

        email = result.get("EMAIL")

        if email is None:
            raise ValueError(
                f"Customer "
                f"{result['CUSTOMER_ID']} "
                "does not have an email address."
            )

        email = str(email).strip()

        if not email:
            raise ValueError(
                f"Customer "
                f"{result['CUSTOMER_ID']} "
                "does not have a usable "
                "email address."
            )

        customer_status = result.get(
            "STATUS"
        )

        if customer_status is not None:
            customer_status = str(
                customer_status
            ).upper()

        if customer_status == "INACTIVE":
            raise ValueError(
                f"Customer "
                f"{result['CUSTOMER_ID']} "
                "is INACTIVE."
            )

        result["EMAIL"] = email

        return result

    finally:
        cursor.close()

def create_orchestration_conversation(
    connection: Any,
) -> str:
    """Create a valid parent conversation for the orchestration."""

    conversation_id = str(
        uuid4()
    )

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO agent_conversations
            (
                conversation_id,
                conversation_status
            )
            VALUES
            (
                :conversation_id,
                'ACTIVE'
            )
            """,
            {
                "conversation_id": conversation_id,
            },
        )

        connection.commit()

        return conversation_id

    finally:
        cursor.close()
# ==============================================================
# CREATE APPROVAL REQUEST
# ==============================================================

def create_approval_request(
    connection: Any,
    conversation_id: str,
    invoice_number: str,
) -> int:
    cursor = connection.cursor()

    try:
        approval_id = cursor.var(int)

        payload = {
            "invoice_number": invoice_number,
            "channel": "EMAIL",
        }

        cursor.execute(
            """
            INSERT INTO agent_approval_requests
            (
                conversation_id,
                action_type,
                action_description,
                action_payload,
                approval_status
            )
            VALUES
            (
                :conversation_id,
                'SEND_PAYMENT_REMINDER',
                :action_description,
                :action_payload,
                'PENDING'
            )
            RETURNING approval_id
            INTO :approval_id
            """,
            {
                "conversation_id": conversation_id,
                "action_description": (
                    "Send a payment reminder "
                    f"for invoice {invoice_number}."
                ),
                "action_payload": json.dumps(
                    payload
                ),
                "approval_id": approval_id,
            },
        )

        connection.commit()

        return int(
            approval_id.getvalue()[0]
        )

    finally:
        cursor.close()


# ==============================================================
# START ORCHESTRATION
# ==============================================================

def start_orchestration(
    connection: Any,
    invoice_number: str,
) -> str:
    orchestration_id = (
        create_orchestration_run(
            connection,
            invoice_number,
        )
    )

    try:
        recipient = resolve_invoice_recipient(
            connection,
            invoice_number,
        )

        conversation_id = (
            create_orchestration_conversation(
                connection
        )
        )

        approval_id = create_approval_request(
            connection,
            conversation_id,
            invoice_number,
        )

        update_orchestration(
            connection,
            orchestration_id,
            status="WAITING_APPROVAL",
            current_step="WAITING_APPROVAL",
            approval_id=approval_id,
        )

        return (
            f"Orchestration {orchestration_id} "
            f"started for invoice "
            f"{invoice_number}.\n"
            f"Customer: "
            f"{recipient['CUSTOMER_NAME']}\n"
            f"Recipient: "
            f"{recipient['EMAIL']}\n"
            f"Approval ID: {approval_id}\n"
            "Status: WAITING_APPROVAL.\n"
            "Use: approve "
            f"{orchestration_id}"
        )

    except Exception as error:
        update_orchestration(
            connection,
            orchestration_id,
            status="FAILED",
            current_step="FAILED",
            error_message=str(error)[:4000],
            completed=True,
        )

        raise


# ==============================================================
# GET ORCHESTRATION
# ==============================================================

def get_orchestration(
    connection: Any,
    orchestration_id: int,
) -> dict[str, Any] | None:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                o.orchestration_id,
                o.invoice_number,
                o.approval_id,
                o.notification_id,
                o.orchestration_status,
                o.current_step,
                o.started_at,
                o.completed_at,
                o.error_message,
                a.conversation_id
            FROM agent_orchestration_runs o
            LEFT JOIN agent_approval_requests a
                ON a.approval_id = o.approval_id
            WHERE orchestration_id =
                :orchestration_id
            """,
            {
                "orchestration_id":
                    orchestration_id,
            },
        )

        return fetch_one_as_dict(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# APPROVE + QUEUE + PROCESS
# ==============================================================

def approve_orchestration(
    connection: Any,
    orchestration_id: int,
) -> str:
    orchestration = get_orchestration(
        connection,
        orchestration_id,
    )

    if orchestration is None:
        raise ValueError(
            f"Orchestration "
            f"{orchestration_id} "
            "was not found."
        )

    if (
        orchestration[
            "ORCHESTRATION_STATUS"
        ]
        != "WAITING_APPROVAL"
    ):
        raise ValueError(
            f"Orchestration "
            f"{orchestration_id} is "
            f"{orchestration['ORCHESTRATION_STATUS']}, "
            "not WAITING_APPROVAL."
        )

    approval_id = int(
        orchestration["APPROVAL_ID"]
    )

    invoice_number = str(
        orchestration["INVOICE_NUMBER"]
    )

    recipient = resolve_invoice_recipient(
        connection,
        invoice_number,
    )

    cursor = connection.cursor()

    try:
        # ------------------------------------------------------
        # APPROVE REQUEST
        # ------------------------------------------------------

        cursor.execute(
            """
            UPDATE agent_approval_requests
            SET
                approval_status = 'APPROVED',
                reviewed_at = SYSTIMESTAMP,
                reviewed_by = 'AR_MANAGER',
                review_comments =
                    'Approved from Day 21 orchestrator.'
            WHERE approval_id = :approval_id
              AND approval_status = 'PENDING'
            """,
            {
                "approval_id": approval_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Approval request could not "
                "be approved."
            )

        update_orchestration(
            connection,
            orchestration_id,
            status="APPROVED",
            current_step="CREATE_OUTBOX",
        )

        # ------------------------------------------------------
        # CREATE OUTBOX RECORD
        # ------------------------------------------------------

        notification_id = cursor.var(
            int
        )

        subject_text = (
            f"Payment Reminder - "
            f"Invoice {invoice_number}"
        )

        message_body = (
            f"Hello "
            f"{recipient['CUSTOMER_NAME']},\n\n"
            f"This is a payment reminder "
            f"for invoice {invoice_number}. "
            "Please review the outstanding "
            "balance and arrange payment.\n\n"
            "Thank you."
        )

        cursor.execute(
            """
            INSERT INTO agent_notification_outbox
            (
                approval_id,
                conversation_id,
                notification_type,
                recipient_address,
                subject_text,
                message_body,
                notification_status,
                retry_count,
                created_at,
                updated_at
            )
            VALUES
            (
                :approval_id,
                :conversation_id,
                'PAYMENT_REMINDER',
                :recipient_address,
                :subject_text,
                :message_body,
                'PENDING',
                0,
                SYSTIMESTAMP,
                SYSTIMESTAMP
            )
            RETURNING notification_id
            INTO :notification_id
            """,
            {
                "approval_id": approval_id,
                "conversation_id":
                    orchestration["CONVERSATION_ID"],
                "recipient_address":
                    recipient["EMAIL"],
                "subject_text": subject_text,
                "message_body": message_body,
                "notification_id":
                    notification_id,
            },
        )

        generated_notification_id = int(
            notification_id.getvalue()[0]
        )

        # ------------------------------------------------------
        # MARK APPROVAL EXECUTED
        # ------------------------------------------------------

        execution_message = (
            f"Notification "
            f"{generated_notification_id} "
            "created by orchestrator."
        )

        cursor.execute(
            """
            UPDATE agent_approval_requests
            SET
                approval_status = 'EXECUTED',
                executed_at = SYSTIMESTAMP,
                execution_status = 'SUCCESS',
                execution_message =
                    :execution_message
            WHERE approval_id = :approval_id
              AND approval_status = 'APPROVED'
            """,
            {
                "execution_message":
                    execution_message,
                "approval_id": approval_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Approval could not be "
                "marked EXECUTED."
            )

        update_orchestration(
            connection,
            orchestration_id,
            status="QUEUED",
            current_step="PROCESS_NOTIFICATION",
            notification_id=
                generated_notification_id,
        )

        # ------------------------------------------------------
        # PROCESS NOTIFICATION
        # ------------------------------------------------------

        cursor.execute(
            """
            UPDATE agent_notification_outbox
            SET
                notification_status =
                    'PROCESSING',
                updated_at = SYSTIMESTAMP
            WHERE notification_id =
                :notification_id
              AND notification_status =
                'PENDING'
            """,
            {
                "notification_id":
                    generated_notification_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Notification could not be "
                "moved to PROCESSING."
            )

        update_orchestration(
            connection,
            orchestration_id,
            status="PROCESSING",
            current_step="SEND_NOTIFICATION",
        )

        # ------------------------------------------------------
        # SIMULATED DELIVERY
        # ------------------------------------------------------

        if not recipient["EMAIL"]:
            raise RuntimeError(
                "Recipient email is missing."
            )

        print()
        print("=" * 72)
        print("SIMULATED DELIVERY")
        print("=" * 72)

        print(
            f"Notification ID : "
            f"{generated_notification_id}"
        )

        print(
            f"Recipient       : "
            f"{recipient['EMAIL']}"
        )

        print(
            f"Subject         : "
            f"{subject_text}"
        )

        print()
        print(message_body)

        print("=" * 72)

        # ------------------------------------------------------
        # MARK SENT
        # ------------------------------------------------------

        cursor.execute(
            """
            UPDATE agent_notification_outbox
            SET
                notification_status = 'SENT',
                processed_at = SYSTIMESTAMP,
                updated_at = SYSTIMESTAMP,
                error_message = NULL,
                failure_reason = NULL,
                next_retry_at = NULL
            WHERE notification_id =
                :notification_id
              AND notification_status =
                'PROCESSING'
            """,
            {
                "notification_id":
                    generated_notification_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Notification could not "
                "be marked SENT."
            )

        update_orchestration(
            connection,
            orchestration_id,
            status="COMPLETED",
            current_step="COMPLETED",
            notification_id=
                generated_notification_id,
            completed=True,
        )

        connection.commit()

        return (
            f"Orchestration "
            f"{orchestration_id} completed.\n"
            f"Approval ID: {approval_id}\n"
            f"Notification ID: "
            f"{generated_notification_id}\n"
            f"Recipient: "
            f"{recipient['EMAIL']}\n"
            "Notification Status: SENT."
        )

    except Exception as error:
        connection.rollback()

        update_orchestration(
            connection,
            orchestration_id,
            status="FAILED",
            current_step="FAILED",
            error_message=str(error)[:4000],
            completed=True,
        )

        raise

    finally:
        cursor.close()


# ==============================================================
# SHOW STATUS
# ==============================================================

def show_status(
    connection: Any,
    orchestration_id: int,
) -> None:
    row = get_orchestration(
        connection,
        orchestration_id,
    )

    if row is None:
        print()
        print(
            f"Orchestration "
            f"{orchestration_id} "
            "was not found."
        )

        return

    print()
    print("=" * 72)
    print("ORCHESTRATION STATUS")
    print("=" * 72)

    print(
        f"Orchestration ID : "
        f"{row['ORCHESTRATION_ID']}"
    )

    print(
        f"Invoice Number   : "
        f"{row['INVOICE_NUMBER']}"
    )

    print(
        f"Approval ID      : "
        f"{row['APPROVAL_ID']}"
    )

    print(
        f"Notification ID  : "
        f"{row['NOTIFICATION_ID']}"
    )

    print(
        f"Status           : "
        f"{row['ORCHESTRATION_STATUS']}"
    )

    print(
        f"Current Step     : "
        f"{row['CURRENT_STEP']}"
    )

    print(
        f"Started At       : "
        f"{row['STARTED_AT']}"
    )

    print(
        f"Completed At     : "
        f"{row['COMPLETED_AT']}"
    )

    print(
        f"Error            : "
        f"{row['ERROR_MESSAGE']}"
    )

    print("=" * 72)


# ==============================================================
# SHOW HISTORY
# ==============================================================

def show_history(
    connection: Any,
) -> None:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                orchestration_id,
                invoice_number,
                approval_id,
                notification_id,
                orchestration_status,
                current_step,
                started_at,
                completed_at,
                error_message
            FROM agent_orchestration_runs
            ORDER BY orchestration_id DESC
            FETCH FIRST 20 ROWS ONLY
            """
        )

        rows = fetch_all_as_dicts(
            cursor
        )

        print()
        print("=" * 90)
        print("ORCHESTRATION HISTORY")
        print("=" * 90)

        if not rows:
            print(
                "No orchestration runs found."
            )

            return

        for row in rows:
            print()

            print(
                f"Orchestration ID : "
                f"{row['ORCHESTRATION_ID']}"
            )

            print(
                f"Invoice          : "
                f"{row['INVOICE_NUMBER']}"
            )

            print(
                f"Approval ID      : "
                f"{row['APPROVAL_ID']}"
            )

            print(
                f"Notification ID  : "
                f"{row['NOTIFICATION_ID']}"
            )

            print(
                f"Status           : "
                f"{row['ORCHESTRATION_STATUS']}"
            )

            print(
                f"Step             : "
                f"{row['CURRENT_STEP']}"
            )

            print(
                f"Started          : "
                f"{row['STARTED_AT']}"
            )

            print(
                f"Completed        : "
                f"{row['COMPLETED_AT']}"
            )

            print(
                f"Error            : "
                f"{row['ERROR_MESSAGE']}"
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
    print("Day 21 - End-to-End Action Orchestrator")
    print("=" * 72)

    print(
        "\nCommands:"
        "\n  run <invoice_number>         Start orchestration"
        "\n  approve <orchestration_id>   Approve and complete flow"
        "\n  status <orchestration_id>    Show run status"
        "\n  history                      Show orchestration history"
        "\n  exit                         Close orchestrator"
    )

    connection = get_connection()

    try:
        while True:
            command = input(
                "\nOrchestrator> "
            ).strip()

            if not command:
                continue

            command_lower = (
                command.lower()
            )

            # ==================================================
            # RUN
            # ==================================================

            if command_lower.startswith(
                "run "
            ):
                parts = command.split(
                    maxsplit=1
                )

                if len(parts) != 2:
                    print(
                        "\nUsage: run "
                        "<invoice_number>"
                    )

                    continue

                invoice_number = (
                    parts[1].strip()
                )

                try:
                    result = start_orchestration(
                        connection,
                        invoice_number,
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
                        f"Orchestration failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # APPROVE
            # ==================================================

            if command_lower.startswith(
                "approve "
            ):
                parts = command.split(
                    maxsplit=1
                )

                if len(parts) != 2:
                    print(
                        "\nUsage: approve "
                        "<orchestration_id>"
                    )

                    continue

                try:
                    orchestration_id = int(
                        parts[1]
                    )

                except ValueError:
                    print(
                        "\nOrchestration ID "
                        "must be a number."
                    )

                    continue

                try:
                    result = approve_orchestration(
                        connection,
                        orchestration_id,
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
                        f"Approval/execution "
                        f"failed: {error}"
                    )

                continue

            # ==================================================
            # STATUS
            # ==================================================

            if command_lower.startswith(
                "status "
            ):
                parts = command.split(
                    maxsplit=1
                )

                if len(parts) != 2:
                    print(
                        "\nUsage: status "
                        "<orchestration_id>"
                    )

                    continue

                try:
                    orchestration_id = int(
                        parts[1]
                    )

                except ValueError:
                    print(
                        "\nOrchestration ID "
                        "must be a number."
                    )

                    continue

                show_status(
                    connection,
                    orchestration_id,
                )

                continue

            # ==================================================
            # HISTORY
            # ==================================================

            if command_lower == "history":
                show_history(
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
                    "Orchestrator closed."
                )

                break

            print()
            print(
                f"Unknown command: "
                f"{command}"
            )

            print(
                "Available commands: "
                "run, approve, status, "
                "history, exit"
            )

    except KeyboardInterrupt:
        print()
        print(
            "Orchestrator interrupted."
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