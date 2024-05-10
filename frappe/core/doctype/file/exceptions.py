import frappe


class MaxFileSizeReachedError(frappe.ValidationError):
	pass


class FolderNotEmpty(frappe.ValidationError):
	pass


class FileTypeNotAllowed(frappe.ValidationError):
	pass


from frappe.exceptions import *
