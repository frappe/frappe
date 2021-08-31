# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE


def get_possible_doctype_names(string: str) -> str:
	"""Convert strings that look like `SalesInvoice` to `Sales Invoice`
	"""
	yield string

	spaced_string = string[0]
	for character in string[1:]:
		spaced_string += (
			f" {character}" if character.isupper() else character
		)

	yield spaced_string

	# uppercased_acronyms = {x: x.isupper() for x in string}
	diff_string = ""
	for i, x in enumerate(string):
		if i > 0 and string[i-1].isupper() and x.isupper() and string[i+1].islower():
			diff_string += f" {x}"
		else:
			diff_string += x
	yield diff_string

class DocTypesNamespace:
	def __getattr__(self, key):
		from frappe.model.base_document import get_controller
		error = None
		for doctype_name in get_possible_doctype_names(key):
			try:
				return get_controller(doctype_name)
			except ImportError as e:
				error = e
				continue
		raise error

	def get(self, doctype: str):
		from frappe.model.base_document import get_controller
		return get_controller(doctype)
