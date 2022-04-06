# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import datetime
from urllib.parse import parse_qs

import frappe
from frappe import _
from frappe.utils import get_request_session


def make_request(method, url, auth=None, headers=None, data=None):
	auth = auth or ""
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
	return make_request("GET", url, **kwargs)

def make_post_request(url, **kwargs):
	return make_request("POST", url, **kwargs)

def make_put_request(url, **kwargs):
	return make_request("PUT", url, **kwargs)

def json_handler(obj):
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return str(obj)
