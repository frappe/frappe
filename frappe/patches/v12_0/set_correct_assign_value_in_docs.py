import frappe


def execute():
	frappe.reload_doc("desk", "doctype", "todo")

	ToDo = frappe.qb.Table("ToDo")
	assignees = frappe.qb.GROUP_CONCAT("owner").distinct().as_("assignees")

	q = (
		frappe.qb.from_(ToDo)
		.select(ToDo.name, ToDo.reference_type, assignees)
		.where(frappe.qb.fn.Coalesce(ToDo.reference_type, "") != "")
		.where(frappe.qb.fn.Coalesce(ToDo.reference_name, "") != "")
		.where(ToDo.status != "Cancelled")
		.groupby(ToDo.reference_type, ToDo.reference_name)
		.get_sql()
	)

	assignments = frappe.db.sql(q, as_dict=True)

	for doc in assignments:
		assignments = doc.assignees.split(',')
		frappe.db.set_value(
			doc.reference_type,
			doc.reference_name,
			'_assign',
			frappe.as_json(assignments),
			update_modified=False
		)
