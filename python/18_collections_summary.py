from __future__ import annotations

from typing import Any

from agent_tool_client import get_connection


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


def money(
    value: Any,
) -> str:
    if value is None:
        value = 0

    return f"${float(value):,.2f}"


# ==============================================================
# AR PORTFOLIO KPI
# ==============================================================

def get_ar_portfolio_kpis(
    connection: Any,
) -> dict[str, Any]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_invoices,

                NVL(
                    SUM(invoice_amount),
                    0
                ) AS total_invoice_amount,

                NVL(
                    SUM(amount_paid),
                    0
                ) AS total_amount_paid,

                NVL(
                    SUM(outstanding_amount),
                    0
                ) AS total_outstanding,

                SUM(
                    CASE
                        WHEN invoice_status = 'PAID'
                        THEN 1
                        ELSE 0
                    END
                ) AS paid_invoices,

                SUM(
                    CASE
                        WHEN invoice_status = 'OPEN'
                        THEN 1
                        ELSE 0
                    END
                ) AS open_invoices,

                SUM(
                    CASE
                        WHEN invoice_status =
                             'PARTIALLY_PAID'
                        THEN 1
                        ELSE 0
                    END
                ) AS partially_paid_invoices

            FROM invoices
            """
        )

        result = fetch_one_as_dict(
            cursor
        )

        if result is None:
            return {}

        return result

    finally:
        cursor.close()


# ==============================================================
# OVERDUE KPI
# ==============================================================

def get_overdue_kpis(
    connection: Any,
) -> dict[str, Any]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS overdue_invoices,

                NVL(
                    SUM(outstanding_amount),
                    0
                ) AS overdue_outstanding,

                NVL(
                    MAX(days_past_due),
                    0
                ) AS maximum_days_past_due,

                NVL(
                    AVG(days_past_due),
                    0
                ) AS average_days_past_due

            FROM vw_ar_aging_detail

            WHERE days_past_due > 0
              AND outstanding_amount > 0
            """
        )

        result = fetch_one_as_dict(
            cursor
        )

        if result is None:
            return {}

        return result

    finally:
        cursor.close()


# ==============================================================
# AGING SUMMARY
# ==============================================================

def get_aging_summary(
    connection: Any,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN TRUNC(SYSDATE) <= TRUNC(due_date)
                    THEN 'CURRENT'

                    WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                         BETWEEN 1 AND 30
                    THEN '1-30 DAYS'

                    WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                         BETWEEN 31 AND 60
                    THEN '31-60 DAYS'

                    WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                         BETWEEN 61 AND 90
                    THEN '61-90 DAYS'

                    ELSE '90+ DAYS'
                END AS aging_bucket,

                COUNT(*) AS invoice_count,

                NVL(
                    SUM(outstanding_amount),
                    0
                ) AS outstanding_amount

            FROM invoices

            WHERE outstanding_amount > 0

            GROUP BY
                CASE
                    WHEN TRUNC(SYSDATE) <= TRUNC(due_date)
                    THEN 'CURRENT'

                    WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                         BETWEEN 1 AND 30
                    THEN '1-30 DAYS'

                    WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                         BETWEEN 31 AND 60
                    THEN '31-60 DAYS'

                    WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                         BETWEEN 61 AND 90
                    THEN '61-90 DAYS'

                    ELSE '90+ DAYS'
                END

            ORDER BY
                CASE
                    CASE
                        WHEN TRUNC(SYSDATE) <= TRUNC(due_date)
                        THEN 'CURRENT'

                        WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                             BETWEEN 1 AND 30
                        THEN '1-30 DAYS'

                        WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                             BETWEEN 31 AND 60
                        THEN '31-60 DAYS'

                        WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                             BETWEEN 61 AND 90
                        THEN '61-90 DAYS'

                        ELSE '90+ DAYS'
                    END

                    WHEN 'CURRENT' THEN 1
                    WHEN '1-30 DAYS' THEN 2
                    WHEN '31-60 DAYS' THEN 3
                    WHEN '61-90 DAYS' THEN 4
                    WHEN '90+ DAYS' THEN 5
                    ELSE 6
                END
            """
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# COLLECTION PRIORITY SUMMARY
# ==============================================================

def get_priority_summary(
    connection: Any,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                collection_priority,
                COUNT(*) AS invoice_count,
                NVL(
                    SUM(outstanding_amount),
                    0
                ) AS outstanding_amount
            FROM
            (
                SELECT
                    outstanding_amount,

                    CASE
                        WHEN TRUNC(SYSDATE) - TRUNC(due_date) > 90
                        THEN 'HIGH'

                        WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                             BETWEEN 61 AND 90
                        THEN 'HIGH'

                        WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                             BETWEEN 31 AND 60
                        THEN 'MEDIUM'

                        WHEN TRUNC(SYSDATE) - TRUNC(due_date)
                             BETWEEN 1 AND 30
                        THEN 'LOW'

                        ELSE 'CURRENT'
                    END AS collection_priority

                FROM invoices

                WHERE outstanding_amount > 0
            )

            WHERE collection_priority <> 'CURRENT'

            GROUP BY collection_priority

            ORDER BY
                CASE collection_priority
                    WHEN 'HIGH' THEN 1
                    WHEN 'MEDIUM' THEN 2
                    WHEN 'LOW' THEN 3
                    ELSE 4
                END
            """
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# ACTION ORCHESTRATOR KPI
# ==============================================================

def get_orchestration_kpis(
    connection: Any,
) -> dict[str, Any]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_orchestrations,

                SUM(
                    CASE
                        WHEN orchestration_status =
                             'COMPLETED'
                        THEN 1
                        ELSE 0
                    END
                ) AS completed,

                SUM(
                    CASE
                        WHEN orchestration_status =
                             'FAILED'
                        THEN 1
                        ELSE 0
                    END
                ) AS failed,

                SUM(
                    CASE
                        WHEN orchestration_status =
                             'WAITING_APPROVAL'
                        THEN 1
                        ELSE 0
                    END
                ) AS waiting_approval,

                SUM(
                    CASE
                        WHEN orchestration_status =
                             'PROCESSING'
                        THEN 1
                        ELSE 0
                    END
                ) AS processing,

                SUM(
                    CASE
                        WHEN orchestration_status =
                             'QUEUED'
                        THEN 1
                        ELSE 0
                    END
                ) AS queued

            FROM agent_orchestration_runs
            """
        )

        result = fetch_one_as_dict(
            cursor
        )

        if result is None:
            return {}

        return result

    finally:
        cursor.close()


# ==============================================================
# APPROVAL KPI
# ==============================================================

def get_approval_kpis(
    connection: Any,
) -> dict[str, Any]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_approvals,

                SUM(
                    CASE
                        WHEN approval_status =
                             'PENDING'
                        THEN 1
                        ELSE 0
                    END
                ) AS pending,

                SUM(
                    CASE
                        WHEN approval_status =
                             'APPROVED'
                        THEN 1
                        ELSE 0
                    END
                ) AS approved,

                SUM(
                    CASE
                        WHEN approval_status =
                             'EXECUTED'
                        THEN 1
                        ELSE 0
                    END
                ) AS executed

            FROM agent_approval_requests
            """
        )

        result = fetch_one_as_dict(
            cursor
        )

        if result is None:
            return {}

        return result

    finally:
        cursor.close()


# ==============================================================
# NOTIFICATION KPI
# ==============================================================

def get_notification_kpis(
    connection: Any,
) -> dict[str, Any]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_notifications,

                SUM(
                    CASE
                        WHEN notification_status =
                             'PENDING'
                        THEN 1
                        ELSE 0
                    END
                ) AS pending,

                SUM(
                    CASE
                        WHEN notification_status =
                             'PROCESSING'
                        THEN 1
                        ELSE 0
                    END
                ) AS processing,

                SUM(
                    CASE
                        WHEN notification_status =
                             'SENT'
                        THEN 1
                        ELSE 0
                    END
                ) AS sent,

                SUM(
                    CASE
                        WHEN notification_status =
                             'FAILED'
                        THEN 1
                        ELSE 0
                    END
                ) AS failed

            FROM agent_notification_outbox
            """
        )

        result = fetch_one_as_dict(
            cursor
        )

        if result is None:
            return {}

        return result

    finally:
        cursor.close()


# ==============================================================
# TOP OVERDUE INVOICES
# ==============================================================

def get_top_overdue_invoices(
    connection: Any,
    limit: int = 10,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT *
            FROM
            (
                SELECT
                    a.invoice_id,
                    a.invoice_number,
                    c.customer_name,
                    a.due_date,
                    a.outstanding_amount,
                    a.days_past_due,
                    a.aging_bucket,
                    a.collection_priority,
                    a.recommended_action

                FROM vw_ar_aging_detail a

                JOIN invoices i
                    ON i.invoice_id =
                       a.invoice_id

                JOIN customers c
                    ON c.customer_id =
                       i.customer_id

                WHERE a.days_past_due > 0
                  AND a.outstanding_amount > 0

                ORDER BY
                    a.days_past_due DESC,
                    a.outstanding_amount DESC
            )

            WHERE ROWNUM <= :row_limit
            """,
            {
                "row_limit": limit,
            },
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# RECENT ORCHESTRATIONS
# ==============================================================

def get_recent_orchestrations(
    connection: Any,
    limit: int = 10,
) -> list[dict[str, Any]]:
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT *
            FROM
            (
                SELECT
                    orchestration_id,
                    invoice_number,
                    orchestration_status,
                    current_step,
                    approval_id,
                    notification_id,
                    started_at,
                    completed_at,
                    error_message

                FROM agent_orchestration_runs

                ORDER BY
                    orchestration_id DESC
            )

            WHERE ROWNUM <= :row_limit
            """,
            {
                "row_limit": limit,
            },
        )

        return fetch_all_as_dicts(
            cursor
        )

    finally:
        cursor.close()


# ==============================================================
# AI COLLECTIONS SUMMARY
# ==============================================================

def generate_collections_summary(
    portfolio: dict[str, Any],
    overdue: dict[str, Any],
    orchestration: dict[str, Any],
    approvals: dict[str, Any],
    notifications: dict[str, Any],
) -> str:

    total_outstanding = float(
        portfolio.get(
            "TOTAL_OUTSTANDING",
            0,
        )
        or 0
    )

    overdue_outstanding = float(
        overdue.get(
            "OVERDUE_OUTSTANDING",
            0,
        )
        or 0
    )

    overdue_invoices = int(
        overdue.get(
            "OVERDUE_INVOICES",
            0,
        )
        or 0
    )

    max_days = int(
        overdue.get(
            "MAXIMUM_DAYS_PAST_DUE",
            0,
        )
        or 0
    )

    completed = int(
        orchestration.get(
            "COMPLETED",
            0,
        )
        or 0
    )

    failed = int(
        orchestration.get(
            "FAILED",
            0,
        )
        or 0
    )

    waiting = int(
        orchestration.get(
            "WAITING_APPROVAL",
            0,
        )
        or 0
    )

    pending_approvals = int(
        approvals.get(
            "PENDING",
            0,
        )
        or 0
    )

    sent_notifications = int(
        notifications.get(
            "SENT",
            0,
        )
        or 0
    )

    failed_notifications = int(
        notifications.get(
            "FAILED",
            0,
        )
        or 0
    )

    overdue_percentage = 0.0

    if total_outstanding > 0:
        overdue_percentage = (
            overdue_outstanding
            / total_outstanding
        ) * 100

    summary_lines = [
        (
            "The Oracle AI Accounts Receivable Agent "
            f"is currently managing "
            f"{money(total_outstanding)} "
            "in outstanding receivables."
        ),
        (
            f"There are {overdue_invoices} overdue "
            f"invoices totaling "
            f"{money(overdue_outstanding)}, "
            f"representing "
            f"{overdue_percentage:.1f}% "
            "of the current outstanding balance."
        ),
    ]

    if overdue_invoices == 0:
        summary_lines.append(
            "There are currently no overdue "
            "invoices requiring collection action."
        )

    elif max_days >= 90:
        summary_lines.append(
            f"The highest-risk invoice is "
            f"{max_days} days past due. "
            "Immediate collection follow-up "
            "should be prioritized."
        )

    elif max_days >= 60:
        summary_lines.append(
            f"The oldest outstanding invoice is "
            f"{max_days} days past due, indicating "
            "elevated collection risk."
        )

    elif max_days >= 30:
        summary_lines.append(
            f"The oldest outstanding invoice is "
            f"{max_days} days past due. "
            "Collection follow-up should continue."
        )

    else:
        summary_lines.append(
            "Overdue exposure is currently "
            "concentrated in relatively recent "
            "delinquencies."
        )

    if waiting > 0 or pending_approvals > 0:
        summary_lines.append(
            f"{max(waiting, pending_approvals)} "
            "collection action(s) are waiting "
            "for manager approval."
        )
    else:
        summary_lines.append(
            "There are no collection actions "
            "currently waiting for manager approval."
        )

    summary_lines.append(
        f"The Action Orchestrator has completed "
        f"{completed} workflow(s), with "
        f"{failed} failed workflow(s)."
    )

    summary_lines.append(
        f"The notification service has successfully "
        f"sent {sent_notifications} reminder(s), "
        f"with {failed_notifications} failed "
        "notification(s)."
    )

    if failed > 0 or failed_notifications > 0:
        summary_lines.append(
            "Operational exceptions were detected. "
            "The AR team should review failed "
            "orchestrations or notification errors."
        )
    else:
        summary_lines.append(
            "No unresolved orchestration or "
            "notification failures are currently "
            "reported."
        )

    return " ".join(
        summary_lines
    )


# ==============================================================
# SHOW DASHBOARD
# ==============================================================

def show_dashboard(
    connection: Any,
) -> None:
    portfolio = get_ar_portfolio_kpis(
        connection
    )

    overdue = get_overdue_kpis(
        connection
    )

    orchestration = get_orchestration_kpis(
        connection
    )

    approvals = get_approval_kpis(
        connection
    )

    notifications = get_notification_kpis(
        connection
    )

    print()
    print("=" * 78)
    print("DAY 22 - AR COLLECTIONS EXECUTIVE DASHBOARD")
    print("=" * 78)

    print()
    print("AR PORTFOLIO")
    print("-" * 78)

    print(
        f"Total Invoices          : "
        f"{portfolio.get('TOTAL_INVOICES', 0)}"
    )

    print(
        f"Total Invoice Amount    : "
        f"{money(portfolio.get('TOTAL_INVOICE_AMOUNT'))}"
    )

    print(
        f"Total Amount Paid       : "
        f"{money(portfolio.get('TOTAL_AMOUNT_PAID'))}"
    )

    print(
        f"Total Outstanding       : "
        f"{money(portfolio.get('TOTAL_OUTSTANDING'))}"
    )

    print(
        f"Paid Invoices           : "
        f"{portfolio.get('PAID_INVOICES', 0)}"
    )

    print(
        f"Open Invoices           : "
        f"{portfolio.get('OPEN_INVOICES', 0)}"
    )

    print(
        f"Partially Paid          : "
        f"{portfolio.get('PARTIALLY_PAID_INVOICES', 0)}"
    )

    print()
    print("OVERDUE EXPOSURE")
    print("-" * 78)

    print(
        f"Overdue Invoices        : "
        f"{overdue.get('OVERDUE_INVOICES', 0)}"
    )

    print(
        f"Overdue Outstanding     : "
        f"{money(overdue.get('OVERDUE_OUTSTANDING'))}"
    )

    print(
        f"Maximum Days Past Due   : "
        f"{overdue.get('MAXIMUM_DAYS_PAST_DUE', 0)}"
    )

    average_days = float(
        overdue.get(
            "AVERAGE_DAYS_PAST_DUE",
            0,
        )
        or 0
    )

    print(
        f"Average Days Past Due   : "
        f"{average_days:.1f}"
    )

    print()
    print("ACTION ORCHESTRATOR")
    print("-" * 78)

    print(
        f"Total Runs              : "
        f"{orchestration.get('TOTAL_ORCHESTRATIONS', 0)}"
    )

    print(
        f"Completed               : "
        f"{orchestration.get('COMPLETED', 0)}"
    )

    print(
        f"Failed                  : "
        f"{orchestration.get('FAILED', 0)}"
    )

    print(
        f"Waiting Approval        : "
        f"{orchestration.get('WAITING_APPROVAL', 0)}"
    )

    print(
        f"Processing              : "
        f"{orchestration.get('PROCESSING', 0)}"
    )

    print(
        f"Queued                  : "
        f"{orchestration.get('QUEUED', 0)}"
    )

    print()
    print("APPROVALS")
    print("-" * 78)

    print(
        f"Total Approvals         : "
        f"{approvals.get('TOTAL_APPROVALS', 0)}"
    )

    print(
        f"Pending                 : "
        f"{approvals.get('PENDING', 0)}"
    )

    print(
        f"Approved                : "
        f"{approvals.get('APPROVED', 0)}"
    )

    print(
        f"Executed                : "
        f"{approvals.get('EXECUTED', 0)}"
    )

    print()
    print("NOTIFICATIONS")
    print("-" * 78)

    print(
        f"Total Notifications     : "
        f"{notifications.get('TOTAL_NOTIFICATIONS', 0)}"
    )

    print(
        f"Pending                 : "
        f"{notifications.get('PENDING', 0)}"
    )

    print(
        f"Processing              : "
        f"{notifications.get('PROCESSING', 0)}"
    )

    print(
        f"Sent                    : "
        f"{notifications.get('SENT', 0)}"
    )

    print(
        f"Failed                  : "
        f"{notifications.get('FAILED', 0)}"
    )

    print()
    print("=" * 78)


# ==============================================================
# SHOW AGING
# ==============================================================

def show_aging(
    connection: Any,
) -> None:
    rows = get_aging_summary(
        connection
    )

    print()
    print("=" * 78)
    print("AR AGING SUMMARY")
    print("=" * 78)

    if not rows:
        print(
            "No outstanding aging records found."
        )
        return

    for row in rows:
        print()

        print(
            f"Aging Bucket       : "
            f"{row['AGING_BUCKET']}"
        )

        print(
            f"Invoice Count      : "
            f"{row['INVOICE_COUNT']}"
        )

        print(
            f"Outstanding Amount : "
            f"{money(row['OUTSTANDING_AMOUNT'])}"
        )

        print("-" * 78)


# ==============================================================
# SHOW PRIORITY
# ==============================================================

def show_priorities(
    connection: Any,
) -> None:
    rows = get_priority_summary(
        connection
    )

    print()
    print("=" * 78)
    print("COLLECTION PRIORITY SUMMARY")
    print("=" * 78)

    if not rows:
        print(
            "No overdue invoices found."
        )
        return

    for row in rows:
        print()

        print(
            f"Priority           : "
            f"{row['COLLECTION_PRIORITY']}"
        )

        print(
            f"Invoice Count      : "
            f"{row['INVOICE_COUNT']}"
        )

        print(
            f"Outstanding Amount : "
            f"{money(row['OUTSTANDING_AMOUNT'])}"
        )

        print("-" * 78)


# ==============================================================
# SHOW TOP OVERDUE
# ==============================================================

def show_top_overdue(
    connection: Any,
) -> None:
    rows = get_top_overdue_invoices(
        connection
    )

    print()
    print("=" * 90)
    print("TOP OVERDUE COLLECTION TARGETS")
    print("=" * 90)

    if not rows:
        print(
            "No overdue invoices found."
        )
        return

    for row in rows:
        print()

        print(
            f"Invoice            : "
            f"{row['INVOICE_NUMBER']}"
        )

        print(
            f"Customer           : "
            f"{row['CUSTOMER_NAME']}"
        )

        print(
            f"Due Date           : "
            f"{row['DUE_DATE']}"
        )

        print(
            f"Outstanding        : "
            f"{money(row['OUTSTANDING_AMOUNT'])}"
        )

        print(
            f"Days Past Due      : "
            f"{row['DAYS_PAST_DUE']}"
        )

        print(
            f"Aging Bucket       : "
            f"{row['AGING_BUCKET']}"
        )

        print(
            f"Priority           : "
            f"{row['COLLECTION_PRIORITY']}"
        )

        print(
            f"Recommended Action : "
            f"{row['RECOMMENDED_ACTION']}"
        )

        print("-" * 90)


# ==============================================================
# SHOW RECENT ACTIONS
# ==============================================================

def show_recent_actions(
    connection: Any,
) -> None:
    rows = get_recent_orchestrations(
        connection
    )

    print()
    print("=" * 90)
    print("RECENT AGENT ACTIONS")
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
            f"Status           : "
            f"{row['ORCHESTRATION_STATUS']}"
        )

        print(
            f"Current Step     : "
            f"{row['CURRENT_STEP']}"
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


# ==============================================================
# SHOW AI COLLECTIONS SUMMARY
# ==============================================================

def show_ai_summary(
    connection: Any,
) -> None:
    portfolio = get_ar_portfolio_kpis(
        connection
    )

    overdue = get_overdue_kpis(
        connection
    )

    orchestration = get_orchestration_kpis(
        connection
    )

    approvals = get_approval_kpis(
        connection
    )

    notifications = get_notification_kpis(
        connection
    )

    summary = generate_collections_summary(
        portfolio,
        overdue,
        orchestration,
        approvals,
        notifications,
    )

    print()
    print("=" * 78)
    print("AI COLLECTIONS MANAGEMENT SUMMARY")
    print("=" * 78)

    print()
    print(summary)

    print()
    print("=" * 78)


# ==============================================================
# FULL REPORT
# ==============================================================

def show_full_report(
    connection: Any,
) -> None:
    show_dashboard(
        connection
    )

    show_aging(
        connection
    )

    show_priorities(
        connection
    )

    show_top_overdue(
        connection
    )

    show_recent_actions(
        connection
    )

    show_ai_summary(
        connection
    )


# ==============================================================
# MAIN
# ==============================================================

def main() -> None:
    print("=" * 78)
    print("Oracle AI Accounts Receivable Agent")
    print("Day 22 - Collections Reporting & AI Summary")
    print("=" * 78)

    print(
        "\nCommands:"
        "\n  dashboard    Show AR collections KPIs"
        "\n  aging        Show aging bucket summary"
        "\n  priority     Show collection priorities"
        "\n  overdue      Show top overdue invoices"
        "\n  actions      Show recent agent actions"
        "\n  summary      Show AI collections summary"
        "\n  report       Show complete Day 22 report"
        "\n  exit         Close reporting console"
    )

    connection = get_connection()

    try:
        while True:
            command = input(
                "\nCollections> "
            ).strip()

            if not command:
                continue

            command_lower = (
                command.lower()
            )

            # ==================================================
            # DASHBOARD
            # ==================================================

            if command_lower == "dashboard":
                try:
                    show_dashboard(
                        connection
                    )

                except Exception as error:
                    print()
                    print(
                        f"Dashboard failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # AGING
            # ==================================================

            if command_lower == "aging":
                try:
                    show_aging(
                        connection
                    )

                except Exception as error:
                    print()
                    print(
                        f"Aging report failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # PRIORITY
            # ==================================================

            if command_lower == "priority":
                try:
                    show_priorities(
                        connection
                    )

                except Exception as error:
                    print()
                    print(
                        f"Priority report failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # OVERDUE
            # ==================================================

            if command_lower == "overdue":
                try:
                    show_top_overdue(
                        connection
                    )

                except Exception as error:
                    print()
                    print(
                        f"Overdue report failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # ACTIONS
            # ==================================================

            if command_lower == "actions":
                try:
                    show_recent_actions(
                        connection
                    )

                except Exception as error:
                    print()
                    print(
                        f"Action report failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # AI SUMMARY
            # ==================================================

            if command_lower == "summary":
                try:
                    show_ai_summary(
                        connection
                    )

                except Exception as error:
                    print()
                    print(
                        f"Summary failed: "
                        f"{error}"
                    )

                continue

            # ==================================================
            # FULL REPORT
            # ==================================================

            if command_lower == "report":
                try:
                    show_full_report(
                        connection
                    )

                except Exception as error:
                    print()
                    print(
                        f"Full report failed: "
                        f"{error}"
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
                    "Collections reporting "
                    "console closed."
                )

                break

            print()
            print(
                f"Unknown command: "
                f"{command}"
            )

            print(
                "Available commands: "
                "dashboard, aging, priority, "
                "overdue, actions, summary, "
                "report, exit"
            )

    except KeyboardInterrupt:
        print()
        print(
            "Collections reporting "
            "interrupted."
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