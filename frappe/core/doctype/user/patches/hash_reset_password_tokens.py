import frappe
from frappe.utils.data import sha256_hash


def execute():
	"""hash reset password tokens"""

	users = frappe.get_all("User", {"reset_password_key": ("is", "set")}, ["name", "reset_password_key"])
	for user in users:
		frappe.db.set_value(
			"User",
			user.name,
			"reset_password_key",
			sha256_hash(user.reset_password_key),
			update_modified=False,
		)
