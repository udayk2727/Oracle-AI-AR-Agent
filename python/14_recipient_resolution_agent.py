from __future__ import annotations

import json
from typing import Any

from agent_tool_client import get_connection


# ==============================================================
# GET INVOICE CUSTOMER
# ==============================================================

def get_invoice_customer(
    connection: Any,
    invoice_number: str,
) -> dict[str, Any] | None:
    """
    Return invoice, customer, and recipient email information.
    """

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

    finally:
        cursor.close()


# ==============================================================
# RESOLVE RECIPIENT
# ==============================================================

def resolve_recipient(
    connection: Any,
    invoice_number: str,
) -> dict[str, Any]:
    """
    Resolve the customer email address for an invoice.
    """

    invoice = get_invoice_customer(
        connection,
        invoice_number,
    )

    if invoice is None:
        raise ValueError(
            f"Invoice {invoice_number} was not found."
        )

    customer_status = invoice.get(
        "STATUS"
    )

    if customer_status is not None:
        customer_status = str(
            customer_status
        ).upper()

    if customer_status == "INACTIVE":
        raise ValueError(
            f"Customer {invoice['CUSTOMER_ID']} is INACTIVE."
        )

    email = invoice.get(
        "EMAIL"
    )

    if email is None:
        raise ValueError(
            f"Customer {invoice['CUSTOMER_ID']} "
            "does not have an email address."
        )

    email = str(email).strip()

    if not email:
        raise ValueError(
            f"Customer {invoice['CUSTOMER_ID']} "
            "does not have a usable email address."
        )

    return {
        "invoice_number": str(
            invoice["INVOICE_NUMBER"]
        ),
        "customer_id": int(
            invoice["CUSTOMER_ID"]
        ),
        "customer_name": invoice[
            "CUSTOMER_NAME"
        ],
        "recipient_address": email,
    }


# ==============================================================
# GET APPROVAL REQUEST
# ==============================================================

def get_approval_request(
    connection: Any,
    approval_id: int,
) -> dict[str, Any] | None:
    """
    Return one approval request.
    """

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                approval_id,
                conversation_id,
                action_type,
                action_description,
                action_payload,
                approval_status,
                reviewed_at,
                reviewed_by,
                executed_at,
                execution_status,
                execution_message
            FROM agent_approval_requests
            WHERE approval_id = :approval_id
            """,
            {
                "approval_id": approval_id,
            },
        )

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

    finally:
        cursor.close()


# ==============================================================
# QUEUE APPROVED NOTIFICATION
# ==============================================================

def execute_approved_action(
    connection: Any,
    approval_id: int,
) -> str:
    """
    Resolve the recipient and queue an approved payment reminder.
    """

    approval = get_approval_request(
        connection,
        approval_id,
    )

    if approval is None:
        raise ValueError(
            f"Approval request {approval_id} was not found."
        )

    if approval["APPROVAL_STATUS"] != "APPROVED":
        raise ValueError(
            f"Approval request {approval_id} is "
            f"{approval['APPROVAL_STATUS']}, not APPROVED."
        )

    action_type = approval[
        "ACTION_TYPE"
    ]

    if action_type != "SEND_PAYMENT_REMINDER":
        raise ValueError(
            f"Unsupported action type: {action_type}"
        )

    payload_raw = approval[
        "ACTION_PAYLOAD"
    ]

    if hasattr(payload_raw, "read"):
        payload_raw = payload_raw.read()

    payload = json.loads(
        payload_raw
    )

    invoice_number = str(
        payload["invoice_number"]
    )

    recipient = resolve_recipient(
        connection,
        invoice_number,
    )

    conversation_id = approval[
        "CONVERSATION_ID"
    ]

    recipient_address = recipient[
        "recipient_address"
    ]

    customer_name = recipient[
        "customer_name"
    ]

    notification_type = (
        "PAYMENT_REMINDER"
    )

    subject_text = (
        f"Payment Reminder - "
        f"Invoice {invoice_number}"
    )

    message_body = (
        f"Hello {customer_name},\n\n"
        f"This is a payment reminder for invoice "
        f"{invoice_number}. "
        "Please review the outstanding balance "
        "and arrange payment.\n\n"
        "Thank you."
    )

    cursor = connection.cursor()

    try:
        # ------------------------------------------------------
        # DUPLICATE PROTECTION
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT notification_id
            FROM agent_notification_outbox
            WHERE approval_id = :approval_id
            """,
            {
                "approval_id": approval_id,
            },
        )

        existing = cursor.fetchone()

        if existing is not None:
            raise ValueError(
                f"Approval request {approval_id} already "
                f"has notification {existing[0]}."
            )

        # ------------------------------------------------------
        # CREATE OUTBOX RECORD
        # ------------------------------------------------------

        notification_id = cursor.var(
            int
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
                :notification_type,
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
                "conversation_id": conversation_id,
                "notification_type": notification_type,
                "recipient_address": recipient_address,
                "subject_text": subject_text,
                "message_body": message_body,
                "notification_id": notification_id,
            },
        )

        generated_notification_id = int(
            notification_id.getvalue()[0]
        )

        execution_message = (
            f"Payment reminder for invoice "
            f"{invoice_number} was queued. "
            f"Recipient: {recipient_address}. "
            f"Notification ID: "
            f"{generated_notification_id}. "
            "Status: PENDING."
        )

        # ------------------------------------------------------
        # MARK APPROVAL EXECUTED
        # ------------------------------------------------------

        cursor.execute(
            """
            UPDATE agent_approval_requests
            SET
                approval_status = 'EXECUTED',
                executed_at = SYSTIMESTAMP,
                execution_status = 'SUCCESS',
                execution_message = :execution_message
            WHERE approval_id = :approval_id
              AND approval_status = 'APPROVED'
            """,
            {
                "execution_message": execution_message,
                "approval_id": approval_id,
            },
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "Approval status changed before execution."
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()

    return execution_message


# ==============================================================
# SHOW RECIPIENT
# ==============================================================

def show_recipient(
    connection: Any,
    invoice_number: str,
) -> None:
    """
    Display the resolved customer recipient.
    """

    recipient = resolve_recipient(
        connection,
        invoice_number,
    )

    print()
    print("=" * 72)
    print("RECIPIENT RESOLUTION")
    print("=" * 72)

    print(
        f"Invoice Number : "
        f"{recipient['invoice_number']}"
    )

    print(
        f"Customer ID    : "
        f"{recipient['customer_id']}"
    )

    print(
        f"Customer Name  : "
        f"{recipient['customer_name']}"
    )

    print(
        f"Recipient      : "
        f"{recipient['recipient_address']}"
    )

    print("=" * 72)


# ==============================================================
# SHOW OUTBOX
# ==============================================================

def show_outbox(
    connection: Any,
) -> None:
    """
    Display notification outbox records.
    """

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
            ORDER BY notification_id
            """
        )

        rows = cursor.fetchall()

        print()
        print("=" * 90)
        print("NOTIFICATION OUTBOX")
        print("=" * 90)

        if not rows:
            print(
                "Notification outbox is empty."
            )

            print("=" * 90)
            return

        for row in rows:
            print()

            print(
                f"Notification ID : {row[0]}"
            )

            print(
                f"Approval ID     : {row[1]}"
            )

            print(
                f"Type            : {row[2]}"
            )

            print(
                f"Recipient       : {row[3]}"
            )

            print(
                f"Subject         : {row[4]}"
            )

            print(
                f"Status          : {row[5]}"
            )

            print(
                f"Retry Count     : {row[6]}"
            )

            print(
                f"Created At      : {row[7]}"
            )

            print(
                f"Processed At    : {row[8]}"
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
    print("Day 18 - Recipient Resolution")
    print("=" * 72)

    print(
        "\nCommands:"
        "\n  resolve <invoice_number>   Resolve customer email"
        "\n  execute <approval_id>      Queue approved reminder"
        "\n  outbox                     Show notification outbox"
        "\n  exit                       Close agent"
    )

    connection = get_connection()

    try:
        while True:
            command = input(
                "\nRecipient-Agent> "
            ).strip()

            if not command:
                continue

            command_lower = (
                command.lower()
            )

            # ==================================================
            # RESOLVE RECIPIENT
            # ==================================================

            if command_lower.startswith(
                "resolve "
            ):
                parts = command.split(
                    maxsplit=1
                )

                if len(parts) != 2:
                    print(
                        "\nUsage: resolve "
                        "<invoice_number>"
                    )
                    continue

                invoice_number = (
                    parts[1].strip()
                )

                try:
                    show_recipient(
                        connection,
                        invoice_number,
                    )

                except Exception as error:
                    print()
                    print(
                        f"Recipient resolution "
                        f"failed: {error}"
                    )

                continue

            # ==================================================
            # EXECUTE APPROVED ACTION
            # ==================================================

            if command_lower.startswith(
                "execute "
            ):
                parts = command.split(
                    maxsplit=1
                )

                if len(parts) != 2:
                    print(
                        "\nUsage: execute "
                        "<approval_id>"
                    )
                    continue

                try:
                    approval_id = int(
                        parts[1]
                    )

                except ValueError:
                    print(
                        "\nApproval ID must "
                        "be a number."
                    )

                    continue

                try:
                    execution_message = (
                        execute_approved_action(
                            connection,
                            approval_id,
                        )
                    )

                    print()
                    print(
                        "Agent:"
                    )

                    print(
                        execution_message
                    )

                except Exception as error:
                    print()
                    print(
                        f"Execution failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # OUTBOX
            # ==================================================

            if command_lower == "outbox":
                show_outbox(
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
                    "Recipient agent closed."
                )

                break

            print()
            print(
                f"Unknown command: "
                f"{command}"
            )

            print(
                "Available commands: "
                "resolve, execute, outbox, exit"
            )

    except KeyboardInterrupt:
        print()
        print(
            "Recipient agent interrupted."
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