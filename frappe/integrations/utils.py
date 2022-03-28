# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
import json,datetime
from urllib.parse import parse_qs
from frappe.utils import get_request_session
from frappe import _

def make_request(method, url, auth=None, headers=None, data=None):
	auth = auth or ''
	data = data or {}
	headers = headers or {}

	try:
		s = get_request_session()
		frappe.flags.integration_request = s.request(method, url, data=data, auth=auth, headers=headers)
		frappe.flags.integration_request.raise_for_status()

		if frappe.flags.integration_request.headers.get("content-type") == "text/plain; charset=utf-8":
			return parse_qs(frappe.flags.integration_request.text)

		return frappe.flags.integration_request.json()
	except Exception as exc:
		frappe.log_error()
		raise exc

def make_get_request(url, **kwargs):
	return make_request('GET', url, **kwargs)

def make_post_request(url, **kwargs):
	return make_request('POST', url, **kwargs)

def make_put_request(url, **kwargs):
	return make_request('PUT', url, **kwargs)

def create_request_log(data, integration_type, service_name, name=None, error=None, request_header=None, is_remote_request=False, **kwargs):
	"""
		DEPRECATED: The parameter integration_type will be removed in the next major release.
		Use is_remote_request instead.
	"""
	if isinstance(data, str) or not kwargs.get('reference_doctype'):
		data = json.loads(data)

	if isinstance(error, str):
		error = json.loads(error)
	
	if isinstance(request_header, str):
		request_header = json.loads('request_header')

	integration_request = frappe.get_doc({
		"doctype": "Integration Request",
		"integration_type": integration_type,
		"is_remote_request": is_remote_request,
		"integration_request_service": service_name,
		"reference_doctype": kwargs.get('reference_doctype') if kwargs.get('reference_doctype') else data.get('reference_doctype'),
		"reference_docname":  kwargs.get('reference_name') if kwargs.get('reference_doctype') else data.get('reference_name'),
		"request_id": kwargs.get('request_id'),
		"url": kwargs.get('url'),
		"request_description": kwargs.get('request_description'),
		"error": frappe.as_json(error, indent=2),
		"data": frappe.as_json(data, indent=2),
		"headers": frappe.as_json(request_header, indent=2)
	})

	if name:
		integration_request.flags._name = name

	integration_request.insert(ignore_permissions=True)
	frappe.db.commit()

	return integration_request

def get_payment_gateway_controller(payment_gateway):
	'''Return payment gateway controller'''
	gateway = frappe.get_doc("Payment Gateway", payment_gateway)
	if gateway.gateway_controller is None:
		try:
			return frappe.get_doc("{0} Settings".format(payment_gateway))
		except Exception:
			frappe.throw(_("{0} Settings not found").format(payment_gateway))
	else:
		try:
			return frappe.get_doc(gateway.gateway_settings, gateway.gateway_controller)
		except Exception:
			frappe.throw(_("{0} Settings not found").format(payment_gateway))


@frappe.whitelist(allow_guest=True, xss_safe=True)
def get_checkout_url(**kwargs):
	try:
		if kwargs.get('payment_gateway'):
			doc = frappe.get_doc("{0} Settings".format(kwargs.get('payment_gateway')))
			return doc.get_payment_url(**kwargs)
		else:
			raise Exception
	except Exception:
		frappe.respond_as_web_page(_("Something went wrong"),
			_("Looks like something is wrong with this site's payment gateway configuration. No payment has been made."),
			indicator_color='red',
			http_status_code=frappe.ValidationError.http_status_code)

def create_payment_gateway(gateway, settings=None, controller=None):
	# NOTE: we don't translate Payment Gateway name because it is an internal doctype
	if not frappe.db.exists("Payment Gateway", gateway):
		payment_gateway = frappe.get_doc({
			"doctype": "Payment Gateway",
			"gateway": gateway,
			"gateway_settings": settings,
			"gateway_controller": controller
		})
		payment_gateway.insert(ignore_permissions=True)

def json_handler(obj):
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return str(obj)
