from __future__ import unicode_literals

import hashlib
import json
from urllib.parse import quote, urlencode, urlparse

import jwt
from oauthlib.oauth2 import FatalClientError, OAuth2Error

import frappe
from frappe import _
from frappe.oauth import OAuthWebRequestValidator, WebApplicationServer
from frappe.integrations.doctype.oauth_provider_settings.oauth_provider_settings import get_oauth_settings

def get_oauth_server():
	if not getattr(frappe.local, 'oauth_server', None):
		oauth_validator = OAuthWebRequestValidator()
		frappe.local.oauth_server = WebApplicationServer(oauth_validator)

	return frappe.local.oauth_server

def sanitize_kwargs(param_kwargs):
	"""Remove 'data' and 'cmd' keys, if present."""
	arguments = param_kwargs
	arguments.pop('data', None)
	arguments.pop('cmd', None)

	return arguments

@frappe.whitelist()
def approve(*args, **kwargs):
	r = frappe.request

	try:
		scopes, frappe.flags.oauth_credentials = get_oauth_server().validate_authorization_request(
			r.url,
			r.method,
			r.get_data(),
			r.headers
		)

		headers, body, status = get_oauth_server().create_authorization_response(
			uri=frappe.flags.oauth_credentials['redirect_uri'],
			body=r.get_data(),
			headers=r.headers,
			scopes=scopes,
			credentials=frappe.flags.oauth_credentials
		)
		uri = headers.get('Location', None)

		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = uri

	except FatalClientError as e:
		return e
	except OAuth2Error as e:
		return e

@frappe.whitelist(allow_guest=True)
def authorize(**kwargs):
	success_url = "/api/method/frappe.integrations.oauth2.approve?" + encode_params(sanitize_kwargs(kwargs))
	failure_url = frappe.form_dict["redirect_uri"] + "?error=access_denied"

	if frappe.session.user == 'Guest':
		#Force login, redirect to preauth again.
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/login?" + encode_params({'redirect-to': frappe.request.url})
	else:
		try:
			r = frappe.request
			scopes, frappe.flags.oauth_credentials = get_oauth_server().validate_authorization_request(
				r.url,
				r.method,
				r.get_data(),
				r.headers
			)

			skip_auth = frappe.db.get_value("OAuth Client", frappe.flags.oauth_credentials['client_id'], "skip_authorization")
			unrevoked_tokens = frappe.get_all("OAuth Bearer Token", filters={"status":"Active"})

			if skip_auth or (get_oauth_settings().skip_authorization == "Auto" and unrevoked_tokens):
				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = success_url
			else:
				#Show Allow/Deny screen.
				response_html_params = frappe._dict({
					"client_id": frappe.db.get_value("OAuth Client", kwargs['client_id'], "app_name"),
					"success_url": success_url,
					"failure_url": failure_url,
					"details": scopes
				})
				resp_html = frappe.render_template("templates/includes/oauth_confirmation.html", response_html_params)
				frappe.respond_as_web_page("Confirm Access", resp_html)
		except FatalClientError as e:
			return e
		except OAuth2Error as e:
			return e

@frappe.whitelist(allow_guest=True)
def get_token(*args, **kwargs):
	#Check whether frappe server URL is set
	frappe_server_url = frappe.db.get_value("Social Login Key", "frappe", "base_url") or None
	if not frappe_server_url:
		frappe.throw(_("Please set Base URL in Social Login Key for Frappe"))

	try:
		r = frappe.request
		headers, body, status = get_oauth_server().create_token_response(
			r.url,
			r.method,
			r.form,
			r.headers,
			frappe.flags.oauth_credentials
		)
		out = frappe._dict(json.loads(body))
		if not out.error and "openid" in out.scope:
			token_user = frappe.db.get_value("OAuth Bearer Token", out.access_token, "user")
			token_client = frappe.db.get_value("OAuth Bearer Token", out.access_token, "client")
			client_secret = frappe.db.get_value("OAuth Client", token_client, "client_secret")
			if token_user in ["Guest", "Administrator"]:
				frappe.throw(_("Logged in as Guest or Administrator"))

			id_token_header = {
				"typ":"jwt",
				"alg":"HS256"
			}
			id_token = {
				"aud": token_client,
				"exp": int((frappe.db.get_value("OAuth Bearer Token", out.access_token, "expiration_time") - frappe.utils.datetime.datetime(1970, 1, 1)).total_seconds()),
				"sub": frappe.db.get_value("User Social Login", {"parent":token_user, "provider": "frappe"}, "userid"),
				"iss": frappe_server_url,
				"at_hash": frappe.oauth.calculate_at_hash(out.access_token, hashlib.sha256)
			}

			id_token_encoded = jwt.encode(id_token, client_secret, algorithm='HS256', headers=id_token_header)
			out.update({"id_token": str(id_token_encoded)})

		frappe.local.response = out

	except FatalClientError as e:
		return e


@frappe.whitelist(allow_guest=True)
def revoke_token(*args, **kwargs):
	r = frappe.request
	headers, body, status = get_oauth_server().create_revocation_response(
		r.url,
		headers=r.headers,
		body=r.form,
		http_method=r.method
	)

	frappe.local.response['http_status_code'] = status
	if status == 200:
		return "success"
	else:
		return "bad request"

@frappe.whitelist()
def openid_profile(*args, **kwargs):
	picture = None
	first_name, last_name, avatar, name = frappe.db.get_value("User", frappe.session.user, ["first_name", "last_name", "user_image", "name"])
	frappe_userid = frappe.db.get_value("User Social Login", {"parent":frappe.session.user, "provider": "frappe"}, "userid")
	request_url = urlparse(frappe.request.url)

	if avatar:
		if validate_url(avatar):
			picture = avatar
		else:
			picture = request_url.scheme + "://" + request_url.netloc + avatar

	user_profile = frappe._dict({
			"sub": frappe_userid,
			"name": " ".join(filter(None, [first_name, last_name])),
			"given_name": first_name,
			"family_name": last_name,
			"email": name,
			"picture": picture
		})

	frappe.local.response = user_profile

def validate_url(url_string):
	try:
		result = urlparse(url_string)
		return result.scheme and result.scheme in ["http", "https", "ftp", "ftps"]
	except:
		return False

def encode_params(params):
	"""
	Encode a dict of params into a query string.

	Use `quote_via=urllib.parse.quote` so that whitespaces will be encoded as
	`%20` instead of as `+`. This is needed because oauthlib cannot handle `+`
	as a whitespace.
	"""
	return urlencode(params, quote_via=quote)
