import frappe
from frappe.desk.doctype.notification_type.notification_type import install_notification_types

# Legacy per-type email checkbox on Notification Settings -> Notification Type name.
# These checkboxes are folded into the `email_notification_types` table.
LEGACY_FIELD_MAP = {
	"Mention": "enable_email_mention",
	"Assignment": "enable_email_assignment",
	"Share": "enable_email_share",
}


def execute():
	"""Seed each user's `email_notification_types` table (opt-out model).

	A user is emailed for every enabled, non-skip Notification Type, except those they had
	explicitly disabled via the old `enable_email_*` checkboxes.
	"""
	frappe.reload_doc("desk", "doctype", "notification_type_preference")
	frappe.reload_doctype("Notification Settings")

	# Make sure the built-in types exist before we reference them.
	install_notification_types()

	from frappe.desk.doctype.notification_log.notification_log import get_skip_email_types

	skip = get_skip_email_types()
	types = [
		name
		for name in frappe.get_all("Notification Type", filters={"enabled": 1}, pluck="name")
		if name not in skip
	]
	if not types:
		return

	for settings_name in frappe.get_all("Notification Settings", pluck="name"):
		settings = frappe.get_doc("Notification Settings", settings_name)
		existing = {row.notification_type for row in settings.email_notification_types}
		changed = False

		for type_name in types:
			if type_name in existing:
				continue

			# respect an explicit opt-out on the legacy checkbox
			legacy_field = LEGACY_FIELD_MAP.get(type_name)
			if (
				legacy_field
				and frappe.db.has_column("Notification Settings", legacy_field)
				and not settings.get(legacy_field)
			):
				continue

			settings.append("email_notification_types", {"notification_type": type_name})
			changed = True

		if changed:
			settings.save(ignore_permissions=True)
