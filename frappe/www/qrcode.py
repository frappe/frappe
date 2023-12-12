# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from urllib.parse import parse_qsl

import frappe
from frappe import _
from frappe.twofactor import get_qr_svg_code


def get_context(context):
	context.no_cache = 1
	context.qr_code_user, context.qrcode_svg = get_user_svg_from_cache()


def get_query_key():
	"""Return query string arg."""
	query_string = frappe.local.request.query_string
	query = dict(parse_qsl(query_string))
	query = {key.decode(): val.decode() for key, val in query.items()}
	if "k" not in list(query):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)
	query = (query["k"]).strip()
	if False in [i.isalpha() or i.isdigit() for i in query]:
		frappe.throw(_("Not Permitted"), frappe.PermissionError)
	return query


def get_user_svg_from_cache():
	"""Get User and SVG code from cache."""
	key = get_query_key()
	totp_uri = frappe.cache.get_value(f"{key}_uri")
	user = frappe.cache.get_value(f"{key}_user")
	if not totp_uri or not user:
		frappe.throw(_("Page has expired!"), frappe.PermissionError)
	if not frappe.db.exists("User", user):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)
	user = frappe.get_doc("User", user)
	svg = get_qr_svg_code(totp_uri)
	return (user, svg.decode())
