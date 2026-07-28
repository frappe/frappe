import frappe

OLD_SYMBOL = "ر.س"
NEW_SYMBOL = "⃁"


def execute():
	Currency = frappe.qb.DocType("Currency")

	frappe.qb.update(Currency).set(Currency.symbol, NEW_SYMBOL).where(
		(Currency.name == "SAR") & (Currency.symbol == OLD_SYMBOL)
	).run()
