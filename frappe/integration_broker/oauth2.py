from __future__ import unicode_literals
import frappe, json
from frappe.oauth import OAuthWebRequestValidator, WebApplicationServer
from oauthlib.oauth2 import FatalClientError, OAuth2Error
from urllib import quote, urlencode
from urlparse import urlparse
from frappe.integrations.doctype.oauth_provider_settings.oauth_provider_settings import get_oauth_settings

def get_oauth_server():
	if not getattr(frappe.local, 'oauth_server', None):
		oauth_validator = OAuthWebRequestValidator()
		frappe.local.oauth_server  = WebApplicationServer(oauth_validator)

	return frappe.local.oauth_server

def get_urlparams_from_kwargs(param_kwargs):
	arguments = param_kwargs
	if arguments.get("data"):
		arguments.pop("data")
	if arguments.get("cmd"):
		arguments.pop("cmd")

	return urlencode(arguments)

@frappe.whitelist()
def approve(*args, **kwargs):
	r = frappe.request
	uri = r.url
	http_method = r.method
	body = r.get_data()
	headers = r.headers

	try:
		scopes, frappe.flags.oauth_credentials = get_oauth_server().validate_authorization_request(uri, http_method, body, headers)

		headers, body, status = get_oauth_server().create_authorization_response(uri=frappe.flags.oauth_credentials['redirect_uri'], \
				body=body, headers=headers, scopes=scopes, credentials=frappe.flags.oauth_credentials)
		uri = headers.get('Location', None)

		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = uri

	except FatalClientError as e:
		return e
	except OAuth2Error as e:
		return e

@frappe.whitelist(allow_guest=True)
def authorize(*args, **kwargs):
	#Fetch provider URL from settings
	oauth_settings = get_oauth_settings()
	params = get_urlparams_from_kwargs(kwargs)
	request_url = urlparse(frappe.request.url)
	success_url = request_url.scheme + "://" + request_url.netloc + "/api/method/frappe.integration_broker.oauth2.approve?" + params
	failure_url = frappe.form_dict["redirect_uri"] + "?error=access_denied"

	if frappe.session['user']=='Guest':
		#Force login, redirect to preauth again.
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/login?redirect-to=/api/method/frappe.integration_broker.oauth2.authorize?" + quote(params)

	elif frappe.session['user']!='Guest':
		try:
			r = frappe.request
			uri = r.url
			http_method = r.method
			body = r.get_data()
			headers = r.headers

			scopes, frappe.flags.oauth_credentials = get_oauth_server().validate_authorization_request(uri, http_method, body, headers)

			skip_auth = frappe.db.get_value("OAuth Client", frappe.flags.oauth_credentials['client_id'], "skip_authorization")
			unrevoked_tokens = frappe.get_all("OAuth Bearer Token", filters={"status":"Active"})

			if skip_auth or (oauth_settings["skip_authorization"] == "Auto" and len(unrevoked_tokens)):

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
	r = frappe.request

	uri = r.url
	http_method = r.method
	body = r.form
	headers = r.headers

	try:
		headers, body, status = get_oauth_server().create_token_response(uri, http_method, body, headers, frappe.flags.oauth_credentials)
		frappe.local.response = frappe._dict(json.loads(body))
	except FatalClientError as e:
		return e


@frappe.whitelist(allow_guest=True)
def revoke_token(*args, **kwargs):
	r = frappe.request
	uri = r.url
	http_method = r.method
	body = r.form
	headers = r.headers

	headers, body, status = get_oauth_server().create_revocation_response(uri, headers=headers, body=body, http_method=http_method)

	frappe.local.response['http_status_code'] = status
	if status == 200:
		return "success"
	else:
		return "bad request"