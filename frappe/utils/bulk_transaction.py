# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _


@frappe.whitelist()
def process_bulk_transaction(data, from_doctype, to_doctype):
	if isinstance(data, str):
		deserialized_data = json.loads(data)
	else:
		deserialized_data = data

	mapper = frappe.db.get_value("Bulk Transaction DocType Mapping", {
		"source": from_doctype,
		"target": to_doctype
	}, [
		"server_script",
		"from_doctype_field",
		"to_doctype_field",
		"docname_field",
		"batch_size"
	], as_dict=1)

	if not mapper:
		frappe.throw(_("Setup mapping for {0} to {1} in Bulk Transaction Settings.").format(from_doctype, to_doctype))

	method_args = {'from_doctype_field': from_doctype, 'to_doctype_field': to_doctype}
	method_args_to_pass = {}
	for key, value in method_args.items():
		if mapper.get(key):
			method_args_to_pass[mapper.key] = value
	
	doc_count = len(deserialized_data)
	if doc_count > mapper.batch_size:
		for idx in range(0, doc_count, mapper.batch_size):
			frappe.enqueue(
				_process_bulk_transaction,
				deserialized_data=deserialized_data[idx:(idx+mapper.batch_size)],
				mapper=mapper,
				method_args_to_pass=method_args_to_pass,
			)
		return
	return _process_bulk_transaction(deserialized_data, mapper, method_args_to_pass)


def _process_bulk_transaction(deserialized_data, mapper, method_args_to_pass):
	doc_list = []
	for data in deserialized_data:
		try:
			frappe.db.savepoint("before_creation_state")
			method_args_to_pass[mapper.docname_field] = data.get("name")
			frappe.form_dict.bulk_transaction = method_args_to_pass
			# doc = frappe.call(mapper.method, **method_args_to_pass)
			frappe.get_doc("Server Script", mapper.server_script).execute_method()
			doc = frappe.response['message']
			if doc.__islocal:
				doc.insert()
			doc_list.append(doc.name)
		except Exception as e:
			frappe.db.rollback(save_point="before_creation_state")
			frappe.msgprint(str(frappe.get_traceback()))
	return doc_list