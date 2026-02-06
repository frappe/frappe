def get_currency_precision(currency):
    if not currency:
        return None

    precision = frappe.db.get_value("Currency", currency, "precision")
    return precision if precision is not None else 2
