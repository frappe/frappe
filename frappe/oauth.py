import frappe, urllib

from urlparse import parse_qs, urlparse
from oauthlib.oauth2.rfc6749.tokens import BearerToken
from oauthlib.oauth2.rfc6749.grant_types import AuthorizationCodeGrant, ImplicitGrant, ResourceOwnerPasswordCredentialsGrant, ClientCredentialsGrant,  RefreshTokenGrant
from oauthlib.oauth2 import RequestValidator
from oauthlib.oauth2.rfc6749.endpoints.authorization import AuthorizationEndpoint
from oauthlib.oauth2.rfc6749.endpoints.token import TokenEndpoint
from oauthlib.oauth2.rfc6749.endpoints.resource import ResourceEndpoint
from oauthlib.oauth2.rfc6749.endpoints.revocation import RevocationEndpoint
from oauthlib.common import Request

class WebApplicationServer(AuthorizationEndpoint, TokenEndpoint, ResourceEndpoint,
						   RevocationEndpoint):

	"""An all-in-one endpoint featuring Authorization code grant and Bearer tokens."""

	def __init__(self, request_validator, token_generator=None,
				 token_expires_in=None, refresh_token_generator=None, **kwargs):
		"""Construct a new web application server.

		:param request_validator: An implementation of
								  oauthlib.oauth2.RequestValidator.
		:param token_expires_in: An int or a function to generate a token
								 expiration offset (in seconds) given a
								 oauthlib.common.Request object.
		:param token_generator: A function to generate a token from a request.
		:param refresh_token_generator: A function to generate a token from a
										request for the refresh token.
		:param kwargs: Extra parameters to pass to authorization-,
					   token-, resource-, and revocation-endpoint constructors.
		"""
		auth_grant = AuthorizationCodeGrant(request_validator)
		refresh_grant = RefreshTokenGrant(request_validator)
		bearer = BearerToken(request_validator, token_generator,
							 token_expires_in, refresh_token_generator)
		AuthorizationEndpoint.__init__(self, default_response_type='code',
									   response_types={'code': auth_grant},
									   default_token_type=bearer)
		TokenEndpoint.__init__(self, default_grant_type='authorization_code',
							   grant_types={
								   'authorization_code': auth_grant,
								   'refresh_token': refresh_grant,
							   },
							   default_token_type=bearer)
		ResourceEndpoint.__init__(self, default_token='Bearer',
								  token_types={'Bearer': bearer})
		RevocationEndpoint.__init__(self, request_validator)


class OAuthWebRequestValidator(RequestValidator):

	# Pre- and post-authorization.
	def validate_client_id(self, client_id, request, *args, **kwargs):
		# Simple validity check, does client exist? Not banned?
		cli_id = frappe.db.get_value("OAuth Client",{ "name":client_id })
		if cli_id:
			request.client = frappe.get_doc("OAuth Client", client_id).as_dict()
			return True
		else:
			return False

	def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
		# Is the client allowed to use the supplied redirect_uri? i.e. has
		# the client previously registered this EXACT redirect uri.

		redirect_uris = frappe.db.get_value("OAuth Client", client_id, 'redirect_uris').split(';')

		if redirect_uri in redirect_uris:
			return True
		else:
			return False

	def get_default_redirect_uri(self, client_id, request, *args, **kwargs):
		# The redirect used if none has been supplied.
		# Prefer your clients to pre register a redirect uri rather than
		# supplying one on each authorization request.
		redirect_uri = frappe.db.get_value("OAuth Client", client_id, 'default_redirect_uri')
		return redirect_uri

	def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
		# Is the client allowed to access the requested scopes?
		client_scopes = frappe.db.get_value("OAuth Client", client_id, 'scopes').split(';')

		are_scopes_valid = True

		for scp in scopes:
			are_scopes_valid = are_scopes_valid and True if scp in client_scopes else False

		return are_scopes_valid

	def get_default_scopes(self, client_id, request, *args, **kwargs):
		# Scopes a client will authorize for if none are supplied in the
		# authorization request.
		scopes = frappe.db.get_value("OAuth Client", client_id, 'scopes').split(';')
		request.scopes = scopes #Apparently this is possible.
		return scopes

	def validate_response_type(self, client_id, response_type, client, request, *args, **kwargs):
		# Clients should only be allowed to use one type of response type, the
		# one associated with their one allowed grant type.
		# In this case it must be "code".

		return (client.response_type.lower() == response_type)


	# Post-authorization

	def save_authorization_code(self, client_id, code, request, *args, **kwargs):

		cookie_dict = get_cookie_dict_from_headers(request)

		oac = frappe.new_doc('OAuth Authorization Code')
		oac.scopes = ';'.join(request.scopes)
		oac.redirect_uri_bound_to_authorization_code = request.redirect_uri
		oac.client = client_id
		oac.user = urllib.unquote(cookie_dict['user_id'])
		oac.authorization_code = code['code']
		oac.save(ignore_permissions=True)
		frappe.db.commit()

	def authenticate_client(self, request, *args, **kwargs):

		cookie_dict = get_cookie_dict_from_headers(request)

		#Get ClientID in URL
		if request.client_id:
			oc = frappe.get_doc("OAuth Client", request.client_id)
		else:
			#Extract token, instantiate OAuth Bearer Token and use clientid from there.
			if frappe.form_dict.has_key("refresh_token"):
				oc = frappe.get_doc("OAuth Client", frappe.db.get_value("OAuth Bearer Token", {"refresh_token": frappe.form_dict["refresh_token"]}, 'client'))
			else:
				oc = frappe.get_doc("OAuth Client", frappe.db.get_value("OAuth Bearer Token", frappe.form_dict["token"], 'client'))
		try:
			request.client = request.client or oc.as_dict()
		except Exception, e:
			print "Failed body authentication: Application %s does not exist".format(cid=request.client_id)

		return frappe.session.user == urllib.unquote(cookie_dict.get('user_id', "Guest"))

	def authenticate_client_id(self, client_id, request, *args, **kwargs):
		cli_id = frappe.db.get_value('OAuth Client', client_id, 'name')
		if not cli_id:
			# Don't allow public (non-authenticated) clients
			return False
		else:
			request["client"] = frappe.get_doc("OAuth Client", cli_id)
			return True

	def validate_code(self, client_id, code, client, request, *args, **kwargs):
		# Validate the code belongs to the client. Add associated scopes,
		# state and user to request.scopes and request.user.

		validcodes = frappe.get_all("OAuth Authorization Code", filters={"client": client_id, "validity": "Valid"})

		checkcodes = []
		for vcode in validcodes:
			checkcodes.append(vcode["name"])

		if code in checkcodes:
			request.scopes = frappe.db.get_value("OAuth Authorization Code", code, 'scopes').split(';')
			request.user = frappe.db.get_value("OAuth Authorization Code", code, 'user')
			return True
		else:
			return False

	def confirm_redirect_uri(self, client_id, code, redirect_uri, client, *args, **kwargs):
		saved_redirect_uri = frappe.db.get_value('OAuth Client', client_id, 'default_redirect_uri')

		return saved_redirect_uri == redirect_uri

	def validate_grant_type(self, client_id, grant_type, client, request, *args, **kwargs):
		# Clients should only be allowed to use one type of grant.
		# In this case, it must be "authorization_code" or "refresh_token"
		return (grant_type in ["authorization_code", "refresh_token"])

	def save_bearer_token(self, token, request, *args, **kwargs):
		# Remember to associate it with request.scopes, request.user and
		# request.client. The two former will be set when you validate
		# the authorization code. Don't forget to save both the
		# access_token and the refresh_token and set expiration for the
		# access_token to now + expires_in seconds.

		otoken = frappe.new_doc("OAuth Bearer Token")
		otoken.client = request.client['name']
		otoken.user = request.user
		otoken.scopes = ";".join(request.scopes)
		otoken.access_token = token['access_token']
		otoken.refresh_token = token['refresh_token']
		otoken.expires_in = token['expires_in']
		otoken.save(ignore_permissions=True)
		frappe.db.commit()

		default_redirect_uri = frappe.db.get_value("OAuth Client", request.client['name'], "default_redirect_uri")
		return default_redirect_uri

	def invalidate_authorization_code(self, client_id, code, request, *args, **kwargs):
		# Authorization codes are use once, invalidate it when a Bearer token
		# has been acquired.

		frappe.db.set_value("OAuth Authorization Code", code, "validity", "Invalid")
		frappe.db.commit()

	# Protected resource request

	def validate_bearer_token(self, token, scopes, request):
		# Remember to check expiration and scope membership
		otoken = frappe.get_doc("OAuth Bearer Token", token) #{"access_token": str(token)})
		is_token_valid = (frappe.utils.datetime.datetime.now() < otoken.expiration_time) \
			and otoken.status != "Revoked"
		client_scopes = frappe.db.get_value("OAuth Client", otoken.client, 'scopes').split(';')
		are_scopes_valid = True
		for scp in scopes:
			are_scopes_valid = are_scopes_valid and True if scp in client_scopes else False

		return is_token_valid and are_scopes_valid

	# Token refresh request
	def get_original_scopes(self, refresh_token, request, *args, **kwargs):
		# Obtain the token associated with the given refresh_token and
		# return its scopes, these will be passed on to the refreshed
		# access token if the client did not specify a scope during the
		# request.
		obearer_token = frappe.get_doc("OAuth Bearer Token", {"refresh_token": refresh_token})
		return obearer_token.scopes

	def revoke_token(self, token, token_type_hint, request, *args, **kwargs):
		"""Revoke an access or refresh token.

		:param token: The token string.
		:param token_type_hint: access_token or refresh_token.
		:param request: The HTTP Request (oauthlib.common.Request)

		Method is used by:
			- Revocation Endpoint
		"""
		otoken = None

		if token_type_hint == "access_token":
			otoken = frappe.db.set_value("OAuth Bearer Token", token, 'status', 'Revoked')
		elif token_type_hint == "refresh_token":
			otoken = frappe.db.set_value("OAuth Bearer Token", {"refresh_token": token}, 'status', 'Revoked')
		else:
			otoken = frappe.db.set_value("OAuth Bearer Token", token, 'status', 'Revoked')
		frappe.db.commit()

	def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
			# """Ensure the Bearer token is valid and authorized access to scopes.

			# OBS! The request.user attribute should be set to the resource owner
			# associated with this refresh token.

			# :param refresh_token: Unicode refresh token
			# :param client: Client object set by you, see authenticate_client.
			# :param request: The HTTP Request (oauthlib.common.Request)
			# :rtype: True or False

			# Method is used by:
			# 	- Authorization Code Grant (indirectly by issuing refresh tokens)
			# 	- Resource Owner Password Credentials Grant (also indirectly)
			# 	- Refresh Token Grant
			# """
			# raise NotImplementedError('Subclasses must implement this method.')

		otoken = frappe.get_doc("OAuth Bearer Token", {"refresh_token": refresh_token, "status": "Active"})

		if not otoken:
			return False
		else:
			return True

		#TODO: Validate scopes.

def get_cookie_dict_from_headers(r):
	if r.headers.get('Cookie'):
		cookie = r.headers.get('Cookie')
		cookie = cookie.split("; ")
		cookie_dict = {k:v for k,v in (x.split('=') for x in cookie)}
		return cookie_dict
	else:
		return {}
