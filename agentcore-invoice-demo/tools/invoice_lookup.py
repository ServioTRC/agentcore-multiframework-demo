"""LangChain sub-agent for invoice lookup, exposed as a Strands @tool."""

import json

from langchain_aws import ChatBedrock
from langchain.agents import create_agent
from langchain_core.tools import tool as langchain_tool
from opentelemetry import trace
from strands import tool

from data.mock_invoices import get_invoice, search_invoices, get_all_invoices
from observability import get_tracer

tracer = get_tracer("tools.invoice_lookup")


# --- LangChain internal tools ---

@langchain_tool
def lookup_invoice_by_id(invoice_id: str) -> str:
    """Look up a specific invoice by its ID (e.g. INV-001)."""
    result = get_invoice(invoice_id)
    if result:
        return json.dumps(result, indent=2)
    return json.dumps({"error": f"Invoice '{invoice_id}' not found"})


@langchain_tool
def search_invoices_tool(query: str) -> str:
    """Search invoices by vendor name, status, or partial ID."""
    results = search_invoices(query)
    if results:
        return json.dumps(results, indent=2)
    return json.dumps({"error": f"No invoices matching '{query}'"})


@langchain_tool
def list_all_invoices() -> str:
    """List all available invoices with their basic details."""
    invoices = get_all_invoices()
    summary = [{"invoice_id": i["invoice_id"], "vendor": i["vendor"],
                "amount": i["amount"], "status": i["status"]} for i in invoices]
    return json.dumps(summary, indent=2)


# --- Build the LangChain agent ---

_LC_TOOLS = [lookup_invoice_by_id, search_invoices_tool, list_all_invoices]


def _build_langchain_agent():
    llm = ChatBedrock(
        model_id="us.anthropic.claude-sonnet-4-6",
        region_name="us-east-1",
    )
    return create_agent(
        llm,
        tools=_LC_TOOLS,
        system_prompt="You are an invoice lookup assistant. Use the available tools to find invoice details. Return clear, concise answers.",
    )


# --- Strands @tool wrapper ---

@tool
def invoice_lookup(query: str) -> str:
    """Look up invoice details by ID or search criteria.
    Use for status checks, finding invoices by vendor, or listing all invoices.

    Args:
        query: Invoice ID (e.g. 'INV-001'), vendor name, status, or general search query.

    Returns:
        Invoice details or search results as formatted text.
    """
    with tracer.start_as_current_span("tool.invoice_lookup") as span:
        span.set_attribute("tool.name", "invoice_lookup")
        span.set_attribute("tool.input", query[:200])
        try:
            agent = _build_langchain_agent()
            result = agent.invoke({"messages": [{"role": "user", "content": query}]})
            messages = result.get("messages", [])
            output = messages[-1].content if messages else "No results found."
            span.set_attribute("tool.output_length", len(output))
            span.set_status(trace.StatusCode.OK)
            return output
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise
