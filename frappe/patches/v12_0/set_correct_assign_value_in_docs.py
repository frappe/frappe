import frappe

def execute():
	frappe.reload_doc('desk', 'doctype', 'todo')

	query = '''
		SELECT
			name, reference_type, reference_name, {} as assignees
		FROM
			`tabToDo`
		WHERE
			COALESCE(reference_type, '') != '' AND
			COALESCE(reference_name, '') != '' AND
			status != 'Cancelled'
		GROUP BY
			reference_type, reference_name
	'''

	assignments = frappe.db.multisql({
		'mariadb': query.format('GROUP_CONCAT(DISTINCT `owner`)'),
		'postgres': query.format('STRING_AGG(DISTINCT "owner", ",")')
	}, as_dict=True)

	for doc in assignments:
		assignments = doc.assignees.split(',')
		frappe.db.set_value(
			doc.reference_type,
			doc.reference_name,
			'_assign',
			frappe.as_json(assignments),
			update_modified=False
		)
