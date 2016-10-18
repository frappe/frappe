from __future__ import unicode_literals
import frappe, json
from frappe.oauth import OAuthWebRequestValidator, WebApplicationServer
from oauthlib.oauth2 import FatalClientError, OAuth2Error
from urllib import quote, urlencode
from urlparse import urlparse

#Variables required across requests
oauth_validator = OAuthWebRequestValidator()
oauth_server  = WebApplicationServer(oauth_validator)
credentials = None

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
		scopes, credentials = oauth_server.validate_authorization_request(uri, http_method, body, headers)

		headers, body, status = oauth_server.create_authorization_response(uri=credentials['redirect_uri'], \
				body=body, headers=headers, scopes=scopes, credentials=credentials)
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
	params = get_urlparams_from_kwargs(kwargs)
	request_url = urlparse(frappe.request.url)
	success_url =  request_url.scheme + request_url.netloc + "/api/method/frappe.integration_broker.oauth2.approve?" + params

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

			scopes, credentials = oauth_server.validate_authorization_request(uri, http_method, body, headers)

			skip_auth = frappe.db.get_value("OAuth Client", credentials['client_id'], "skip_authorization")
			unrevoked_tokens = frappe.get_all("OAuth Bearer Token", filters={"status":"Active"})

			if skip_auth or (oauth_settings["skip_authorization"] == "Auto" and len(unrevoked_tokens)):

				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = success_url
			else:
				#Show Allow/Deny screen.
				response_html_params = frappe._dict({
					"client_id": frappe.db.get_value("OAuth Client", kwargs['client_id'], "app_name"),
					"success_url": success_url,
					"details": scopes,
					"error": ""
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
	body = r.get_data()
	headers = r.headers

	try:
		headers, body, status = oauth_server.create_token_response(uri, http_method, body, headers, credentials)
		out = json.loads(body)
		return out
	except FatalClientError as e:
		return e


@frappe.whitelist(allow_guest=True)
def revoke_token(*args, **kwargs):
	r = frappe.request
	uri = r.url
	http_method = r.method
	body = r.get_data()
	headers = r.headers
	
	headers, body, status = oauth_server.create_revocation_response(uri, headers=headers, body=body, http_method=http_method)
	
	frappe.local.response = frappe._dict({"status": status})

	return "Access Token revoked successfully"

@frappe.whitelist(allow_guest=True, xss_safe=True)
def test_resource(*args, **kwargs):
	r = frappe.request
	uri = r.url
	http_method = r.method
	body = r.get_data()
	headers = r.headers

	if not kwargs["access_token"]:
		return "Access Token Required"

	required_scopes = frappe.db.get_value("OAuth Bearer Token", kwargs["access_token"], "scopes").split(";")

	valid, oauthlib_request = oauth_server.verify_request(uri, http_method, body, headers, required_scopes)

	if valid:
	 	return "Access Granted"
	else:
		return "403: Forbidden"
