from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI

from agent_tool_client import (
    get_collection_queue,
    get_connection,
    get_customer_summary,
    get_invoice_details,
    get_overdue_invoices,
)


# ==============================================================
# PROJECT CONFIGURATION
# ==============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(
    PROJECT_ROOT / ".env",
    override=True,
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5")


# ==============================================================
# CONVERSATION MEMORY
# ==============================================================

@dataclass
class ConversationState:
    """Store temporary context while the Python program is running."""

    customer_id: int | None = None
    invoice_number: str | None = None
    last_tool_name: str | None = None
    last_tool_arguments: dict[str, Any] = field(default_factory=dict)
    last_records: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)

    def remember_user_message(self, message: str) -> None:
        self.history.append(
            {
                "role": "user",
                "content": message,
            }
        )

    def remember_agent_message(self, message: str) -> None:
        self.history.append(
            {
                "role": "assistant",
                "content": message,
            }
        )

    def update_tool_context(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        records: list[dict[str, Any]],
    ) -> None:
        self.last_tool_name = tool_name
        self.last_tool_arguments = arguments
        self.last_records = records

        customer_id = arguments.get("customer_id")

        if customer_id is not None:
            self.customer_id = int(customer_id)

        invoice_number = arguments.get("invoice_number")

        if invoice_number:
            self.invoice_number = str(invoice_number)

    def clear(self) -> None:
        self.customer_id = None
        self.invoice_number = None
        self.last_tool_name = None
        self.last_tool_arguments = {}
        self.last_records = []
        self.history = []


# ==============================================================
# OPENAI TOOL DEFINITIONS
# ==============================================================

TOOLS = [
    {
        "type": "function",
        "name": "get_customer_summary",
        "description": (
            "Return the Accounts Receivable balance, collection risk, "
            "payment history, and overall collection summary for one customer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "The Oracle customer ID.",
                }
            },
            "required": ["customer_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_overdue_invoices",
        "description": (
            "Return overdue invoices for one customer, including days past "
            "due, aging bucket, collection priority, and recommended action."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "The Oracle customer ID.",
                }
            },
            "required": ["customer_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_collection_queue",
        "description": (
            "Return the prioritized Accounts Receivable collection queue. "
            "Priority may be CRITICAL, HIGH, MEDIUM, LOW, MONITOR, or null."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": ["string", "null"],
                    "enum": [
                        "CRITICAL",
                        "HIGH",
                        "MEDIUM",
                        "LOW",
                        "MONITOR",
                        None,
                    ],
                    "description": "Optional collection-priority filter.",
                }
            },
            "required": ["priority"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_invoice_details",
        "description": (
            "Return detailed Accounts Receivable information for one "
            "invoice number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_number": {
                    "type": "string",
                    "description": "The invoice number.",
                }
            },
            "required": ["invoice_number"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# ==============================================================
# OPENAI INSTRUCTIONS
# ==============================================================

ROUTER_INSTRUCTIONS = """
You are the routing component of an Oracle Accounts Receivable Agent.

Choose exactly one available tool when the user's question can be
answered using an approved Accounts Receivable tool.

Routing rules:

- Customer account, balance, risk, payment behavior, or overall
  collection summary:
  get_customer_summary

- Overdue invoices for a particular customer:
  get_overdue_invoices

- Collection queue, accounts to contact, collection priorities,
  or invoices requiring action:
  get_collection_queue

- Details, status, balance, or payment information for a specific invoice:
  get_invoice_details

Never invent customer IDs or invoice numbers.

When a required identifier is missing, ask the user to provide it
instead of calling a tool.
"""


ANSWER_INSTRUCTIONS = """
You are an Oracle Accounts Receivable collections assistant.

Use only the supplied Oracle tool results.

Rules:

- Never invent customers, invoices, balances, dates, statuses, or actions.
- Clearly state when no records were returned.
- Summarize the most important financial information first.
- Mention outstanding amount, days past due, aging bucket,
  collection priority, and recommended action when available.
- Use professional and human-friendly language.
- Format monetary amounts using dollars and two decimal places.
- When multiple invoices are returned, summarize the overall situation
  and mention only the most important records.
"""


FOLLOW_UP_INSTRUCTIONS = """
You are an Oracle Accounts Receivable conversation assistant.

Answer the follow-up question using only the supplied Oracle records
and conversation context.

Rules:

- Never invent financial facts.
- Do not switch to another customer or invoice unless the user clearly asks.
- Use previous Oracle records when the user says phrases such as:
  "which one", "the oldest one", "that customer", "those invoices",
  "what action should we take", or similar follow-up language.
- Clearly state when the available records are insufficient.
- Keep the response professional and easy to understand.
- Format monetary amounts using dollars and two decimal places.
"""


# ==============================================================
# OPENAI CLIENT
# ==============================================================

def validate_environment() -> None:
    """Verify that the OpenAI API configuration exists."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is missing from the project .env file."
        )


def create_client() -> OpenAI:
    """Create the OpenAI API client."""

    validate_environment()
    return OpenAI()


# ==============================================================
# QUESTION ROUTING
# ==============================================================

def route_question(question: str) -> dict[str, Any]:
    """Ask the model to choose one approved Oracle AR tool."""

    client = create_client()

    response = client.responses.create(
        model=MODEL,
        instructions=ROUTER_INSTRUCTIONS,
        tools=TOOLS,
        input=question,
    )

    for item in response.output:
        if item.type == "function_call":
            return {
                "action": "call_tool",
                "tool_name": item.name,
                "arguments": json.loads(item.arguments),
            }

    return {
        "action": "respond",
        "message": response.output_text,
    }


# ==============================================================
# ORACLE TOOL EXECUTION
# ==============================================================

def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    """Open Oracle, execute one approved AR tool, and close the connection."""

    connection = get_connection()

    try:
        if tool_name == "get_customer_summary":
            return get_customer_summary(
                connection,
                arguments["customer_id"],
            )

        if tool_name == "get_overdue_invoices":
            return get_overdue_invoices(
                connection,
                arguments["customer_id"],
            )

        if tool_name == "get_collection_queue":
            return get_collection_queue(
                connection,
                arguments.get("priority"),
            )

        if tool_name == "get_invoice_details":
            return get_invoice_details(
                connection,
                arguments["invoice_number"],
            )

        raise ValueError(
            f"Unsupported Oracle tool: {tool_name}"
        )

    finally:
        connection.close()


# ==============================================================
# NATURAL-LANGUAGE ANSWERS
# ==============================================================

def generate_final_answer(
    question: str,
    tool_name: str,
    arguments: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    """Convert trusted Oracle records into a human-friendly response."""

    if not records:
        return (
            "No matching Accounts Receivable records were found "
            "for that request."
        )

    client = create_client()

    prompt = {
        "user_question": question,
        "oracle_tool": tool_name,
        "tool_arguments": arguments,
        "records_returned": len(records),
        "oracle_results": records[:20],
    }

    response = client.responses.create(
        model=MODEL,
        instructions=ANSWER_INSTRUCTIONS,
        input=json.dumps(
            prompt,
            default=str,
        ),
    )

    return response.output_text


def generate_follow_up_answer(
    question: str,
    state: ConversationState,
) -> str:
    """Answer a follow-up question using previous trusted Oracle results."""

    if not state.last_records:
        return (
            "I do not have previous Oracle results for this conversation. "
            "Please first ask for a customer summary, invoice details, "
            "overdue invoices, or a collection queue."
        )

    client = create_client()

    context = {
        "current_customer_id": state.customer_id,
        "current_invoice_number": state.invoice_number,
        "previous_oracle_tool": state.last_tool_name,
        "previous_tool_arguments": state.last_tool_arguments,
        "previous_records_returned": len(state.last_records),
        "previous_oracle_results": state.last_records[:20],
        "recent_conversation": state.history[-6:],
        "follow_up_question": question,
    }

    response = client.responses.create(
        model=MODEL,
        instructions=FOLLOW_UP_INSTRUCTIONS,
        input=json.dumps(
            context,
            default=str,
        ),
    )

    return response.output_text


def is_follow_up_question(question: str) -> bool:
    """Identify common questions that depend on prior context."""

    normalized = question.strip().lower()

    follow_up_phrases = (
        "which one",
        "which invoice",
        "the oldest",
        "the newest",
        "the highest",
        "the largest",
        "the lowest",
        "what action",
        "what should we do",
        "what should i do",
        "tell me more",
        "explain that",
        "why is it",
        "why is that",
        "those invoices",
        "that customer",
        "that invoice",
        "this customer",
        "this invoice",
        "summarize them",
        "summarize it",
    )

    return any(
        phrase in normalized
        for phrase in follow_up_phrases
    )


# ==============================================================
#  ORACLE AUDIT FUNCTIONS
# ==============================================================

def start_conversation(connection: Any) -> str:
    """Create an Oracle audit record for a new conversation."""

    conversation_id = str(uuid4())
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


def log_agent_activity(
    connection: Any,
    conversation_id: str,
    activity_type: str,
    *,
    user_question: str | None = None,
    tool_name: str | None = None,
    tool_arguments: dict[str, Any] | None = None,
    records_returned: int | None = None,
    agent_response: str | None = None,
    execution_status: str = "SUCCESS",
    error_message: str | None = None,
) -> None:
    """Insert one agent audit event into Oracle."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO agent_activity_log
            (
                conversation_id,
                activity_type,
                user_question,
                tool_name,
                tool_arguments,
                records_returned,
                agent_response,
                execution_status,
                error_message
            )
            VALUES
            (
                :conversation_id,
                :activity_type,
                :user_question,
                :tool_name,
                :tool_arguments,
                :records_returned,
                :agent_response,
                :execution_status,
                :error_message
            )
            """,
            {
                "conversation_id": conversation_id,
                "activity_type": activity_type,
                "user_question": user_question,
                "tool_name": tool_name,
                "tool_arguments": (
                    json.dumps(
                        tool_arguments,
                        default=str,
                    )
                    if tool_arguments is not None
                    else None
                ),
                "records_returned": records_returned,
                "agent_response": agent_response,
                "execution_status": execution_status,
                "error_message": error_message,
            },
        )

        connection.commit()

    finally:
        cursor.close()


def end_conversation(
    connection: Any,
    conversation_id: str,
    status: str = "COMPLETED",
) -> None:
    """Mark the conversation as completed or failed."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE agent_conversations
            SET
                ended_at = SYSTIMESTAMP,
                conversation_status = :status
            WHERE conversation_id = :conversation_id
            """,
            {
                "status": status,
                "conversation_id": conversation_id,
            },
        )

        connection.commit()

    finally:
        cursor.close()


# ==============================================================
# MAIN CONVERSATION PROGRAM
# ==============================================================

def main() -> None:
    print("=" * 72)
    print("Oracle AI Accounts Receivable Agent — Approved Action Execution")
    print("=" * 72)

    print(
        "\nCommands:"
        "\n  request reminder <invoice_number>  Create reminder approval request"
        "\n  approvals                          Show pending approvals"
        "\n  approve <approval_id>              Approve a request"
        "\n  reject <approval_id>               Reject a request"
        "\n  execute <approval_id>              Execute an approved action"
        "\n  clear                              Clear conversation memory"
        "\n  context                            Display conversation context"
        "\n  exit                               End conversation"
    )

    state = ConversationState()

    audit_connection = get_connection()
    conversation_id = start_conversation(audit_connection)

    print(f"\nConversation ID: {conversation_id}")

    conversation_closed = False

    try:
        while True:
            question = input("\nYou: ").strip()

            if not question:
                print("Please enter a question.")
                continue

            command = question.lower()

            # ==================================================
            # EXIT
            # ==================================================

            if command in {"exit", "quit"}:
                log_agent_activity(
                    connection=audit_connection,
                    conversation_id=conversation_id,
                    activity_type="SESSION_END",
                    user_question=question,
                )

                end_conversation(
                    connection=audit_connection,
                    conversation_id=conversation_id,
                    status="COMPLETED",
                )

                conversation_closed = True

                print("\nAgent: Conversation ended.")
                break

            # ==================================================
            # CLEAR MEMORY
            # ==================================================

            if command == "clear":
                state.clear()

                log_agent_activity(
                    connection=audit_connection,
                    conversation_id=conversation_id,
                    activity_type="MEMORY_CLEAR",
                    user_question=question,
                )

                print("\nAgent: Conversation memory cleared.")
                continue

            # ==================================================
            # CONTEXT
            # ==================================================

            if command == "context":
                current_context = {
                    "conversation_id": conversation_id,
                    "customer_id": state.customer_id,
                    "invoice_number": state.invoice_number,
                    "last_tool_name": state.last_tool_name,
                    "last_tool_arguments": state.last_tool_arguments,
                    "last_record_count": len(state.last_records),
                    "history_message_count": len(state.history),
                }

                print("\nCurrent conversation context:")
                print(
                    json.dumps(
                        current_context,
                        indent=2,
                        default=str,
                    )
                )

                continue

            # ==================================================
            # CREATE APPROVAL REQUEST
            # ==================================================

            if command.startswith("request reminder "):
                parts = question.split(maxsplit=2)

                if len(parts) < 3:
                    print(
                        "\nAgent: Please provide an invoice number."
                    )
                    continue

                invoice_number = parts[2].strip()

                approval_id = create_approval_request(
                    connection=audit_connection,
                    conversation_id=conversation_id,
                    action_type="SEND_PAYMENT_REMINDER",
                    action_description=(
                        "Send a payment reminder for invoice "
                        f"{invoice_number}."
                    ),
                    action_payload={
                        "invoice_number": invoice_number,
                        "channel": "EMAIL",
                    },
                )

                log_agent_activity(
                    connection=audit_connection,
                    conversation_id=conversation_id,
                    activity_type="APPROVAL_REQUEST",
                    user_question=question,
                    tool_name="SEND_PAYMENT_REMINDER",
                    tool_arguments={
                        "invoice_number": invoice_number,
                        "approval_id": approval_id,
                    },
                )

                print(
                    "\nAgent: This action requires human approval."
                )
                print(
                    f"Approval request {approval_id} was created."
                )

                continue

            # ==================================================
            # LIST PENDING APPROVALS
            # ==================================================

            if command == "approvals":
                pending = get_pending_approvals(
                    audit_connection
                )

                if not pending:
                    print("\nAgent: No pending approvals.")

                else:
                    print("\nPending approvals:")

                    for request in pending:
                        print(
                            f"\nApproval ID: "
                            f"{request['APPROVAL_ID']}"
                        )

                        print(
                            f"Action: "
                            f"{request['ACTION_TYPE']}"
                        )

                        print(
                            f"Description: "
                            f"{request['ACTION_DESCRIPTION']}"
                        )

                        print(
                            f"Requested at: "
                            f"{request['REQUESTED_AT']}"
                        )

                        print(
                            f"Status: "
                            f"{request['APPROVAL_STATUS']}"
                        )

                continue

            # ==================================================
            # APPROVE REQUEST
            # ==================================================

            if command.startswith("approve "):
                parts = command.split(maxsplit=1)

                if len(parts) < 2:
                    print(
                        "\nAgent: Please provide an approval ID."
                    )
                    continue

                try:
                    approval_id = int(parts[1])

                except ValueError:
                    print(
                        "\nAgent: Approval ID must be a number."
                    )
                    continue

                updated = decide_approval(
                    connection=audit_connection,
                    approval_id=approval_id,
                    decision="APPROVED",
                    reviewed_by="AR_MANAGER",
                    comments="Approved from agent console.",
                )

                if updated:
                    log_agent_activity(
                        connection=audit_connection,
                        conversation_id=conversation_id,
                        activity_type="APPROVAL_DECISION",
                        user_question=question,
                        tool_name="APPROVE_REQUEST",
                        tool_arguments={
                            "approval_id": approval_id,
                            "decision": "APPROVED",
                        },
                    )

                    print(
                        f"\nAgent: Approval request "
                        f"{approval_id} was approved."
                    )

                    print(
                        "You can now execute it using:"
                    )

                    print(
                        f"execute {approval_id}"
                    )

                else:
                    print(
                        "\nAgent: The approval request was not "
                        "found or is no longer pending."
                    )

                continue

            # ==================================================
            # REJECT REQUEST
            # ==================================================

            if command.startswith("reject "):
                parts = command.split(maxsplit=1)

                if len(parts) < 2:
                    print(
                        "\nAgent: Please provide an approval ID."
                    )
                    continue

                try:
                    approval_id = int(parts[1])

                except ValueError:
                    print(
                        "\nAgent: Approval ID must be a number."
                    )
                    continue

                updated = decide_approval(
                    connection=audit_connection,
                    approval_id=approval_id,
                    decision="REJECTED",
                    reviewed_by="AR_MANAGER",
                    comments="Rejected from agent console.",
                )

                if updated:
                    log_agent_activity(
                        connection=audit_connection,
                        conversation_id=conversation_id,
                        activity_type="APPROVAL_DECISION",
                        user_question=question,
                        tool_name="REJECT_REQUEST",
                        tool_arguments={
                            "approval_id": approval_id,
                            "decision": "REJECTED",
                        },
                    )

                    print(
                        f"\nAgent: Approval request "
                        f"{approval_id} was rejected."
                    )

                else:
                    print(
                        "\nAgent: The approval request was not "
                        "found or is no longer pending."
                    )

                continue

            # ==================================================
            # EXECUTE APPROVED ACTION
            # ==================================================

            if command.startswith("execute "):
                parts = command.split(maxsplit=1)

                if len(parts) < 2:
                    print(
                        "\nAgent: Please provide an approval ID."
                    )
                    continue

                try:
                    approval_id = int(parts[1])

                except ValueError:
                    print(
                        "\nAgent: Approval ID must be a number."
                    )
                    continue

                try:
                    execution_message = execute_approved_action(
                        connection=audit_connection,
                        approval_id=approval_id,
                    )

                    log_agent_activity(
                        connection=audit_connection,
                        conversation_id=conversation_id,
                        activity_type="ACTION_EXECUTION",
                        user_question=question,
                        tool_name="EXECUTE_APPROVED_ACTION",
                        tool_arguments={
                            "approval_id": approval_id,
                        },
                        agent_response=execution_message,
                    )

                    print("\nAgent:")
                    print(execution_message)

                except Exception as error:
                    log_agent_activity(
                        connection=audit_connection,
                        conversation_id=conversation_id,
                        activity_type="ERROR",
                        user_question=question,
                        execution_status="FAILED",
                        error_message=str(error)[:4000],
                    )

                    print("\nAgent:")
                    print(error)

                continue

            # ==================================================
            # NORMAL AI / ORACLE FLOW
            # ==================================================

            state.remember_user_message(question)

            log_agent_activity(
                connection=audit_connection,
                conversation_id=conversation_id,
                activity_type="USER_MESSAGE",
                user_question=question,
            )

            try:
                # ----------------------------------------------
                # FOLLOW-UP QUESTION
                # ----------------------------------------------

                if (
                    is_follow_up_question(question)
                    and state.last_records
                ):
                    final_answer = generate_follow_up_answer(
                        question=question,
                        state=state,
                    )

                # ----------------------------------------------
                # NEW AI-ROUTED QUESTION
                # ----------------------------------------------

                else:
                    result = route_question(question)

                    if result["action"] == "call_tool":
                        print(
                            f"\nCalling Oracle tool: "
                            f"{result['tool_name']}"
                        )

                        records = execute_tool(
                            tool_name=result["tool_name"],
                            arguments=result["arguments"],
                        )

                        print(
                            f"Rows returned: {len(records)}"
                        )

                        log_agent_activity(
                            connection=audit_connection,
                            conversation_id=conversation_id,
                            activity_type="TOOL_CALL",
                            user_question=question,
                            tool_name=result["tool_name"],
                            tool_arguments=result["arguments"],
                            records_returned=len(records),
                        )

                        state.update_tool_context(
                            tool_name=result["tool_name"],
                            arguments=result["arguments"],
                            records=records,
                        )

                        final_answer = generate_final_answer(
                            question=question,
                            tool_name=result["tool_name"],
                            arguments=result["arguments"],
                            records=records,
                        )

                    else:
                        final_answer = result["message"]

                # ----------------------------------------------
                # SAVE + LOG AGENT RESPONSE
                # ----------------------------------------------

                state.remember_agent_message(
                    final_answer
                )

                log_agent_activity(
                    connection=audit_connection,
                    conversation_id=conversation_id,
                    activity_type="AGENT_RESPONSE",
                    user_question=question,
                    agent_response=final_answer,
                )

                print("\nAgent:")
                print(final_answer)

            except Exception as error:
                log_agent_activity(
                    connection=audit_connection,
                    conversation_id=conversation_id,
                    activity_type="ERROR",
                    user_question=question,
                    execution_status="FAILED",
                    error_message=str(error)[:4000],
                )

                print("\nAgent error:")
                print(error)

    except KeyboardInterrupt:
        print(
            "\n\nAgent: Keyboard interruption received."
        )

    finally:
        if not conversation_closed:
            try:
                end_conversation(
                    connection=audit_connection,
                    conversation_id=conversation_id,
                    status="ERROR",
                )

            except Exception as close_error:
                print(
                    "Unable to update conversation status:",
                    close_error,
                )

        audit_connection.close()


def create_approval_request(
    connection: Any,
    conversation_id: str,
    action_type: str,
    action_description: str,
    action_payload: dict[str, Any],
) -> int:
    """Create a pending human-approval request in Oracle."""

    cursor = connection.cursor()

    try:
        approval_id = cursor.var(int)

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
                :action_type,
                :action_description,
                :action_payload,
                'PENDING'
            )
            RETURNING approval_id INTO :approval_id
            """,
            {
                "conversation_id": conversation_id,
                "action_type": action_type,
                "action_description": action_description,
                "action_payload": json.dumps(
                    action_payload,
                    default=str,
                ),
                "approval_id": approval_id,
            },
        )

        connection.commit()

        return int(approval_id.getvalue()[0])

    finally:
        cursor.close()

def get_pending_approvals(
    connection: Any,
) -> list[dict[str, Any]]:
    """Return currently pending approval requests."""

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT
                approval_id,
                conversation_id,
                requested_at,
                action_type,
                action_description,
                action_payload,
                approval_status
            FROM agent_approval_requests
            WHERE approval_status = 'PENDING'
            ORDER BY requested_at
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

def decide_approval(
    connection: Any,
    approval_id: int,
    decision: str,
    reviewed_by: str,
    comments: str | None = None,
) -> bool:
    """Approve or reject a pending request."""

    normalized_decision = decision.strip().upper()

    if normalized_decision not in {"APPROVED", "REJECTED"}:
        raise ValueError(
            "Decision must be APPROVED or REJECTED."
        )

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE agent_approval_requests
            SET
                approval_status = :decision,
                reviewed_at = SYSTIMESTAMP,
                reviewed_by = :reviewed_by,
                review_comments = :comments
            WHERE approval_id = :approval_id
              AND approval_status = 'PENDING'
            """,
            {
                "decision": normalized_decision,
                "reviewed_by": reviewed_by,
                "comments": comments,
                "approval_id": approval_id,
            },
        )

        connection.commit()

        return cursor.rowcount == 1

    finally:
        cursor.close()

def get_approval_request(
    connection: Any,
    approval_id: int,
) -> dict[str, Any] | None:
    """Return one approval request."""

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

        return dict(zip(columns, row))

    finally:
        cursor.close()

def execute_approved_action(
    connection: Any,
    approval_id: int,
) -> str:
    """Execute only a previously approved agent action."""

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

    action_type = approval["ACTION_TYPE"]

    payload_raw = approval["ACTION_PAYLOAD"]

    if hasattr(payload_raw, "read"):
        payload_raw = payload_raw.read()

    payload = json.loads(payload_raw)

    if action_type == "SEND_PAYMENT_REMINDER":
        invoice_number = payload["invoice_number"]

        execution_message = (
            "Payment reminder simulation completed "
            f"for invoice {invoice_number}."
        )

    else:
        raise ValueError(
            f"Unsupported action type: {action_type}"
        )

    cursor = connection.cursor()

    try:
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

    finally:
        cursor.close()

    return execution_message

if __name__ == "__main__":
    main()
