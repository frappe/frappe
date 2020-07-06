import frappe

def execute():
	frappe.reload_doc('desk', 'doctype', 'todo')

	closed_todos = frappe.get_all(
		'ToDo',
		fields = ['name', 'reference_type', 'reference_name', 'owner'],
		filters = {
			'status': 'Closed'
		}
	)

	for doc in closed_todos:
		if doc.reference_type and doc.reference_name:
			assignments = frappe.db.get_value(doc.reference_type, doc.reference_name, '_assign')
			assignments = frappe.parse_json(assignments) or []
			if isinstance(assignments, list) and doc.owner not in assignments:
				assignments.append(doc.owner)
				frappe.db.set_value(doc.reference_type, doc.reference_name, '_assign', frappe.as_json(assignments))
