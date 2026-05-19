"""Mock invoice data for the AgentCore demo."""

INVOICES = {
    "INV-001": {
        "invoice_id": "INV-001",
        "vendor": "Acme Corp",
        "amount": 12500.00,
        "status": "Paid",
        "due_date": "2026-04-15",
        "po_number": "PO-2026-0451",
        "line_items": [
            {"description": "Cloud consulting services", "quantity": 50, "unit_price": 200.00, "total": 10000.00},
            {"description": "Infrastructure setup", "quantity": 1, "unit_price": 2500.00, "total": 2500.00},
        ],
        "notes": "Paid on time",
    },
    "INV-002": {
        "invoice_id": "INV-002",
        "vendor": "GlobalTech",
        "amount": 8750.50,
        "status": "Pending",
        "due_date": "2026-05-20",
        "po_number": "PO-2026-0523",
        "line_items": [
            {"description": "Software licenses (annual)", "quantity": 25, "unit_price": 350.02, "total": 8750.50},
        ],
        "notes": "Awaiting approval",
    },
    "INV-003": {
        "invoice_id": "INV-003",
        "vendor": "FastShip LLC",
        "amount": 45000.00,
        "status": "Overdue",
        "due_date": "2026-04-01",
        "po_number": None,  # Intentionally missing for validation demo
        "line_items": [
            {"description": "Bulk freight shipping Q1", "quantity": 1, "unit_price": 30000.00, "total": 30000.00},
            {"description": "Express delivery surcharge", "quantity": 1, "unit_price": 15000.00, "total": 15000.00},
        ],
        "notes": "Amount exceeds $25K threshold, missing PO number",
    },
}


def get_invoice(invoice_id: str) -> dict | None:
    """Retrieve a single invoice by ID."""
    return INVOICES.get(invoice_id.upper())


def search_invoices(query: str) -> list[dict]:
    """Search invoices by vendor name, status, or ID."""
    query_lower = query.lower()
    results = []
    for inv in INVOICES.values():
        if (query_lower in inv["invoice_id"].lower()
                or query_lower in inv["vendor"].lower()
                or query_lower in inv["status"].lower()):
            results.append(inv)
    return results


def get_all_invoices() -> list[dict]:
    """Return all invoices."""
    return list(INVOICES.values())
