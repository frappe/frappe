import frappe


# no context object is accepted
def get_context():
	context = frappe.attrdict()
	context.body = "Custom Content"
	return context
