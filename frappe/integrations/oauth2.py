import json
from urllib.parse import quote, urlencode
from oauthlib.oauth2 import FatalClientError, OAuth2Error
from oauthlib.openid.connect.core.endpoints.pre_configured import (
	Server as WebApplicationServer,
)

import frappe
from frappe.oauth import (
	OAuthWebRequestValidator,
	generate_json_error_response,
	get_server_url,
	get_userinfo,
)
from frappe.integrations.doctype.oauth_provider_settings.oauth_provider_settings import (
	get_oauth_settings,
)


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
		) = get_oauth_server().validate_authorization_request(
			r.url, r.method, r.get_data(), r.headers
		)

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
	success_url = "/api/method/frappe.integrations.oauth2.approve?" + encode_params(
		sanitize_kwargs(kwargs)
	)
	failure_url = frappe.form_dict["redirect_uri"] + "?error=access_denied"

	if frappe.session.user == "Guest":
		# Force login, redirect to preauth again.
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/login?" + encode_params(
			{"redirect-to": frappe.request.url}
		)
	else:
		try:
			r = frappe.request
			(
				scopes,
				frappe.flags.oauth_credentials,
			) = get_oauth_server().validate_authorization_request(
				r.url, r.method, r.get_data(), r.headers
			)

			skip_auth = frappe.db.get_value(
				"OAuth Client",
				frappe.flags.oauth_credentials["client_id"],
				"skip_authorization",
			)
			unrevoked_tokens = frappe.get_all(
				"OAuth Bearer Token", filters={"status": "Active"}
			)

			if skip_auth or (
				get_oauth_settings().skip_authorization == "Auto" and unrevoked_tokens
			):
				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = success_url
			else:
				# Show Allow/Deny screen.
				response_html_params = frappe._dict(
					{
						"client_id": frappe.db.get_value(
							"OAuth Client", kwargs["client_id"], "app_name"
						),
						"success_url": success_url,
						"failure_url": failure_url,
						"details": scopes,
					}
				)
				resp_html = frappe.render_template(
					"templates/includes/oauth_confirmation.html", response_html_params
				)
				frappe.respond_as_web_page("Confirm Access", resp_html)
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


@frappe.whitelist(allow_guest=True)
def openid_configuration():
	frappe_server_url = get_server_url()
	frappe.local.response = frappe._dict(
		{
			"issuer": frappe_server_url,
			"authorization_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.authorize",
			"token_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.get_token",
			"userinfo_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.openid_profile",
			"revocation_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.revoke_token",
			"introspection_endpoint": f"{frappe_server_url}/api/method/frappe.integrations.oauth2.introspect_token",
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


@frappe.whitelist(allow_guest=True)
def introspect_token(token=None, token_type_hint=None):
	if token_type_hint not in ["access_token", "refresh_token"]:
		token_type_hint = "access_token"
	try:
		bearer_token = None
		if token_type_hint == "access_token":
			bearer_token = frappe.get_doc("OAuth Bearer Token", {"access_token": token})
		elif token_type_hint == "refresh_token":
			bearer_token = frappe.get_doc(
				"OAuth Bearer Token", {"refresh_token": token}
			)

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
