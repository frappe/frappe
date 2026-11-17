import frappe


def execute():
	"""Knowledge's embedding model, chosen before Flow Model said which models embed."""
	if model := frappe.db.get_single_value("Flow Knowledge Settings", "embedding_model"):
		frappe.db.set_value("Flow Model", model, "embedding", 1)
