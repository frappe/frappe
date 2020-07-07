import frappe

def execute():
	frappe.reload_doc('desk', 'doctype', 'todo')

	if frappe.db.db_type == 'mariadb':
		fields = 'name, reference_type, reference_name, group_concat(distinct owner) as owner'
	else:
		fields = 'name, reference_type, reference_name, string_agg(distinct owner, ",") as owner'

	closed_todos = frappe.db.sql('''
		SELECT
			{fields}
		FROM
			`tabTodo`
		WHERE
			reference_type != '' and reference_name != '' and
			status = 'Closed'
		GROUP BY
			reference_type, reference_name
	'''.format(fields=fields), as_dict=True)

	for doc in closed_todos:
		assignments = frappe.db.get_value(doc.reference_type, doc.reference_name, '_assign')
		assignments = frappe.parse_json(assignments) or []
		unique_assignments = list(set(doc.owner.split(',') + assignments))
		frappe.db.set_value(doc.reference_type, doc.reference_name, '_assign', frappe.as_json(unique_assignments))
