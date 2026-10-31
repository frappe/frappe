import frappe
from frappe.database.utils import drop_index_if_exists
from frappe.desk.doctype.doctype_view.doctype_view import SITE_ROW
from frappe.desk.doctype.doctype_view.doctype_view import on_doctype_update as add_view_address
from frappe.desk.doctype.doctype_view.key_space import KeySpace

# The view's old address held its label, and a star's old key had no view.
OLD_VIEW_ADDRESS = ("reference_doctype", "type", "user", "label")
OLD_STAR_KEY = ("user", "reference_doctype", "reference_name")


def execute():
	"""Key each saved view, then point each star on one at its list and key; a star on a view gone or not the person's goes."""
	key_saved_views()
	move_view_stars()


def key_saved_views():
	drop_unique("Doctype View", OLD_VIEW_ADDRESS, name="unique_view_address")
	unkeyed = frappe.get_all(
		"Doctype View",
		filters={"label": ("!=", ""), "key": ""},
		fields=["name", "reference_doctype", "label"],
		order_by="creation asc",
	)
	for view in unkeyed:
		key = KeySpace(view.reference_doctype).claim(view.label)
		frappe.db.set_value("Doctype View", view.name, "key", key, update_modified=False)
	add_view_address()


def move_view_stars():
	drop_unique("Favourite", OLD_STAR_KEY)
	stars = frappe.get_all(
		"Favourite", filters={"reference_doctype": "Doctype View"}, fields=["name", "user", "reference_name"]
	)
	for star in stars:
		view = frappe.db.get_value(
			"Doctype View", star.reference_name, ["reference_doctype", "key", "user"], as_dict=True
		)
		if not (view and view.key and view.user in (SITE_ROW, star.user)):
			frappe.db.delete("Favourite", star.name)
			continue

		moved = {"reference_doctype": "DocType", "reference_name": view.reference_doctype, "view": view.key}
		if frappe.db.exists("Favourite", {"user": star.user, **moved}):
			frappe.db.delete("Favourite", star.name)
		else:
			frappe.db.set_value("Favourite", star.name, moved, update_modified=False)


def drop_unique(doctype: str, fields: tuple[str, ...], name: str | None = None):
	"""Drop the unique key `add_unique` made on `fields`, under the name each database gave it."""
	table = f"tab{doctype}"
	if frappe.db.db_type == "postgres":
		from frappe.database.postgres.schema import get_qualified_index_name

		legacy = "unique_" + "_".join(fields)
		for constraint in (
			[name] if name else [get_qualified_index_name(table, list(fields), "unique"), legacy]
		):
			frappe.db.sql_ddl(f'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "{constraint}"')
		return

	prefix = f"{table}_" if frappe.db.db_type == "sqlite" else ""
	drop_index_if_exists(table, name or f"{prefix}unique_{'_'.join(fields)}")
