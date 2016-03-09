# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.utils import cstr

def execute():
	# deprecated on 2016-03-09
	# using insert_after instead
	return

	frappe.db.sql("""delete from `tabProperty Setter` where property='previous_field'""")

	all_custom_fields = frappe._dict()
	for d in frappe.db.sql("""select name, dt, fieldname, insert_after from `tabCustom Field`
		where insert_after is not null and insert_after != ''""", as_dict=1):
			all_custom_fields.setdefault(d.dt, frappe._dict()).setdefault(d.fieldname, d.insert_after)

	for dt, custom_fields in all_custom_fields.items():
		_idx = []
		existing_ps = frappe.db.get_value("Property Setter",
			{"doc_type": dt, "property": "_idx"}, ["name", "value", "creation"], as_dict=1)

		# if no existsing property setter, build based on meta
		if not existing_ps:
			_idx = get_sorted_fields(dt, custom_fields)
		else:
			_idx = json.loads(existing_ps.value)

			idx_needs_to_be_fixed = False
			for fieldname, insert_after in custom_fields.items():
				# Delete existing property setter if field is not there
				if fieldname not in _idx:
					idx_needs_to_be_fixed = True
					break
				else:
					previous_field = _idx[_idx.index(fieldname) - 1]

					if previous_field != insert_after and cstr(existing_ps.creation) >= "2015-12-28":
						idx_needs_to_be_fixed = True
						break

			if idx_needs_to_be_fixed:
				frappe.delete_doc("Property Setter", existing_ps.name)
				_idx = get_sorted_fields(dt, custom_fields)

		if _idx:
			frappe.make_property_setter({
				"doctype":dt,
				"doctype_or_field": "DocType",
				"property": "_idx",
				"value": json.dumps(_idx),
				"property_type": "Text"
			}, validate_fields_for_doctype=False)


def get_sorted_fields(doctype, custom_fields):
	"""sort on basis of insert_after"""
	fields_dict = frappe.get_meta(doctype).get("fields")

	standard_fields_count = frappe.db.sql("""select count(name) from `tabDocField`
		where parent=%s""", doctype)[0][0]

	newlist = []
	pending = [d.fieldname for d in fields_dict]

	maxloops = len(custom_fields) + 20
	while (pending and maxloops>0):
		maxloops -= 1
		for fieldname in pending[:]:
			if fieldname in custom_fields and len(newlist) >= standard_fields_count:
				# field already added
				for n in newlist:
					if n==custom_fields.get(fieldname):
						newlist.insert(newlist.index(n)+1, fieldname)
						pending.remove(fieldname)
						break
			else:
				newlist.append(fieldname)
				pending.remove(fieldname)

	# recurring at end
	if pending:
		newlist += pending

	return newlist
