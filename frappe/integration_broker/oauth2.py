from __future__ import unicode_literals
import frappe, json
from frappe.oauth import OAuthWebRequestValidator, WebApplicationServer
from oauthlib.oauth2 import FatalClientError, OAuth2Error
from urllib import quote, urlencode
#from mnt_oauth.doctype.oauth_provider_settings.oauth_provider_settings import get_oauth_settings
#from mnt_oauth_provider_decorator import OAuth2ProviderDecorator


#Variables required across requests
oauth_validator = OAuthWebRequestValidator()
oauth_server  = WebApplicationServer(oauth_validator)
credentials = None
# provider = OAuth2ProviderDecorator(oauth_server)

def get_urlparams_from_kwargs(param_kwargs):
	arguments = param_kwargs
	if arguments.get("data"):
		arguments.pop("data")
	if arguments.get("cmd"):
		arguments.pop("cmd")

	return urlencode(arguments)

# def hasvalidtoken(client, scopes):
# 	tokens = frappe.get_all("OAuth Bearer Token", fields=["name", "scopes"], \
# 		filters=[['client', '=', client], ['status', '=', 'Active'], ['expiration_time', '>', frappe.utils.datetime.datetime.now()]])
# 		# check past authorizations regarded the same scopes as the current one
# 	token_names = []
# 	for token in tokens:
# 		if token["scopes"] in scopes:
# 			return True
# 	return False
@frappe.whitelist()
def test():
    return "Test"

@frappe.whitelist()
def mnt_approveauth(*args, **kwargs):
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
def mnt_authorize(*args, **kwargs):
	#Fetch provider URL from settings
	oauth_settings = get_oauth_settings()
	params = get_urlparams_from_kwargs(kwargs)
	success_url = oauth_settings["provider_url"] + "/api/method/mnt_oauth.api_oauth.mnt_approveauth?" + params

	if frappe.session['user']=='Guest':
		#Force login, redirect to preauth again.
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/login?redirect-to=/api/method/mnt_oauth.api_oauth.mnt_authorize?" + quote(params)

	elif frappe.session['user']!='Guest':
		try:
			r = frappe.request
			uri = r.url
			http_method = r.method
			body = r.get_data()
			headers = r.headers

			scopes, credentials = oauth_server.validate_authorization_request(uri, http_method, body, headers)

			skipauth = frappe.db.get_value("OAuth Client", credentials['client_id'], "skip_authorization")
			unrevoked_tokens = frappe.get_all("OAuth Bearer Token", filters={"status":"Active"})

			if skipauth or (oauth_settings["skip_authorization"] == "Auto" and len(unrevoked_tokens)):

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
				resp_html = frappe.render_template("mnt_oauth/templates/includes/mnt_oauth_confirmation.html", response_html_params)
				frappe.respond_as_web_page("MNT OAuth Conf.", resp_html)

		except FatalClientError as e:
			return e
		except OAuth2Error as e:
			return e

def printstuff(s,times=100):
	for x in xrange(1,times):
		print s

@frappe.whitelist(allow_guest=True)
def mnt_gettoken(*args, **kwargs):
	r = frappe.request

	uri = r.url
	http_method = r.method
	body = r.get_data()
	headers = r.headers

	try:
		headers, body, status = oauth_server.create_token_response(uri, http_method, body, headers, credentials)
		out = json.loads(body)

		otoken_user = frappe.db.get_value("OAuth Bearer Token", out.get("access_token"), "user")
		#Add User ID to token response.
		out.update({"user_id": otoken_user})

		return out
	except FatalClientError as e:
		return e


@frappe.whitelist(allow_guest=True)
def mnt_revoketoken(*args, **kwargs):
	r = frappe.request
	uri = r.url
	http_method = r.method
	body = r.get_data()
	headers = r.headers

	headers, body, status = oauth_server.create_revocation_response(uri, headers=headers, body=body, http_method=http_method)

	#return body

	frappe.local.response = frappe._dict({"status": status})

	##return headers, body, status

@frappe.whitelist(allow_guest=True, xss_safe=True)
def mnt_testresource(*args, **kwargs):
	r = frappe.request
	uri = r.url
	http_method = r.method
	body = r.get_data()
	headers = r.headers

	# for x in xrange(1,20):
	# 	print r

	if not kwargs["access_token"]:
		return "Access Token Required"

	required_scopes = frappe.db.get_value("OAuth Bearer Token", kwargs["access_token"], "scopes").split(";")

	valid, oauthlib_request = oauth_server.verify_request(uri, http_method, body, headers, required_scopes)


	if valid:
	 	return "Access Granted"
	else:
		return "403: Forbidden"

	# if not kwargs["access_token"]:
	# 	return "Access Token Required"

	# valid_token = frappe.get_doc("OAuth Bearer Token", kwargs["access_token"])

	# if valid_token.expiration_time < frappe.datetime.datetime.utils.now() and valid_token.status == "Active":
	#elif

import frappe.website.render

@frappe.whitelist(allow_guest=True, xss_safe=True)
def testfunc(*args, **kwargs):
	r = frappe.request
	uri = r.url
	http_method = r.method
	body = r.get_data()
	headers = r.headers

	#frappe.response.headers.add("xyz","abc") Nonetype
	#frappe.response['headers'] = {"abc":"xyz0"} Nonetype




	# #return frappe.website.render.build_response (uri, "Pass", 200, headers={"abc":"xyz"})
	# frappe.response.headers.add("abc","xyz")

	# return "x"


	# from werkzeug.wrappers import Response
	# # build response
	# response = Response()
	# response.mimetype = 'text/json'
	# response.charset = 'utf-8'
	# response.headers[b"ABC"] = "XYZ".encode("utf-8")
	# response.data = "BLAH".encode("utf-8")
	# return response
