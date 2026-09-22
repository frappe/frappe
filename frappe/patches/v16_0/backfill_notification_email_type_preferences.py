import frappe
from frappe.desk.doctype.notification_type.notification_type import install_notification_types
from frappe.model.naming import make_autoname
from frappe.utils import now

# Legacy per-type email checkbox on Notification Settings -> Notification Type name.
# These checkboxes are folded into the `email_notification_types` table.
LEGACY_FIELD_MAP = {
	"Mention": "enable_email_mention",
	"Assignment": "enable_email_assignment",
	"Share": "enable_email_share",
	# v15 still ships Energy Points (dropped on develop), so its opt-out must be honoured too.
	"Energy Point": "enable_email_energy_point",
}

CHILD_DOCTYPE = "Notification Type Preference"
PARENTFIELD = "email_notification_types"

BATCH_SIZE = 5000

# `bulk_insert` takes values positionally. Rows are built as dicts and projected through
# this list, so reordering it can never silently shuffle column values.
ROW_FIELDS = [
	"name",
	"creation",
	"modified",
	"modified_by",
	"owner",
	"docstatus",
	"idx",
	"parent",
	"parenttype",
	"parentfield",
	"notification_type",
]


def execute():
	"""Seed each user's `email_notification_types` table (opt-out model).

	A user is emailed for every enabled, non-skip Notification Type, except those they had
	explicitly disabled via the old `enable_email_*` checkboxes.

	The rows are written with `bulk_insert` rather than `doc.save()`: a save per user costs
	~9 writes (parent update, child table churn, Version row) and a large site would blow
	past `MAX_WRITES_PER_TRANSACTION` before the patch finished.
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

	legacy_fields = {
		type_name: field
		for type_name, field in LEGACY_FIELD_MAP.items()
		if type_name in types and frappe.db.has_column("Notification Settings", field)
	}

	timestamp = now()

	for batch in _settings_batches(["name", *legacy_fields.values()]):
		seeded = _seeded_preferences(batch[0].name, batch[-1].name)
		rows = (
			_as_row(user, type_name, idx, timestamp)
			for user, type_name, idx in _preferences_to_add(batch, types, legacy_fields, seeded)
		)

		frappe.db.bulk_insert(
			CHILD_DOCTYPE,
			fields=ROW_FIELDS,
			values=([row[field] for field in ROW_FIELDS] for row in rows),
			ignore_duplicates=True,
		)


def _settings_batches(fields: list[str]):
	"""Page through Notification Settings by name, so no step holds the whole table."""
	last_name = ""

	while True:
		batch = frappe.get_all(
			"Notification Settings",
			filters={"name": (">", last_name)},
			fields=fields,
			order_by="name asc",
			limit_page_length=BATCH_SIZE,
		)
		if not batch:
			return

		yield batch
		last_name = batch[-1].name


def _seeded_preferences(first_name: str, last_name: str) -> dict[str, set[str]]:
	"""Preferences already present for the parents in `[first_name, last_name]`."""
	seeded = {}

	for row in frappe.get_all(
		CHILD_DOCTYPE,
		filters=[
			["parenttype", "=", "Notification Settings"],
			["parentfield", "=", PARENTFIELD],
			["parent", ">=", first_name],
			["parent", "<=", last_name],
		],
		fields=["parent", "notification_type"],
	):
		seeded.setdefault(row.parent, set()).add(row.notification_type)

	return seeded


def _preferences_to_add(
	batch: list, types: list[str], legacy_fields: dict[str, str], existing: dict[str, set[str]]
):
	"""Yield `(user, notification_type, idx)` for every preference not already seeded."""
	for settings in batch:
		seeded = existing.get(settings.name, set())
		idx = len(seeded)

		for type_name in types:
			if type_name in seeded:
				continue

			# respect an explicit opt-out on the legacy checkbox
			legacy_field = legacy_fields.get(type_name)
			if legacy_field and not settings.get(legacy_field):
				continue

			idx += 1
			yield settings.name, type_name, idx


def _as_row(user: str, type_name: str, idx: int, timestamp: str) -> dict:
	"""One `Notification Type Preference` row, keyed by column name."""
	return {
		"name": make_autoname("hash", CHILD_DOCTYPE),
		"creation": timestamp,
		"modified": timestamp,
		"modified_by": "Administrator",
		"owner": "Administrator",
		"docstatus": 0,
		"idx": idx,
		"parent": user,
		"parenttype": "Notification Settings",
		"parentfield": PARENTFIELD,
		"notification_type": type_name,
	}
