from click import secho

import frappe

GRAVATAR_PATTERN = "%gravatar.com%"

DOCTYPES = (
	("User", "user_image"),
	("Contact", "image"),
)


def execute():
	"""Clear image fields that point to Gravatar."""
	for doctype, fieldname in DOCTYPES:
		filters = {fieldname: ("like", GRAVATAR_PATTERN)}
		count = frappe.db.count(doctype, filters=filters)

		if not count:
			continue

		secho(f"{doctype}: found {count} record(s) with Gravatar URL in `{fieldname}`", fg="yellow")
		frappe.db.set_value(doctype, filters, fieldname, "", update_modified=False)
		secho(f"  cleared {count} record(s)", fg="green")
