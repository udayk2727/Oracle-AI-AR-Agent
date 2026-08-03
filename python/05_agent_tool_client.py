from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import oracledb
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_connection() -> oracledb.Connection:
    """Create an Oracle connection using credentials from .env."""

    load_dotenv(PROJECT_ROOT / ".env")

    required_variables = [
        "ORACLE_USER",
        "ORACLE_PASSWORD",
        "ORACLE_HOST",
        "ORACLE_PORT",
        "ORACLE_SERVICE",
    ]

    missing_variables = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing_variables)
        )

    return oracledb.connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        host=os.environ["ORACLE_HOST"],
        port=int(os.environ["ORACLE_PORT"]),
        service_name=os.environ["ORACLE_SERVICE"],
    )


def cursor_to_records(cursor: oracledb.Cursor) -> list[dict[str, Any]]:
    """Convert an Oracle cursor result into dictionaries."""

    if cursor.description is None:
        return []

    column_names = [
        column[0].lower()
        for column in cursor.description
    ]

    return [
        dict(zip(column_names, row))
        for row in cursor
    ]


def print_results(
    tool_name: str,
    records: list[dict[str, Any]],
) -> None:
    """Display tool output in readable JSON format."""

    print("\n" + "=" * 70)
    print(f"TOOL: {tool_name}")
    print(f"ROWS RETURNED: {len(records)}")
    print("=" * 70)

    print(
        json.dumps(
            records,
            indent=2,
            default=str,
        )
    )

def get_customer_summary(
    connection: oracledb.Connection,
    customer_id: int,
) -> list[dict[str, Any]]:
    """Call AR_AGENT_TOOLS.GET_CUSTOMER_SUMMARY."""

    call_cursor = connection.cursor()
    result_cursor = connection.cursor()

    try:
        print(f"Calling Oracle for customer {customer_id}...")

        call_cursor.callproc(
            "AR_AGENT_TOOLS.GET_CUSTOMER_SUMMARY",
            [
                customer_id,
                result_cursor,
            ],
        )

        print("Oracle procedure completed. Reading results...")

        return cursor_to_records(result_cursor)

    finally:
        result_cursor.close()
        call_cursor.close()
def get_overdue_invoices(
    connection: oracledb.Connection,
    customer_id: int,
) -> list[dict[str, Any]]:
    """Return overdue invoices for one customer."""

    cursor = connection.cursor()
    output_cursor = cursor.var(oracledb.CURSOR)

    try:
        cursor.callproc(
            "AR_AGENT_TOOLS.GET_OVERDUE_INVOICES",
            [
                customer_id,
                output_cursor,
            ],
        )

        returned_cursor = output_cursor.getvalue()
        return cursor_to_records(returned_cursor)

    finally:
        returned_cursor = output_cursor.getvalue()

        if returned_cursor is not None:
            returned_cursor.close()

        cursor.close()

def get_collection_queue(
    connection: oracledb.Connection,
    priority: str | None = None,
) -> list[dict[str, Any]]:
    """Return the AR collection queue."""

    cursor = connection.cursor()
    output_cursor = cursor.var(oracledb.CURSOR)

    try:
        cursor.callproc(
            "AR_AGENT_TOOLS.GET_COLLECTION_QUEUE",
            [
                priority,
                output_cursor,
            ],
        )

        returned_cursor = output_cursor.getvalue()
        return cursor_to_records(returned_cursor)

    finally:
        returned_cursor = output_cursor.getvalue()

        if returned_cursor is not None:
            returned_cursor.close()

        cursor.close()

def get_invoice_details(
    connection: oracledb.Connection,
    invoice_number: str,
) -> list[dict[str, Any]]:
    """Return full details for one invoice."""

    cursor = connection.cursor()
    output_cursor = cursor.var(oracledb.CURSOR)

    try:
        cursor.callproc(
            "AR_AGENT_TOOLS.GET_INVOICE_DETAILS",
            [
                invoice_number,
                output_cursor,
            ],
        )

        returned_cursor = output_cursor.getvalue()
        return cursor_to_records(returned_cursor)

    finally:
        returned_cursor = output_cursor.getvalue()

        if returned_cursor is not None:
            returned_cursor.close()

        cursor.close()

def show_menu() -> None:
    print("\nOracle AI Accounts Receivable Agent")
    print("------------------------------------")
    print("1. Get customer summary")
    print("2. Get overdue invoices")
    print("3. Get collection queue")
    print("4. Get invoice details")
    print("5. Exit")

def main() -> None:
    connection = get_connection()

    try:
        print("Connected to Oracle successfully.")

        while True:
            show_menu()
            choice = input("\nSelect an option: ").strip()

            try:
                if choice == "1":
                    customer_id = int(
                        input("Enter customer ID: ").strip()
                    )

                    records = get_customer_summary(
                        connection,
                        customer_id,
                    )

                    print_results(
                        "GET_CUSTOMER_SUMMARY",
                        records,
                    )

                elif choice == "2":
                    customer_id = int(
                        input("Enter customer ID: ").strip()
                    )

                    records = get_overdue_invoices(
                        connection,
                        customer_id,
                    )

                    print_results(
                        "GET_OVERDUE_INVOICES",
                        records,
                    )

                elif choice == "3":
                    priority = input(
                        "Enter priority "
                        "(CRITICAL/HIGH/MEDIUM/LOW or blank): "
                    ).strip()

                    records = get_collection_queue(
                        connection,
                        priority.upper() if priority else None,
                    )

                    print_results(
                        "GET_COLLECTION_QUEUE",
                        records[:20],
                    )

                elif choice == "4":
                    invoice_number = input(
                        "Enter invoice number: "
                    ).strip()

                    records = get_invoice_details(
                        connection,
                        invoice_number,
                    )

                    print_results(
                        "GET_INVOICE_DETAILS",
                        records,
                    )

                elif choice == "5":
                    print("Closing the agent tool client.")
                    break

                else:
                    print("Invalid option. Select 1 through 5.")

            except ValueError:
                print("Please enter a valid numeric customer ID.")

            except oracledb.DatabaseError as error:
                oracle_error = error.args[0]
                print(
                    "Oracle tool error:",
                    oracle_error.message,
                )

    finally:
        connection.close()
        print("Oracle connection closed.")


if __name__ == "__main__":
    main()