# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.model import no_value_fields, table_fields
from frappe.model.document import Document
from frappe.utils import cstr

FIELDTYPES_TO_IGNORE = frozenset(fieldtype for fieldtype in no_value_fields if fieldtype not in table_fields)


class Version(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		data: DF.Code | None
		docname: DF.Data
		ref_doctype: DF.Link
	# end: auto-generated types

	def update_version_info(self, old: Document | None, new: Document) -> bool:
		"""Update changed info and return true if change contains useful data."""
		if not old:
			# Check if doc has some information about creation source like data import
			return self.for_insert(new)
		else:
			return self.set_diff(old, new)

	@staticmethod
	def set_impersonator(data):
		if not frappe.session:
			return
		if impersonator := frappe.session.data.get("impersonated_by"):
			data["impersonated_by"] = impersonator

		if audit_user := frappe.session.data.get("audit_user"):
			data["audit_user"] = audit_user

	def set_diff(self, old: Document, new: Document) -> bool:
		"""Set the data property with the diff of the docs if present"""
		diff = get_diff(old, new)
		if diff:
			self.set_impersonator(diff)
			self.ref_doctype = new.doctype
			self.docname = new.name
			self.data = frappe.as_json(diff, indent=None, separators=(",", ":"))
			return True
		else:
			return False

	def for_insert(self, doc: Document) -> bool:
		updater_reference = doc.flags.updater_reference
		if not updater_reference:
			return False

		data = {
			"creation": doc.creation,
			"updater_reference": updater_reference,
			"created_by": doc.owner,
		}
		self.set_impersonator(data)
		self.ref_doctype = doc.doctype
		self.docname = doc.name
		self.data = frappe.as_json(data, indent=None, separators=(",", ":"))
		return True

	def get_data(self):
		return json.loads(self.data)


def get_diff(old, new, for_child=False, compare_cancelled=False):
	"""Get diff between 2 document objects

	If there is a change, then returns a dict like:

	        {
	                "changed"    : [[fieldname1, old, new], [fieldname2, old, new]],
	                "added"      : [[table_fieldname1, {dict}], ],
	                "removed"    : [[table_fieldname1, {dict}], ],
	                "row_changed": [[table_fieldname1, row_name1, row_index,
	                        [[child_fieldname1, old, new],
	                        [child_fieldname2, old, new]], ]
	                ],

	        }"""
	if not new:
		return None

	blacklisted_fields = ["Markdown Editor", "Text Editor", "Code", "HTML Editor"]

	# capture data import if set
	data_import = new.flags.via_data_import
	updater_reference = new.flags.updater_reference

	out = frappe._dict(
		changed=[],
		added=[],
		removed=[],
		row_changed=[],
		data_import=data_import,
		updater_reference=updater_reference,
	)

	if not for_child:
		amended_from = new.get("amended_from")
		old_row_name_field = "_amended_from" if (amended_from and amended_from == old.name) else "name"

	for df in new.meta.fields:
		if df.fieldtype in FIELDTYPES_TO_IGNORE or getattr(df, "is_virtual", False):
			continue

		old_value, new_value = old.get(df.fieldname), new.get(df.fieldname)
		if df.fieldtype in ("Link", "Dynamic Link"):
			old_value, new_value = cstr(old_value), cstr(new_value)

		if not for_child and df.fieldtype in table_fields:
			old_rows_by_name = {}
			for d in old_value:
				old_rows_by_name[d.name] = d

			found_rows = set()

			# check rows for additions, changes
			for i, d in enumerate(new_value):
				old_row_name = getattr(d, old_row_name_field, None)
				if compare_cancelled:
					if amended_from:
						if len(old_value) > i:
							old_row_name = old_value[i].name

				if old_row_name and old_row_name in old_rows_by_name:
					found_rows.add(old_row_name)

					diff = get_diff(old_rows_by_name[old_row_name], d, for_child=True)
					if diff and diff.changed:
						out.row_changed.append((df.fieldname, i, d.name, diff.changed))
				else:
					out.added.append([df.fieldname, d.as_dict()])

			# check for deletions
			for d in old_value:
				if d.name not in found_rows:
					out.removed.append([df.fieldname, d.as_dict()])

		elif old_value != new_value:
			if df.fieldtype not in blacklisted_fields:
				old_value = old.get_formatted(df.fieldname) if old_value else old_value
				new_value = new.get_formatted(df.fieldname) if new_value else new_value

			if old_value != new_value:
				doctype = new.doctype or old.doctype
				if doctype:
					meta = frappe.get_meta(doctype)

					if (field_meta := meta.get_field(df.fieldname)) and field_meta.fieldtype == "Link":
						link_meta = frappe.get_meta(field_meta.options)

						# Show title field value if field is Link and show_title_field_in_link is True
						if link_meta.show_title_field_in_link and (
							(title_field := link_meta.get_title_field()) != "name"
						):
							old_title_val, new_title_val = "", ""
							result = frappe.db.get_values(
								field_meta.options,
								{"name": ("in", (old_value, new_value))},
								["name", title_field],
							)
							for r in result:
								if r[0] == old_value:
									old_title_val = r[1]
								elif r[0] == new_value:
									new_title_val = r[1]
							out.changed.append((df.fieldname, old_title_val, new_title_val))
							continue
				out.changed.append((df.fieldname, old_value, new_value))

	# name & docstatus
	if not for_child:
		for key in ("name", "docstatus"):
			old_value = getattr(old, key)
			new_value = getattr(new, key)

			if old_value != new_value:
				out.changed.append([key, old_value, new_value])

	if any((out.changed, out.added, out.removed, out.row_changed)):
		return out

	else:
		return None


def on_doctype_update():
	frappe.db.add_index("Version", ["ref_doctype", "docname"])
