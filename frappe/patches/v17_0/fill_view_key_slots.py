import frappe
from frappe.desk.doctype.doctype_view.app_views import app_views
from frappe.desk.doctype.doctype_view.doctype_view import SITE_ROW
from frappe.desk.doctype.doctype_view.doctype_view import on_doctype_update as add_key_index
from frappe.desk.doctype.doctype_view.key_space import KeySpace


def execute():
	"""Fill each saved view's key slot; when two views share a key, the older keeps it and the newer gets the next free one."""
	holders = {
		(view.reference_doctype, view.key_slot): view.user
		for view in frappe.get_all(
			"Doctype View",
			filters={"key_slot": ("is", "set")},
			fields=["reference_doctype", "key_slot", "user"],
		)
	}
	unfilled = frappe.get_all(
		"Doctype View",
		filters={"key": ("!=", ""), "key_slot": ("is", "not set")},
		fields=["name", "reference_doctype", "user", "key"],
		order_by="creation asc",
	)
	for view in unfilled:
		if view.user == SITE_ROW and view.key in app_views(view.reference_doctype):
			continue  # a site override of an app view, which the address index holds

		key = view.key
		if (view.reference_doctype, key) in holders:
			key = KeySpace(view.reference_doctype).claim(key)
			move_references(view, key, holders[(view.reference_doctype, view.key)])
		frappe.db.set_value("Doctype View", view.name, {"key": key, "key_slot": key}, update_modified=False)
		holders[(view.reference_doctype, key)] = view.user
	add_key_index()


def move_references(view, key: str, holder: str):
	"""Point the stars and defaults that opened the moved view at its new key: its owner's, or for a site view everyone's but the holder's."""
	if view.user:
		users = view.user
	elif holder:
		users = ("!=", holder)
	else:
		return  # two site views at one key: no star says which it meant

	frappe.db.set_value(
		"Favourite",
		{
			"reference_doctype": "DocType",
			"reference_name": view.reference_doctype,
			"view": view.key,
			"user": users,
		},
		"view",
		key,
		update_modified=False,
	)
	frappe.db.set_value(
		"Default View",
		{"reference_doctype": view.reference_doctype, "view": view.key, "user": users},
		"view",
		key,
		update_modified=False,
	)
