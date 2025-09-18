import datetime
import json
from typing import Literal, cast
from urllib.parse import quote, urlencode, urlparse

from oauthlib.oauth2 import FatalClientError, OAuth2Error
from oauthlib.openid.connect.core.endpoints.pre_configured import Server as WebApplicationServer
from pydantic import ValidationError
from werkzeug import Response
from werkzeug.exceptions import NotFound

import frappe
import frappe.utils
from frappe import oauth
from frappe.integrations.utils import (
	OAuth2DynamicClientMetadata,
	create_new_oauth_client,
	get_oauth_settings,
	validate_dynamic_client_metadata,
)
from frappe.oauth import (
	OAuthWebRequestValidator,
	generate_json_error_response,
	get_server_url,
	get_userinfo,
)

ENDPOINTS = {
	"token_endpoint": "/api/method/frappe.integrations.oauth2.get_token",
	"userinfo_endpoint": "/api/method/frappe.integrations.oauth2.openid_profile",
	"revocation_endpoint": "/api/method/frappe.integrations.oauth2.revoke_token",
	"authorization_endpoint": "/api/method/frappe.integrations.oauth2.authorize",
	"introspection_endpoint": "/api/method/frappe.integrations.oauth2.introspect_token",
}


def get_oauth_server():
	if not getattr(frappe.local, "oauth_server", None):
		oauth_validator = OAuthWebRequestValidator()
		frappe.local.oauth_server = WebApplicationServer(oauth_validator)

	return frappe.local.oauth_server


def sanitize_kwargs(param_kwargs):
	"""Remove 'data' and 'cmd' keys, if present."""
	arguments = param_kwargs
	arguments.pop("data", None)
	arguments.pop("cmd", None)

	return arguments


def encode_params(params):
	"""
	Encode a dict of params into a query string.

	Use `quote_via=urllib.parse.quote` so that whitespaces will be encoded as
	`%20` instead of as `+`. This is needed because oauthlib cannot handle `+`
	as a whitespace.
	"""
	return urlencode(params, quote_via=quote)


@frappe.whitelist()
def approve(*args, **kwargs):
	r = frappe.request

	try:
		(
			scopes,
			frappe.flags.oauth_credentials,
		) = get_oauth_server().validate_authorization_request(r.url, r.method, r.get_data(), r.headers)

		headers, body, status = get_oauth_server().create_authorization_response(
			uri=frappe.flags.oauth_credentials["redirect_uri"],
			body=r.get_data(),
			headers=r.headers,
			scopes=scopes,
			credentials=frappe.flags.oauth_credentials,
		)
		uri = headers.get("Location", None)

		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = uri
		return

	except (FatalClientError, OAuth2Error) as e:
		return generate_json_error_response(e)


@frappe.whitelist(allow_guest=True)
def authorize(**kwargs):
	success_url = "/api/method/frappe.integrations.oauth2.approve?" + encode_params(sanitize_kwargs(kwargs))
	failure_url = frappe.form_dict.get("redirect_uri", "") + "?error=access_denied"

	if frappe.session.user == "Guest":
		# Force login, redirect to preauth again.
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/login?" + encode_params({"redirect-to": frappe.request.url})
	else:
		try:
			r = frappe.request
			(
				scopes,
				frappe.flags.oauth_credentials,
			) = get_oauth_server().validate_authorization_request(r.url, r.method, r.get_data(), r.headers)

			skip_auth = frappe.db.get_value(
				"OAuth Client",
				frappe.flags.oauth_credentials["client_id"],
				"skip_authorization",
			)
			unrevoked_tokens = frappe.db.exists(
				"OAuth Bearer Token", {"status": "Active", "user": frappe.session.user}
			)

			if skip_auth or (get_oauth_settings().skip_authorization == "Auto" and unrevoked_tokens):
				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = success_url
			else:
				if "openid" in scopes:
					scopes.remove("openid")
					scopes.extend(["Full Name", "Email", "User Image", "Roles"])

				# Show Allow/Deny screen.
				response_html_params = frappe._dict(
					{
						"client_id": frappe.db.get_value("OAuth Client", kwargs["client_id"], "app_name"),
						"success_url": success_url,
						"failure_url": failure_url,
						"details": scopes,
					}
				)
				resp_html = frappe.render_template(
					"templates/includes/oauth_confirmation.html", response_html_params
				)
				frappe.respond_as_web_page(frappe._("Confirm Access"), resp_html, primary_action=None)
		except (FatalClientError, OAuth2Error) as e:
			return generate_json_error_response(e)


@frappe.whitelist(allow_guest=True)
def get_token(*args, **kwargs):
	try:
		r = frappe.request
		headers, body, status = get_oauth_server().create_token_response(
			r.url, r.method, r.form, r.headers, frappe.flags.oauth_credentials
		)
		body = frappe._dict(json.loads(body))

		if body.error:
			frappe.local.response = body
			frappe.local.response["http_status_code"] = 400
			return

		frappe.local.response = body
		return

	except (FatalClientError, OAuth2Error) as e:
		return generate_json_error_response(e)


@frappe.whitelist(allow_guest=True)
def revoke_token(*args, **kwargs):
	try:
		r = frappe.request
		headers, body, status = get_oauth_server().create_revocation_response(
			r.url,
			headers=r.headers,
			body=r.form,
			http_method=r.method,
		)
	except (FatalClientError, OAuth2Error):
		pass

	# status_code must be 200
	frappe.local.response = frappe._dict({})
	frappe.local.response["http_status_code"] = status or 200
	return


@frappe.whitelist()
def openid_profile(*args, **kwargs):
	try:
		r = frappe.request
		headers, body, status = get_oauth_server().create_userinfo_response(
			r.url,
			headers=r.headers,
			body=r.form,
		)
		body = frappe._dict(json.loads(body))
		frappe.local.response = body
		return

	except (FatalClientError, OAuth2Error) as e:
		return generate_json_error_response(e)


def get_openid_configuration():
	response = Response()
	response.mimetype = "application/json"
	frappe_server_url = get_server_url()
	response.data = frappe.as_json(
		{
			"issuer": frappe_server_url,
			"authorization_endpoint": f"{frappe_server_url}{ENDPOINTS['authorization_endpoint']}",
			"token_endpoint": f"{frappe_server_url}{ENDPOINTS['token_endpoint']}",
			"userinfo_endpoint": f"{frappe_server_url}{ENDPOINTS['userinfo_endpoint']}",
			"revocation_endpoint": f"{frappe_server_url}{ENDPOINTS['revocation_endpoint']}",
			"introspection_endpoint": f"{frappe_server_url}{ENDPOINTS['introspection_endpoint']}",
			"response_types_supported": [
				"code",
				"token",
				"code id_token",
				"code token id_token",
				"id_token",
				"id_token token",
			],
			"subject_types_supported": ["public"],
			"id_token_signing_alg_values_supported": ["HS256"],
		}
	)
	return response


@frappe.whitelist(allow_guest=True)
def introspect_token(token=None, token_type_hint=None):
	if token_type_hint not in ["access_token", "refresh_token"]:
		token_type_hint = "access_token"
	try:
		bearer_token = None
		if token_type_hint == "access_token":
			bearer_token = frappe.get_doc("OAuth Bearer Token", {"access_token": token})
		elif token_type_hint == "refresh_token":
			bearer_token = frappe.get_doc("OAuth Bearer Token", {"refresh_token": token})

		client = frappe.get_doc("OAuth Client", bearer_token.client)

		token_response = frappe._dict(
			{
				"client_id": client.client_id,
				"trusted_client": client.skip_authorization,
				"active": bearer_token.status == "Active",
				"exp": round(bearer_token.expiration_time.timestamp()),
				"scope": bearer_token.scopes,
			}
		)

		if "openid" in bearer_token.scopes:
			sub = frappe.get_value(
				"User Social Login",
				{"provider": "frappe", "parent": bearer_token.user},
				"userid",
			)

			if sub:
				token_response.update({"sub": sub})
				user = frappe.get_doc("User", bearer_token.user)
				userinfo = get_userinfo(user)
				token_response.update(userinfo)

		frappe.local.response = token_response

	except Exception:
		frappe.local.response = frappe._dict({"active": False})


def handle_wellknown(path: str):
	"""Path handler for GET requests to /.well-known/ endpoints. Invoked in app.py"""

	if path.startswith("/.well-known/openid-configuration"):
		return get_openid_configuration()

	if path.startswith("/.well-known/oauth-authorization-server") and is_oauth_metadata_enabled(
		"auth_server"
	):
		return get_authorization_server_metadata()

	if path.startswith("/.well-known/oauth-protected-resource") and is_oauth_metadata_enabled("resource"):
		return get_protected_resource_metadata()

	raise NotFound


def get_authorization_server_metadata():
	"""
	Creates response for the /.well-known/oauth-authorization-server endpoint.

	Reference: https://datatracker.ietf.org/doc/html/rfc8414
	"""

	response = Response()
	response.mimetype = "application/json"
	response.data = frappe.as_json(_get_authorization_server_metadata())
	frappe.local.allow_cors = "*"
	return response


def _get_authorization_server_metadata():
	"""
	Responds with the authorization server metadata.

	Reference: https://datatracker.ietf.org/doc/html/rfc8414#section-2

	Note:
		Value for response_types_supported does not include token because, PKCE
		token flow is not supported. Responding with token in the redirect URL
		is an unsafe practice, so code is the only supported response type.
	"""

	issuer = get_resource_url()
	metadata = dict(
		issuer=issuer,
		authorization_endpoint=f"{issuer}{ENDPOINTS['authorization_endpoint']}",
		token_endpoint=f"{issuer}{ENDPOINTS['token_endpoint']}",
		response_types_supported=["code"],
		response_modes_supported=["query"],
		grant_types_supported=["authorization_code", "refresh_token"],
		token_endpoint_auth_methods_supported=["none", "client_secret_basic"],
		service_documentation="https://docs.frappe.io/framework/user/en/guides/integration/how_to_set_up_oauth#add-a-client-app",
		revocation_endpoint=f"{issuer}{ENDPOINTS['revocation_endpoint']}",
		revocation_endpoint_auth_methods_supported=["client_secret_basic"],
		introspection_endpoint=f"{issuer}{ENDPOINTS['introspection_endpoint']}",
		userinfo_endpoint=f"{issuer}{ENDPOINTS['userinfo_endpoint']}",
		code_challenge_methods_supported=["S256"],
	)

	if frappe.get_cached_value("OAuth Settings", "OAuth Settings", "enable_dynamic_client_registration"):
		metadata["registration_endpoint"] = f"{issuer}/api/method/frappe.integrations.oauth2.register_client"

	return metadata


@frappe.whitelist(allow_guest=True, methods=["POST"])
def register_client():
	"""
	Registers an OAuth client.

	Reference: https://datatracker.ietf.org/doc/html/rfc7591
	"""

	if not frappe.get_cached_value("OAuth Settings", "OAuth Settings", "enable_dynamic_client_registration"):
		raise NotFound

	response = Response()
	response.mimetype = "application/json"
	data = frappe.request.json

	if data is None:
		response.status_code = 400
		response.data = frappe.as_json(
			{
				"error": "invalid_client_metadata",
				"error_description": "Request body is empty",
			}
		)
		return response

	try:
		client = OAuth2DynamicClientMetadata.model_validate(data)
	except ValidationError as e:
		response.status_code = 400
		response.data = frappe.as_json({"error": "invalid_client_metadata", "error_description": str(e)})
		return response

	"""
	Note:

	A check for existing client cannot be done unless a software_statement (JWT)
	is issued. Use of software_statement is not yet implemented.

	Doing an exists check based on just client_name or other replicable
	parameters risks leaking client_id and client_secret. So it's better to
	issue a new client.
	"""

	if error := validate_dynamic_client_metadata(client):
		response.status_code = 400
		response.data = frappe.as_json({"error": "invalid_client_metadata", "error_description": error})
		return response

	doc = create_new_oauth_client(client)
	response_data = {
		"client_id": doc.client_id,
		"client_secret": doc.client_secret,
		"client_id_issued_at": doc.client_id_issued_at(),
		"client_secret_expires_at": 0,
		# Response should include registered metadata
		"client_name": doc.app_name,
		"client_uri": doc.client_uri,
		"grant_types": ["authorization_code"],
		"response_types": ["code"],
		"logo_uri": doc.logo_uri,
		"tos_uri": doc.tos_uri,
		"policy_uri": doc.policy_uri,
		"software_id": doc.software_id,
		"software_version": doc.software_version,
		"scope": doc.scopes,
		"redirect_uris": doc.redirect_uris.split("\n") if doc.redirect_uris else None,
		"contacts": doc.contacts.split("\n") if doc.contacts else None,
	}

	if doc.is_public_client():
		del response_data["client_secret"]

	_del_none_values(response_data)
	response.status_code = 201  # Created
	response.data = frappe.as_json(response_data)
	return response


def get_protected_resource_metadata():
	"""
	Creates response for the /.well-known/oauth-protected-resource endpoint.

	Reference: https://datatracker.ietf.org/doc/html/rfc9728
	"""

	response = Response()
	response.mimetype = "application/json"
	response.data = frappe.as_json(_get_protected_resource_metadata())
	return response


def _get_protected_resource_metadata():
	from frappe.integrations.doctype.oauth_settings.oauth_settings import OAuthSettings

	oauth_settings = cast(OAuthSettings, frappe.get_cached_doc("OAuth Settings", ignore_permissions=True))
	resource = get_resource_url()
	authorization_servers = [resource]

	if oauth_settings.show_social_login_key_as_authorization_server:
		authorization_servers.extend(
			frappe.get_list(
				"Social Login Key",
				filters={
					"enable_social_login": True,
					"show_in_resource_metadata": True,
				},
				pluck="base_url",
				ignore_permissions=True,
			)
		)

	metadata = dict(
		resource=resource,
		authorization_servers=authorization_servers,
		bearer_methods_supported=["header"],
		resource_name=oauth_settings.resource_name,
		resource_documentation=oauth_settings.resource_documentation,
		resource_policy_uri=oauth_settings.resource_policy_uri,
		resource_tos_uri=oauth_settings.resource_tos_uri,
	)

	if oauth_settings.scopes_supported is not None:
		scopes = []
		for _s in oauth_settings.scopes_supported.split("\n"):
			s = _s.strip()
			if s is None:
				continue
			scopes.append(s)

		if scopes:
			metadata["scopes_supported"] = scopes
	_del_none_values(metadata)
	return metadata


def is_oauth_metadata_enabled(label: Literal["resource", "auth_server"]):
	if label not in ["resource", "auth_server"]:
		return False

	fieldname = "show_auth_server_metadata"
	if label == "resource":
		fieldname = "show_protected_resource_metadata"

	return bool(
		frappe.get_cached_value(
			"OAuth Settings",
			"OAuth Settings",
			fieldname,
		)
	)


def get_resource_url():
	"""Uses request URL to reflect the resource URL"""
	request_url = urlparse(frappe.request.url)
	return f"{request_url.scheme}://{request_url.netloc}"


def _del_none_values(d: dict):
	for k in list(d.keys()):
		if k in d and d[k] is None:
			del d[k]


def set_cors_for_privileged_requests():
	"""
	Called in before_request hook, prevents failure of privileged requests,
	for OPTIONS and:
	1. GET requests on /.well-known/
	2. POST requests on /api/method/frappe.integrations.oauth2.register_client

	Point 2. also depends on OAuth Settings for dynamic client registration.
	Without these, registration requests from public clients will fail due to
	preflight requests failing.
	"""
	if (
		frappe.conf.allow_cors == "*"
		or not frappe.local.request
		or not frappe.local.request.headers.get("Origin")
	):
		return

	if frappe.request.path.startswith("/.well-known/") and frappe.request.method in ("GET", "OPTIONS"):
		frappe.local.allow_cors = "*"
		return

	if (
		frappe.request.path.startswith("/api/method/frappe.integrations.oauth2.register_client")
		and frappe.request.method in ("POST", "OPTIONS")
		and frappe.get_cached_value(
			"OAuth Settings",
			"OAuth Settings",
			"enable_dynamic_client_registration",
		)
	):
		_set_allowed_cors()
		return

	if (
		frappe.request.path.startswith(ENDPOINTS["token_endpoint"])
		or frappe.request.path.startswith(ENDPOINTS["revocation_endpoint"])
		or frappe.request.path.startswith(ENDPOINTS["introspection_endpoint"])
		or frappe.request.path.startswith(ENDPOINTS["userinfo_endpoint"])
	) and frappe.request.method in ("POST", "OPTIONS"):
		_set_allowed_cors()
		return


def _set_allowed_cors():
	allowed = frappe.get_cached_value(
		"OAuth Settings",
		"OAuth Settings",
		"allowed_public_client_origins",
	)
	if not allowed:
		return

	allowed = allowed.strip().splitlines()
	if "*" in allowed:
		frappe.local.allow_cors = "*"
	else:
		frappe.local.allow_cors = allowed
