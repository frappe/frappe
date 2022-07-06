# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import datetime
import json
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


def create_request_log(
	data,
	integration_type=None,
	service_name=None,
	name=None,
	error=None,
	request_headers=None,
	output=None,
	**kwargs,
):
	"""
	DEPRECATED: The parameter integration_type will be removed in the next major release.
	Use is_remote_request instead.
	"""
	if integration_type == "Remote":
		kwargs["is_remote_request"] = 1

	elif integration_type == "Subscription Notification":
		kwargs["request_description"] = integration_type

	reference_doctype = reference_docname = None
	if "reference_doctype" not in kwargs:
		if isinstance(data, str):
			data = json.loads(data)

		reference_doctype = data.get("reference_doctype")
		reference_docname = data.get("reference_docname")

	integration_request = frappe.get_doc(
		{
			"doctype": "Integration Request",
			"integration_request_service": service_name,
			"request_headers": get_json(request_headers),
			"data": get_json(data),
			"output": get_json(output),
			"error": get_json(error),
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			**kwargs,
		}
	)

	if name:
		integration_request.flags._name = name

	integration_request.insert(ignore_permissions=True)
	frappe.db.commit()

	return integration_request


def get_json(obj):
	return obj if isinstance(obj, str) else frappe.as_json(obj, indent=1)


def get_payment_gateway_controller(payment_gateway):
	"""Return payment gateway controller"""
	gateway = frappe.get_doc("Payment Gateway", payment_gateway)
	if gateway.gateway_controller is None:
		try:
			return frappe.get_doc(f"{payment_gateway} Settings")
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
		if kwargs.get("payment_gateway"):
			doc = frappe.get_doc("{} Settings".format(kwargs.get("payment_gateway")))
			return doc.get_payment_url(**kwargs)
		else:
			raise Exception
	except Exception:
		frappe.respond_as_web_page(
			_("Something went wrong"),
			_(
				"Looks like something is wrong with this site's payment gateway configuration. No payment has been made."
			),
			indicator_color="red",
			http_status_code=frappe.ValidationError.http_status_code,
		)


def create_payment_gateway(gateway, settings=None, controller=None):
	# NOTE: we don't translate Payment Gateway name because it is an internal doctype
	if not frappe.db.exists("Payment Gateway", gateway):
		payment_gateway = frappe.get_doc(
			{
				"doctype": "Payment Gateway",
				"gateway": gateway,
				"gateway_settings": settings,
				"gateway_controller": controller,
			}
		)
		payment_gateway.insert(ignore_permissions=True)


def json_handler(obj):
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return str(obj)
