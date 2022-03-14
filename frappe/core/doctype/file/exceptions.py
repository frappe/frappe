import frappe

class MaxFileSizeReachedError(frappe.ValidationError):
	pass

class FolderNotEmpty(frappe.ValidationError):
	pass
