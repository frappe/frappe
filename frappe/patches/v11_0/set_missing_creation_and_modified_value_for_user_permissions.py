import frappe
from frappe.utils import now_datetime

def execute():
	user_permissions = frappe.get_all('User Permission', filters={
		'creation': ''
	})

	user_permissions = (d.name for d in user_permissions)

	if not user_permissions: return

	frappe.db.sql('''UPDATE `tabUser Permission`
		SET `modified`=%(timestamp)s AND `creation`=%(timestamp)s
		WHERE `name` IN ('{}')'''.format("', '".join(user_permissions)),  # nosec
		dict(timestamp = now_datetime())
	)