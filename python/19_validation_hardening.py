from __future__ import annotations

from typing import Any

from agent_tool_client import get_connection


# ==============================================================
# REQUIRED DATABASE OBJECTS
# ==============================================================

REQUIRED_TABLES = [
    "CUSTOMERS",
    "INVOICES",
    "AGENT_CONVERSATIONS",
    "AGENT_APPROVAL_REQUESTS",
    "AGENT_NOTIFICATION_OUTBOX",
    "AGENT_ORCHESTRATION_RUNS",
]

REQUIRED_VIEWS = [
    "VW_AR_AGING_DETAIL",
]


# ==============================================================
# DATABASE CONNECTION CHECK
# ==============================================================

def check_database_connection(
    connection: Any,
) -> dict[str, Any]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                SYSDATE AS database_time
            FROM dual
            """
        )

        row = cursor.fetchone()

        return {
            "check": "Database Connection",
            "status": "PASS",
            "message": (
                f"Oracle connection is healthy. "
                f"Database time: {row[0]}"
            ),
        }

    except Exception as error:
        return {
            "check": "Database Connection",
            "status": "FAIL",
            "message": str(error),
        }

    finally:
        cursor.close()


# ==============================================================
# TABLE EXISTENCE CHECK
# ==============================================================

def check_required_tables(
    connection: Any,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()

    results = []

    try:
        for table_name in REQUIRED_TABLES:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM user_tables
                WHERE table_name = :table_name
                """,
                {
                    "table_name": table_name,
                },
            )

            count = cursor.fetchone()[0]

            if count == 1:
                results.append(
                    {
                        "check": table_name,
                        "status": "PASS",
                        "message": "Required table exists.",
                    }
                )

            else:
                results.append(
                    {
                        "check": table_name,
                        "status": "FAIL",
                        "message": "Required table is missing.",
                    }
                )

        return results

    finally:
        cursor.close()


# ==============================================================
# VIEW EXISTENCE CHECK
# ==============================================================

def check_required_views(
    connection: Any,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()

    results = []

    try:
        for view_name in REQUIRED_VIEWS:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM user_views
                WHERE view_name = :view_name
                """,
                {
                    "view_name": view_name,
                },
            )

            count = cursor.fetchone()[0]

            if count == 1:
                results.append(
                    {
                        "check": view_name,
                        "status": "PASS",
                        "message": "Required view exists.",
                    }
                )

            else:
                results.append(
                    {
                        "check": view_name,
                        "status": "FAIL",
                        "message": "Required view is missing.",
                    }
                )

        return results

    finally:
        cursor.close()

# ==============================================================
# AR DATA INTEGRITY CHECKS
# ==============================================================

def check_ar_data_integrity(
    connection: Any,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()

    results = []

    try:
        # ------------------------------------------------------
        # NEGATIVE OUTSTANDING BALANCES
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM invoices
            WHERE outstanding_amount < 0
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Negative Outstanding Balances",
                "status": (
                    "PASS"
                    if count == 0
                    else "FAIL"
                ),
                "message": (
                    f"{count} invoice(s) found."
                ),
            }
        )

        # ------------------------------------------------------
        # NEGATIVE AMOUNT PAID
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM invoices
            WHERE amount_paid < 0
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Negative Amount Paid",
                "status": (
                    "PASS"
                    if count == 0
                    else "FAIL"
                ),
                "message": (
                    f"{count} invoice(s) found."
                ),
            }
        )

        # ------------------------------------------------------
        # OUTSTANDING GREATER THAN INVOICE AMOUNT
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM invoices
            WHERE outstanding_amount > invoice_amount
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Outstanding > Invoice Amount",
                "status": (
                    "PASS"
                    if count == 0
                    else "FAIL"
                ),
                "message": (
                    f"{count} invoice(s) found."
                ),
            }
        )

        # ------------------------------------------------------
        # MISSING DUE DATES
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM invoices
            WHERE due_date IS NULL
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Missing Due Dates",
                "status": (
                    "PASS"
                    if count == 0
                    else "WARNING"
                ),
                "message": (
                    f"{count} invoice(s) found."
                ),
            }
        )

        # ------------------------------------------------------
        # ORPHAN INVOICES
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM invoices i
            LEFT JOIN customers c
                ON c.customer_id = i.customer_id
            WHERE c.customer_id IS NULL
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Orphan Invoices",
                "status": (
                    "PASS"
                    if count == 0
                    else "FAIL"
                ),
                "message": (
                    f"{count} invoice(s) without "
                    "a valid customer."
                ),
            }
        )

        # ------------------------------------------------------
        # CUSTOMERS WITHOUT EMAIL
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM customers
            WHERE email IS NULL
               OR TRIM(email) IS NULL
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Customers Without Email",
                "status": (
                    "PASS"
                    if count == 0
                    else "WARNING"
                ),
                "message": (
                    f"{count} customer(s) found."
                ),
            }
        )

        return results

    finally:
        cursor.close()


# ==============================================================
# DISPLAY AR DATA HEALTH
# ==============================================================

def show_ar_data_health(
    connection: Any,
) -> None:
    print()
    print("=" * 78)
    print("AR DATA INTEGRITY VALIDATION")
    print("=" * 78)

    results = check_ar_data_integrity(
        connection
    )

    for result in results:
        print()
        print(
            f"[{result['status']}] "
            f"{result['check']}"
        )

        print(
            f"    {result['message']}"
        )

    print()
    print("=" * 78)

# ==============================================================
# DISPLAY HEALTH REPORT
# ==============================================================

def show_schema_health(
    connection: Any,
) -> None:
    print()
    print("=" * 78)
    print("DAY 23 - DATABASE & SCHEMA HEALTH CHECK")
    print("=" * 78)

    connection_result = check_database_connection(
        connection
    )

    print()
    print(
        f"[{connection_result['status']}] "
        f"{connection_result['check']}"
    )

    print(
        f"    {connection_result['message']}"
    )

    print()
    print("REQUIRED TABLES")
    print("-" * 78)

    table_results = check_required_tables(
        connection
    )

    for result in table_results:
        print(
            f"[{result['status']}] "
            f"{result['check']} - "
            f"{result['message']}"
        )

    print()
    print("REQUIRED VIEWS")
    print("-" * 78)

    view_results = check_required_views(
        connection
    )

    for result in view_results:
        print(
            f"[{result['status']}] "
            f"{result['check']} - "
            f"{result['message']}"
        )

    print()
    print("=" * 78)

# ==============================================================
# AGENT WORKFLOW HEALTH CHECKS
# ==============================================================

def check_agent_workflow_health(
    connection: Any,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()

    results = []

    try:
        # ------------------------------------------------------
        # STALE STARTED ORCHESTRATIONS
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM agent_orchestration_runs
            WHERE orchestration_status = 'STARTED'
              AND started_at < SYSTIMESTAMP - INTERVAL '30' MINUTE
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Stale STARTED Orchestrations",
                "status": (
                    "PASS"
                    if count == 0
                    else "WARNING"
                ),
                "message": (
                    f"{count} stale orchestration(s) found."
                ),
            }
        )

        # ------------------------------------------------------
        # FAILED ORCHESTRATIONS
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM agent_orchestration_runs
            WHERE orchestration_status = 'FAILED'
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Failed Orchestrations",
                "status": (
                    "PASS"
                    if count == 0
                    else "WARNING"
                ),
                "message": (
                    f"{count} failed orchestration(s) found."
                ),
            }
        )

        # ------------------------------------------------------
        # PENDING APPROVALS
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM agent_approval_requests
            WHERE approval_status = 'PENDING'
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Pending Approvals",
                "status": (
                    "PASS"
                    if count == 0
                    else "WARNING"
                ),
                "message": (
                    f"{count} pending approval(s) found."
                ),
            }
        )

        # ------------------------------------------------------
        # FAILED NOTIFICATIONS
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM agent_notification_outbox
            WHERE notification_status = 'FAILED'
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Failed Notifications",
                "status": (
                    "PASS"
                    if count == 0
                    else "FAIL"
                ),
                "message": (
                    f"{count} failed notification(s) found."
                ),
            }
        )

        # ------------------------------------------------------
        # STUCK PROCESSING NOTIFICATIONS
        # ------------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM agent_notification_outbox
            WHERE notification_status = 'PROCESSING'
              AND updated_at < SYSTIMESTAMP - INTERVAL '30' MINUTE
            """
        )

        count = cursor.fetchone()[0]

        results.append(
            {
                "check": "Stuck Notifications",
                "status": (
                    "PASS"
                    if count == 0
                    else "WARNING"
                ),
                "message": (
                    f"{count} stuck notification(s) found."
                ),
            }
        )

        return results

    finally:
        cursor.close()


# ==============================================================
# DISPLAY WORKFLOW HEALTH
# ==============================================================

def show_agent_workflow_health(
    connection: Any,
) -> None:
    print()
    print("=" * 78)
    print("AGENT WORKFLOW HEALTH")
    print("=" * 78)

    results = check_agent_workflow_health(
        connection
    )

    for result in results:
        print()
        print(
            f"[{result['status']}] "
            f"{result['check']}"
        )

        print(
            f"    {result['message']}"
        )

    print()
    print("=" * 78)

# ==============================================================
# PRODUCTION READINESS REPORT
# ==============================================================

def show_production_readiness(
    connection: Any,
) -> None:
    results = []

    # Database connection
    results.append(
        check_database_connection(
            connection
        )
    )

    # Schema
    results.extend(
        check_required_tables(
            connection
        )
    )

    results.extend(
        check_required_views(
            connection
        )
    )

    # AR data
    results.extend(
        check_ar_data_integrity(
            connection
        )
    )

    # Agent workflow
    results.extend(
        check_agent_workflow_health(
            connection
        )
    )

    pass_count = sum(
        1
        for result in results
        if result["status"] == "PASS"
    )

    warning_count = sum(
        1
        for result in results
        if result["status"] == "WARNING"
    )

    fail_count = sum(
        1
        for result in results
        if result["status"] == "FAIL"
    )

    total_checks = len(
        results
    )

    if fail_count > 0:
        overall_status = "FAIL"

    elif warning_count > 0:
        overall_status = "WARNING"

    else:
        overall_status = "PASS"

    readiness_score = 0.0

    if total_checks > 0:
        readiness_score = (
            pass_count
            / total_checks
        ) * 100

    print()
    print("=" * 78)
    print("PRODUCTION READINESS REPORT")
    print("=" * 78)

    print()
    print(
        f"Total Checks      : "
        f"{total_checks}"
    )

    print(
        f"Passed            : "
        f"{pass_count}"
    )

    print(
        f"Warnings          : "
        f"{warning_count}"
    )

    print(
        f"Failed            : "
        f"{fail_count}"
    )

    print(
        f"Readiness Score   : "
        f"{readiness_score:.1f}%"
    )

    print()
    print("-" * 78)

    print(
        f"Overall Status    : "
        f"{overall_status}"
    )

    print("-" * 78)

    print()

    if overall_status == "PASS":
        print(
            "The Oracle AI Accounts Receivable "
            "Agent passed all production "
            "readiness checks."
        )

    elif overall_status == "WARNING":
        print(
            "The Oracle AI Accounts Receivable "
            "Agent is operational, but some "
            "warnings should be reviewed before "
            "production deployment."
        )

    else:
        print(
            "The Oracle AI Accounts Receivable "
            "Agent has failed one or more "
            "critical validation checks."
        )

    print()
    print("=" * 78)
# ==============================================================
# MAIN
# ==============================================================

def main() -> None:
    print("=" * 78)
    print("Oracle AI Accounts Receivable Agent")
    print("Day 23 - Validation & Production Hardening")
    print("=" * 78)

    connection = get_connection()

    try:
        show_schema_health(
            connection
        )
        show_ar_data_health(
            connection
        )
        show_agent_workflow_health(
            connection
        )
        show_production_readiness(
            connection
        )

    except Exception as error:
        print()
        print(
            f"Day 23 validation failed: "
            f"{error}"
        )

    finally:
        connection.close()

        print()
        print(
            "Oracle connection closed."
        )


# ==============================================================
# PROGRAM ENTRY POINT
# ==============================================================

if __name__ == "__main__":
    main()