# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from urlparse import parse_qs
from frappe.twofactor import get_qr_svg_code

def get_context(context):
	context.no_cache = 1
	context.qr_code_user,context.qrcode_svg = get_user_svg_from_cache()

def get_query_key():
	'''Return query string arg.'''
	query_string = frappe.local.request.query_string
	query = parse_qs(query_string)
	if not 'k' in query.keys():
		frappe.throw(_('Not Permitted'),frappe.PermissionError)
	query = (query['k'][0]).strip()
	if False in [i.isalpha() or i.isdigit() for i in query]:
		frappe.throw(_('Not Permitted'),frappe.PermissionError)
	return query

def get_user_svg_from_cache():
	'''Get User and SVG code from cache.'''
	key = get_query_key()
	totp_uri = frappe.cache().get_value("{}_uri".format(key))
	user = frappe.cache().get_value("{}_user".format(key))
	if not totp_uri or not user:
		frappe.throw(_('Page has expired!'),frappe.PermissionError)
	if not frappe.db.exists('User',user):
		frappe.throw(_('Not Permitted'), frappe.PermissionError)
	user = frappe.get_doc('User',user)
	svg = get_qr_svg_code(totp_uri)
	return (user,svg)
