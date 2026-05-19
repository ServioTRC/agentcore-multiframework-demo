"""LangGraph sub-agent for invoice validation, exposed as a Strands @tool."""

import json
from typing import TypedDict, Annotated
from operator import add

from langgraph.graph import StateGraph, END
from opentelemetry import trace
from strands import tool

from data.mock_invoices import get_invoice
from observability import get_tracer

tracer = get_tracer("tools.invoice_validator")


# --- State definition ---

class ValidationState(TypedDict):
    invoice_id: str
    invoice_data: dict
    extracted_fields: dict
    validation_results: Annotated[list[str], add]
    final_report: str


# --- Graph nodes ---

def extract_fields(state: ValidationState) -> dict:
    """Node 1: Extract key fields from the invoice."""
    data = state["invoice_data"]
    extracted = {
        "invoice_id": data.get("invoice_id"),
        "vendor": data.get("vendor"),
        "amount": data.get("amount"),
        "status": data.get("status"),
        "due_date": data.get("due_date"),
        "po_number": data.get("po_number"),
        "line_items_count": len(data.get("line_items", [])),
        "line_items_total": sum(item.get("total", 0) for item in data.get("line_items", [])),
    }
    return {"extracted_fields": extracted}


def validate_rules(state: ValidationState) -> dict:
    """Node 2: Validate against business rules."""
    fields = state["extracted_fields"]
    errors = []

    if not fields.get("po_number"):
        errors.append("MISSING_PO: Purchase Order number is required")

    if fields.get("amount", 0) > 25000:
        errors.append(f"HIGH_VALUE: Amount ${fields['amount']:,.2f} exceeds $25,000 threshold")

    if fields.get("line_items_total") and fields.get("amount"):
        if abs(fields["line_items_total"] - fields["amount"]) > 0.01:
            errors.append(
                f"AMOUNT_MISMATCH: Line items total ${fields['line_items_total']:,.2f} "
                f"!= invoice amount ${fields['amount']:,.2f}"
            )

    if fields.get("status", "").lower() == "overdue":
        errors.append(f"OVERDUE: Invoice is past due date ({fields.get('due_date')})")

    return {"validation_results": errors}


def generate_report(state: ValidationState) -> dict:
    """Node 3: Generate final validation report."""
    fields = state["extracted_fields"]
    errors = state["validation_results"]
    report = {
        "invoice_id": fields.get("invoice_id"),
        "vendor": fields.get("vendor"),
        "amount": fields.get("amount"),
        "is_valid": len(errors) == 0,
        "issues_found": len(errors),
        "issues": errors,
        "recommendation": "Approved for payment" if not errors else "Requires review",
    }
    return {"final_report": json.dumps(report, indent=2)}


# --- Build the graph ---

def _build_validation_graph():
    graph = StateGraph(ValidationState)
    graph.add_node("extract_fields", extract_fields)
    graph.add_node("validate_rules", validate_rules)
    graph.add_node("generate_report", generate_report)
    graph.set_entry_point("extract_fields")
    graph.add_edge("extract_fields", "validate_rules")
    graph.add_edge("validate_rules", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()


# --- Strands @tool wrapper ---

@tool
def invoice_validator(invoice_id: str) -> str:
    """Validate an invoice against business rules.
    Checks amount thresholds, required fields (PO number), line item totals, and payment status.

    Args:
        invoice_id: The invoice ID to validate (e.g. 'INV-003').

    Returns:
        Validation report with issues found and recommendation.
    """
    with tracer.start_as_current_span("tool.invoice_validator") as span:
        span.set_attribute("tool.name", "invoice_validator")
        span.set_attribute("tool.invoice_id", invoice_id)
        try:
            invoice_data = get_invoice(invoice_id)
            if not invoice_data:
                span.set_attribute("tool.error", "not_found")
                return json.dumps({"error": f"Invoice '{invoice_id}' not found"})

            workflow = _build_validation_graph()
            result = workflow.invoke({
                "invoice_id": invoice_id,
                "invoice_data": invoice_data,
                "extracted_fields": {},
                "validation_results": [],
                "final_report": "",
            })
            output = result["final_report"]
            span.set_attribute("tool.issues_found", json.loads(output).get("issues_found", 0))
            span.set_status(trace.StatusCode.OK)
            return output
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise
