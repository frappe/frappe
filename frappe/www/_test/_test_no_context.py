import frappe


# no context object is accepted
def get_context():
	context = frappe._dict()
	context.body = "Custom Content"
	return context
