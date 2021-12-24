import frappe


class AccessTokenUrlNotSetError(frappe.ValidationError):
	pass


class AuthorizeUrlNotSetError(frappe.ValidationError):
	pass


class BaseUrlNotSetError(frappe.ValidationError):
	pass


class ClientIDNotSetError(frappe.ValidationError):
	pass


class ClientSecretNotSetError(frappe.ValidationError):
	pass


class RedirectUrlNotSetError(frappe.ValidationError):
	pass
