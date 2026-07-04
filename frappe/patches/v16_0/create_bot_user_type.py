from frappe.utils.install import create_user_type


def execute():
	# Seed the standard "Bot" user type on existing sites.
	create_user_type()
