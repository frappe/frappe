import frappe
from frappe.utils import now_datetime

def execute():
	user_permissions = frappe.get_all('User Permission', filters={
		'creation': ''
	})

	user_permissions = (d.name for d in user_permissions)

	if not user_permissions: return

	frappe.db.sql('UPDATE `tabUser Permission` SET `modified`=%s AND `creation`=%s WHERE `name` IN ({})' # nosec
			.format(','.join(['%s'] * len(user_permissions))),
			now_datetime()
		)