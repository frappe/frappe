def test_currency_precision_independent_of_language():
    frappe.set_user("Administrator")
    frappe.local.lang = "en"

    v1 = frappe.utils.formatters.format_currency(123.456, "USD")

    frappe.local.lang = "fr"
    v2 = frappe.utils.formatters.format_currency(123.456, "USD")

    assert v1 == v2



def test_currency_precision_from_currency_doctype():
    frappe.db.set_value("Currency", "USD", "precision", 2)
    result = frappe.utils.formatters.format_currency(1.2345, "USD")
    assert "1.23" in result
