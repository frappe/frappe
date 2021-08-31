# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See LICENSE

def change_case(string: str) -> str:
	new_string = string[0]
	for character in string[1:]:
		if character.isupper():
			new_string += f" {character}"
		else:
			new_string += character
	return new_string

class DocTypesNamespace:
	def __getattr__(self, key):
		from frappe.model.base_document import get_controller
		try:
			dt = change_case(key)
			return get_controller(dt)
		except ImportError:
			return get_controller(key)

def get_doctypes_lazy():
	return DocTypesNamespace()
