# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from enum import StrEnum
from typing import Optional

from werkzeug.exceptions import NotFound
from werkzeug.routing import Map, Submount
from werkzeug.wrappers import Request, Response

import frappe
import frappe.client
from frappe import _
from frappe.utils.response import build_response


# ---------------------------------------------------------------------------
# API Versioning
# ---------------------------------------------------------------------------

class ApiVersion(StrEnum):
	V1 = "v1"
	V2 = "v2"


# ---------------------------------------------------------------------------
# Main API Handler
# ---------------------------------------------------------------------------

def handle(request: Request) -> Response:
	"""
	Entry point for `/api` methods.

	APIs are versioned using the second segment of the path.
	- v1 -> `/api/v1/*`
	- v2 -> `/api/v2/*`

	Supported endpoints:
	- `/api/method/{methodname}` calls a whitelisted method.
	- `/api/resource/{doctype}` queries a DocType (table).
	  Examples:
	    ?fields=["name", "owner"]
	    ?filters=[["Task", "name", "like", "%005"]]
	    ?limit_start=0
	    ?limit_page_length=20
	- `/api/resource/{doctype}/{name}` points to a resource:
	    - `GET`    -> Fetch document
	    - `POST`   -> Insert document
	    - `PUT`    -> Update document
	    - `DELETE` -> Delete document
	"""

	# Optional logging of API requests
	if frappe.get_system_settings("log_api_requests"):
		frappe.get_doc(
			{
				"doctype": "API Request Log",
				"path": request.path,
				"user": frappe.session.user,
				"method": request.method,
			}
		).deferred_insert()

	# Resolve endpoint
	try:
		endpoint, arguments = API_URL_MAP.bind_to_environ(request.environ).match()
	except NotFound:
		# Wrap 404 for backward compatibility
		raise frappe.DoesNotExistError

	# Execute the matched endpoint
	data = endpoint(**arguments)

	if isinstance(data, Response):
		return data

	if data is not None:
		frappe.response["data"] = data

	return build_response("json")


# ---------------------------------------------------------------------------
# API URL Map
# ---------------------------------------------------------------------------

from frappe.api.v1 import url_rules as v1_rules
from frappe.api.v2 import url_rules as v2_rules

API_URL_MAP = Map(
	[
		# v1 routes
		Submount("/api", v1_rules),
		Submount(f"/api/{ApiVersion.V1.value}", v1_rules),

		# v2 routes
		Submount(f"/api/{ApiVersion.V2.value}", v2_rules),
	],
	strict_slashes=False,  # Allow skipping trailing slashes
	merge_slashes=False,
)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def get_api_version() -> Optional[ApiVersion]:
	"""Determine API version based on request path."""
	if not frappe.request:
		return None

	if frappe.request.path.startswith(f"/api/{ApiVersion.V2.value}"):
		return ApiVersion.V2

	return ApiVersion.V1
