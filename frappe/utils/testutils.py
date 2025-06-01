# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import nts


def add_custom_field(doctype, fieldname, fieldtype="Data", options=None):
	nts.get_doc(
		{
			"doctype": "Custom Field",
			"dt": doctype,
			"fieldname": fieldname,
			"fieldtype": fieldtype,
			"options": options,
		}
	).insert()


def clear_custom_fields(doctype):
	nts.db.delete("Custom Field", {"dt": doctype})
	nts.clear_cache(doctype=doctype)
