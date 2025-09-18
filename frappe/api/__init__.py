# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from contextlib import suppress
from enum import Enum

from werkzeug.exceptions import NotFound
from werkzeug.routing import Map, Submount
from werkzeug.wrappers import Request, Response

import frappe
from frappe import _
from frappe.pulse.app_heartbeat_event import capture_app_heartbeat
from frappe.utils.response import build_response


class ApiVersion(str, Enum):
	V1 = "v1"
	V2 = "v2"


def handle(request: Request):
	"""
	Entry point for `/api` methods.

	APIs are versioned using second part of path.
	v1 -> `/api/v1/*`
	v2 -> `/api/v2/*`

	Different versions have different specification but broadly following things are supported:

	- `/api/method/{methodname}` will call a whitelisted method
	- `/api/resource/{doctype}` will query a table
	        examples:
	        - `?fields=["name", "owner"]`
	        - `?filters=[["Task", "name", "like", "%005"]]`
	        - `?limit_start=0`
	        - `?limit_page_length=20`
	- `/api/resource/{doctype}/{name}` will point to a resource
	        `GET` will return document
	        `POST` will insert
	        `PUT` will update
	        `DELETE` will delete
	"""

	try:
		endpoint, arguments = API_URL_MAP.bind_to_environ(request.environ).match()
	except NotFound:  # Wrap 404 - backward compatiblity
		raise frappe.DoesNotExistError

	data = endpoint(**arguments)
	if isinstance(data, Response):
		return data

	if data is not None:
		frappe.response["data"] = data
	data = build_response("json")

	with suppress(Exception):
		capture_app_heartbeat(arguments)

	return data


# Merge all API version routing rules
from frappe.api.v1 import url_rules as v1_rules
from frappe.api.v2 import url_rules as v2_rules

API_URL_MAP = Map(
	[
		# V1 routes
		Submount("/api", v1_rules),
		Submount(f"/api/{ApiVersion.V1.value}", v1_rules),
		Submount(f"/api/{ApiVersion.V2.value}", v2_rules),
	],
	strict_slashes=False,  # Allows skipping trailing slashes
	merge_slashes=False,
)


def get_api_version() -> ApiVersion | None:
	if not frappe.request:
		return

	if frappe.request.path.startswith(f"/api/{ApiVersion.V2.value}"):
		return ApiVersion.V2
	return ApiVersion.V1
