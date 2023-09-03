# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from werkzeug.exceptions import NotFound
from werkzeug.routing import Map, Submount
from werkzeug.wrappers import Request, Response

import frappe
import frappe.client
import frappe.handler
from frappe import _
from frappe.utils.response import build_response


def handle(request: Request):
	"""
	Handler for `/api` methods

	### Examples:

	`/api/method/{methodname}` will call a whitelisted method

	`/api/resource/{doctype}` will query a table
	        examples:
	        - `?fields=["name", "owner"]`
	        - `?filters=[["Task", "name", "like", "%005"]]`
	        - `?limit_start=0`
	        - `?limit_page_length=20`

	`/api/resource/{doctype}/{name}` will point to a resource
	        `GET` will return doclist
	        `POST` will insert
	        `PUT` will update
	        `DELETE` will delete

	`/api/resource/{doctype}/{name}?run_method={method}` will run a whitelisted controller method
	"""

	try:
		endpoint, arguments = API_URL_MAP.bind_to_environ(request.environ).match()
	except NotFound:  # Wrap 404 - backward compatiblity
		raise frappe.DoesNotExistError

	resp = endpoint(**arguments)
	if isinstance(resp, Response):
		return resp

	return build_response("json")


# Merge all API version routing rules
from frappe.api.v1 import url_rules as v1_rules
from frappe.api.v2 import url_rules as v2_rules

API_URL_MAP = Map(
	[
		# V1 routes
		Submount("/api", v1_rules),
		Submount("/api/v1", v1_rules),
		Submount("/api/v2", v2_rules),
	],
	strict_slashes=False,  # Allows skipping trailing slashes
)
