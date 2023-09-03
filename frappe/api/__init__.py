# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import base64
import binascii
from urllib.parse import urlencode, urlparse

from werkzeug.exceptions import NotFound
from werkzeug.routing import Map
from werkzeug.wrappers import Request

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

	endpoint(**arguments)
	return build_response("json")


def validate_auth():
	"""
	Authenticate and sets user for the request.
	"""
	authorization_header = frappe.get_request_header("Authorization", "").split(" ")

	if len(authorization_header) == 2:
		validate_oauth(authorization_header)
		validate_auth_via_api_keys(authorization_header)

	validate_auth_via_hooks()


def validate_oauth(authorization_header):
	"""
	Authenticate request using OAuth and set session user

	Args:
	        authorization_header (list of str): The 'Authorization' header containing the prefix and token
	"""

	from frappe.integrations.oauth2 import get_oauth_server
	from frappe.oauth import get_url_delimiter

	form_dict = frappe.local.form_dict
	token = authorization_header[1]
	req = frappe.request
	parsed_url = urlparse(req.url)
	access_token = {"access_token": token}
	uri = (
		parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path + "?" + urlencode(access_token)
	)
	http_method = req.method
	headers = req.headers
	body = req.get_data()
	if req.content_type and "multipart/form-data" in req.content_type:
		body = None

	try:
		required_scopes = frappe.db.get_value("OAuth Bearer Token", token, "scopes").split(
			get_url_delimiter()
		)
		valid, oauthlib_request = get_oauth_server().verify_request(
			uri, http_method, body, headers, required_scopes
		)
		if valid:
			frappe.set_user(frappe.db.get_value("OAuth Bearer Token", token, "user"))
			frappe.local.form_dict = form_dict
	except AttributeError:
		pass


def validate_auth_via_api_keys(authorization_header):
	"""
	Authenticate request using API keys and set session user

	Args:
	        authorization_header (list of str): The 'Authorization' header containing the prefix and token
	"""

	try:
		auth_type, auth_token = authorization_header
		authorization_source = frappe.get_request_header("Frappe-Authorization-Source")
		if auth_type.lower() == "basic":
			api_key, api_secret = frappe.safe_decode(base64.b64decode(auth_token)).split(":")
			validate_api_key_secret(api_key, api_secret, authorization_source)
		elif auth_type.lower() == "token":
			api_key, api_secret = auth_token.split(":")
			validate_api_key_secret(api_key, api_secret, authorization_source)
	except binascii.Error:
		frappe.throw(
			_("Failed to decode token, please provide a valid base64-encoded token."),
			frappe.InvalidAuthorizationToken,
		)
	except (AttributeError, TypeError, ValueError):
		pass


def validate_api_key_secret(api_key, api_secret, frappe_authorization_source=None):
	"""frappe_authorization_source to provide api key and secret for a doctype apart from User"""
	doctype = frappe_authorization_source or "User"
	doc = frappe.db.get_value(doctype=doctype, filters={"api_key": api_key}, fieldname=["name"])
	form_dict = frappe.local.form_dict
	doc_secret = frappe.utils.password.get_decrypted_password(doctype, doc, fieldname="api_secret")
	if api_secret == doc_secret:
		if doctype == "User":
			user = frappe.db.get_value(doctype="User", filters={"api_key": api_key}, fieldname=["name"])
		else:
			user = frappe.db.get_value(doctype, doc, "user")
		if frappe.local.login_manager.user in ("", "Guest"):
			frappe.set_user(user)
		frappe.local.form_dict = form_dict


def validate_auth_via_hooks():
	for auth_hook in frappe.get_hooks("auth_hooks", []):
		frappe.get_attr(auth_hook)()


# Merge all API version routing rules
from frappe.api.v1 import url_rules as v1_rules

url_rules = [
	*v1_rules,
]

API_URL_MAP = Map(url_rules)
