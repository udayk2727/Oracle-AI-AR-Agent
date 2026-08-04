from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from dataclasses import dataclass, field

from agent_tool_client import (
    get_collection_queue,
    get_connection,
    get_customer_summary,
    get_invoice_details,
    get_overdue_invoices,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

MODEL = os.getenv("OPENAI_MODEL", "gpt-5")


def validate_environment() -> None:
    """Confirm that required AI configuration exists."""

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is missing from the project .env file."
        )


def create_client() -> OpenAI:
    """Create the OpenAI client."""

    validate_environment()
    return OpenAI()


TOOLS = [
    {
        "type": "function",
        "name": "get_customer_summary",
        "description": (
            "Return the Accounts Receivable collection and risk summary "
            "for one customer."
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
            "Return overdue invoices for one customer, including days "
            "past due, aging bucket, priority, and recommended action."
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
            "Return the prioritized AR collection queue. The optional "
            "priority may be CRITICAL, HIGH, MEDIUM, LOW, or MONITOR."
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
                    "description": (
                        "Optional collection-priority filter."
                    ),
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
            "Return detailed AR information for one invoice number."
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


ROUTER_INSTRUCTIONS = """
You are the routing component of an Oracle Accounts Receivable Agent.

Choose exactly one available tool when the user's question can be answered
using an AR tool.

Routing rules:
- Customer account, balance, risk, or overall collection summary:
  get_customer_summary
- Overdue invoices for a particular customer:
  get_overdue_invoices
- Collection work queue, accounts to contact, or invoices by priority:
  get_collection_queue
- Details or status of a particular invoice:
  get_invoice_details

Never invent customer IDs or invoice numbers.
If a required identifier is missing, ask the user for it instead of
calling a tool.
"""
ANSWER_INSTRUCTIONS = """
You are an Oracle Accounts Receivable collections assistant.

Use only the Oracle tool results provided to you.

Rules:
- Do not invent customers, invoices, balances, dates, or statuses.
- Clearly state when no records were returned.
- Summarize the most important financial information first.
- Mention outstanding amount, days past due, aging bucket,
  collection priority, and recommended action when available.
- Use concise, professional, human-friendly language.
- Format monetary amounts using dollars and two decimal places.
- If multiple invoices are returned, summarize the overall result
  and list only the most important records.
"""
FOLLOW_UP_INSTRUCTIONS = """
You are an Oracle Accounts Receivable conversation assistant.

Answer the user's follow-up question using only the supplied Oracle
records and conversation context.

Rules:
- Do not invent financial facts.
- Do not change the customer or invoice unless the user clearly asks.
- Use the previous Oracle records when the question refers to
  "it", "that customer", "those invoices", "the oldest one",
  "the highest one", or similar follow-up language.
- Clearly say when the available records are insufficient.
- Keep the response professional and easy to understand.
- Format money using dollars and two decimal places.
"""

@dataclass
class ConversationState:
    """Store short-term AR conversation context."""

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


def route_question(question: str) -> dict[str, Any]:
    """Ask the model to select an appropriate AR tool."""

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
                "call_id": item.call_id,
            }

    return {
        "action": "respond",
        "message": response.output_text,
    }


def is_follow_up_question(question: str) -> bool:
    """Identify questions that depend on prior conversation context."""

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

def main() -> None:
    print("=" * 65)
    print("Oracle AI Accounts Receivable Agent — Conversation Mode")
    print("=" * 65)

    print(
        "\nAsk an AR question. Type 'exit' to stop, "
        "'clear' to reset memory, or 'context' to inspect memory."
    )

    state = ConversationState()

    while True:
        question = input("\nYou: ").strip()

        if not question:
            print("Please enter a question.")
            continue

        command = question.lower()

        if command in {"exit", "quit"}:
            print("\nAgent: Conversation ended.")
            break

        if command == "clear":
            state.clear()
            print("\nAgent: Conversation memory cleared.")
            continue

        if command == "context":
            print("\nCurrent conversation context:")
            print(
                json.dumps(
                    {
                        "customer_id": state.customer_id,
                        "invoice_number": state.invoice_number,
                        "last_tool_name": state.last_tool_name,
                        "last_tool_arguments": state.last_tool_arguments,
                        "last_record_count": len(state.last_records),
                    },
                    indent=2,
                    default=str,
                )
            )
            continue

        state.remember_user_message(question)

        try:
            if is_follow_up_question(question) and state.last_records:
                final_answer = generate_follow_up_answer(
                    question=question,
                    state=state,
                )

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

                    print(f"Rows returned: {len(records)}")

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

            state.remember_agent_message(final_answer)

            print("\nAgent:")
            print(final_answer)

        except Exception as error:
            print("\nAgent error:")
            print(error)



def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    print("Opening Oracle connection...")
    connection = get_connection()
    print("Oracle connection opened.")

    try:
        if tool_name == "get_overdue_invoices":
            print("Calling overdue invoice procedure...")

            records = get_overdue_invoices(
                connection,
                arguments["customer_id"],
            )

            print("Oracle procedure completed.")
            return records

        if tool_name == "get_customer_summary":
            return get_customer_summary(
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

        raise ValueError(f"Unsupported tool: {tool_name}")

    finally:
        print("Closing Oracle connection...")
        connection.close()

def generate_final_answer(
    question: str,
    tool_name: str,
    arguments: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    """Convert trusted Oracle results into a natural-language answer."""

    if not records:
        return (
            "No matching Accounts Receivable records were found "
            "for that request."
        )

    client = create_client()

    limited_records = records[:20]

    prompt = {
        "user_question": question,
        "oracle_tool": tool_name,
        "tool_arguments": arguments,
        "records_returned": len(records),
        "oracle_results": limited_records,
    }

    print("Generating natural-language answer...")

    response = client.responses.create(
        model=MODEL,
        instructions=ANSWER_INSTRUCTIONS,
        input=json.dumps(
            prompt,
            default=str,
        ),
    )

    print("Natural-language answer generated.")

    return response.output_text

def generate_follow_up_answer(
    question: str,
    state: ConversationState,
) -> str:
    """Answer using the previous trusted Oracle result."""

    if not state.last_records:
        return (
            "I do not have previous Oracle results for this "
            "conversation. Please first ask for a customer summary, "
            "invoice details, overdue invoices, or collection queue."
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

    print("Generating follow-up answer...")

    response = client.responses.create(
        model=MODEL,
        instructions=FOLLOW_UP_INSTRUCTIONS,
        input=json.dumps(
            context,
            default=str,
        ),
    )

    print("Follow-up answer generated.")

    return response.output_text


if __name__ == "__main__":
    main()