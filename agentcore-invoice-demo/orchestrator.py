"""Strands orchestrator agent — routes user requests to LangChain/LangGraph sub-agents."""

from strands import Agent
from strands.models.bedrock import BedrockModel

from tools.invoice_lookup import invoice_lookup
from tools.invoice_validator import invoice_validator
from observability import get_tracer

tracer = get_tracer("orchestrator")

SYSTEM_PROMPT = """\
You are an invoice processing assistant. You help users with two capabilities:

1. **Invoice Lookup** — Use the `invoice_lookup` tool to retrieve invoice details,
   check status, search by vendor name, or list all invoices.

2. **Invoice Validation** — Use the `invoice_validator` tool to validate a specific
   invoice against business rules (PO number requirement, $25K threshold, line item
   totals, overdue status).

Routing rules:
- Questions about status, details, or searching → use invoice_lookup
- Requests to validate, check compliance, or audit → use invoice_validator
- If the user asks to validate, always pass the invoice ID (e.g. "INV-003")

Always provide clear, concise answers based on the tool results.
"""


def create_orchestrator() -> Agent:
    """Create and return the Strands orchestrator agent with tracing."""
    with tracer.start_as_current_span("orchestrator.create") as span:
        model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-6",
            region_name="us-east-1",
        )
        agent = Agent(
            model=model,
            tools=[invoice_lookup, invoice_validator],
            system_prompt=SYSTEM_PROMPT,
        )
        span.set_attribute("orchestrator.tools", "invoice_lookup,invoice_validator")
        span.set_attribute("orchestrator.model", "us.anthropic.claude-sonnet-4-6")
    return agent
