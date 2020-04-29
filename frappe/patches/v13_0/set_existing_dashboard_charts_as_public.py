import frappe

def execute():
	frappe.reload_doc('desk', 'doctype', 'dashboard_chart')

	if not frappe.db.table_exists('Dashboard Chart'):
		return

	users_with_permission = frappe.get_all(
		"Has Role",
		fields=["parent"],
		filters={"role": ['in', ['System Manager', 'Dashboard Manager']], "parenttype": "User"},
		distinct=True,
		as_list=True
	)

	users = tuple(
		[item if type(item) == str else item.encode('utf8') for sublist in users_with_permission for item in sublist]
	)

	frappe.db.sql("""
		UPDATE
			`tabDashboard Chart`
		SET
			`tabDashboard Chart`.`is_public`=1
		WHERE
			`tabDashboard Chart`.owner in {users}
		""".format(users=users)
	)
