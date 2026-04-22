import frappe


def execute():
	Language = frappe.qb.DocType("Language")

	frappe.qb.update(Language).set(Language.language_name, "မြန်မာ").where(
		Language.language_code == "my"
	).run()
