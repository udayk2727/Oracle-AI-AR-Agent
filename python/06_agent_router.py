from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

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


def main() -> None:
    print("=" * 60)
    print("Oracle AI Accounts Receivable Agent")
    print("=" * 60)

    question = input("\nAsk an AR question: ").strip()

    if not question:
        print("Please enter a question.")
        return

    result = route_question(question)

    if result["action"] == "call_tool":
        print(f"\nCalling Oracle tool: {result['tool_name']}")

        records = execute_tool(
            tool_name=result["tool_name"],
            arguments=result["arguments"],
        )

        print(f"Rows returned: {len(records)}")

        final_answer = generate_final_answer(
            question=question,
            tool_name=result["tool_name"],
            arguments=result["arguments"],
            records=records,
        )

        print("\nAgent response:")
        print(final_answer)

    else:
        print("\nAgent response:")
        print(result["message"])



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


if __name__ == "__main__":
    main()