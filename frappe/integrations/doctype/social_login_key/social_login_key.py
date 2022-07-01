# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe import _
from frappe.model.document import Document


class BaseUrlNotSetError(frappe.ValidationError):
	pass


class AuthorizeUrlNotSetError(frappe.ValidationError):
	pass


class AccessTokenUrlNotSetError(frappe.ValidationError):
	pass


class RedirectUrlNotSetError(frappe.ValidationError):
	pass


class ClientIDNotSetError(frappe.ValidationError):
	pass


class ClientSecretNotSetError(frappe.ValidationError):
	pass


class SocialLoginKey(Document):
	def autoname(self):
		self.name = frappe.scrub(self.provider_name)

	def validate(self):
		self.set_icon()
		if self.custom_base_url and not self.base_url:
			frappe.throw(_("Please enter Base URL"), exc=BaseUrlNotSetError)
		if not self.authorize_url:
			frappe.throw(_("Please enter Authorize URL"), exc=AuthorizeUrlNotSetError)
		if not self.access_token_url:
			frappe.throw(_("Please enter Access Token URL"), exc=AccessTokenUrlNotSetError)
		if not self.redirect_url:
			frappe.throw(_("Please enter Redirect URL"), exc=RedirectUrlNotSetError)
		if self.enable_social_login and not self.client_id:
			frappe.throw(
				_("Please enter Client ID before social login is enabled"), exc=ClientIDNotSetError
			)
		if self.enable_social_login and not self.client_secret:
			frappe.throw(
				_("Please enter Client Secret before social login is enabled"), exc=ClientSecretNotSetError
			)

	def set_icon(self):
		icon_map = {
			"Google": "google.svg",
			"Frappe": "frappe.svg",
			"Facebook": "facebook.svg",
			"Office 365": "office_365.svg",
			"GitHub": "github.svg",
			"Salesforce": "salesforce.svg",
			"fairlogin": "fair.svg",
		}

		if self.provider_name in icon_map:
			icon_file = icon_map[self.provider_name]
			self.icon = f"/assets/frappe/icons/social/{icon_file}"

	@frappe.whitelist()
	def get_social_login_provider(self, provider, initialize=False):
		providers = {}

		providers["Office 365"] = {
			"provider_name": "Office 365",
			"enable_social_login": 1,
			"base_url": "https://login.microsoftonline.com",
			"custom_base_url": 0,
			"icon": "fa fa-windows",
			"authorize_url": "https://login.microsoftonline.com/common/oauth2/authorize",
			"access_token_url": "https://login.microsoftonline.com/common/oauth2/token",
			"redirect_url": "/api/method/frappe.integrations.oauth2_logins.login_via_office365",
			"api_endpoint": None,
			"api_endpoint_args": None,
			"auth_url_data": json.dumps({"response_type": "code", "scope": "openid"}),
		}

		providers["GitHub"] = {
			"provider_name": "GitHub",
			"enable_social_login": 1,
			"base_url": "https://api.github.com/",
			"custom_base_url": 0,
			"icon": "fa fa-github",
			"authorize_url": "https://github.com/login/oauth/authorize",
			"access_token_url": "https://github.com/login/oauth/access_token",
			"redirect_url": "/api/method/frappe.www.login.login_via_github",
			"api_endpoint": "user",
			"api_endpoint_args": None,
			"auth_url_data": json.dumps({"scope": "user:email"}),
		}

		providers["Google"] = {
			"provider_name": "Google",
			"enable_social_login": 1,
			"base_url": "https://www.googleapis.com",
			"custom_base_url": 0,
			"icon": "fa fa-google",
			"authorize_url": "https://accounts.google.com/o/oauth2/auth",
			"access_token_url": "https://accounts.google.com/o/oauth2/token",
			"redirect_url": "/api/method/frappe.www.login.login_via_google",
			"api_endpoint": "oauth2/v2/userinfo",
			"api_endpoint_args": None,
			"auth_url_data": json.dumps(
				{
					"scope": "https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email",
					"response_type": "code",
				}
			),
		}

		providers["Facebook"] = {
			"provider_name": "Facebook",
			"enable_social_login": 1,
			"base_url": "https://graph.facebook.com",
			"custom_base_url": 0,
			"icon": "fa fa-facebook",
			"authorize_url": "https://www.facebook.com/dialog/oauth",
			"access_token_url": "https://graph.facebook.com/oauth/access_token",
			"redirect_url": "/api/method/frappe.www.login.login_via_facebook",
			"api_endpoint": "/v2.5/me",
			"api_endpoint_args": json.dumps(
				{"fields": "first_name,last_name,email,gender,location,verified,picture"}
			),
			"auth_url_data": json.dumps(
				{"display": "page", "response_type": "code", "scope": "email,public_profile"}
			),
		}

		providers["Frappe"] = {
			"provider_name": "Frappe",
			"enable_social_login": 1,
			"custom_base_url": 1,
			"icon": "/assets/frappe/images/frappe-favicon.svg",
			"redirect_url": "/api/method/frappe.www.login.login_via_frappe",
			"api_endpoint": "/api/method/frappe.integrations.oauth2.openid_profile",
			"api_endpoint_args": None,
			"authorize_url": "/api/method/frappe.integrations.oauth2.authorize",
			"access_token_url": "/api/method/frappe.integrations.oauth2.get_token",
			"auth_url_data": json.dumps({"response_type": "code", "scope": "openid"}),
		}

		providers["Salesforce"] = {
			"provider_name": "Salesforce",
			"enable_social_login": 1,
			"base_url": "https://login.salesforce.com",
			"custom_base_url": 0,
			"icon": "fa fa-cloud",  # https://github.com/FortAwesome/Font-Awesome/issues/1744
			"redirect_url": "/api/method/frappe.integrations.oauth2_logins.login_via_salesforce",
			"api_endpoint": "https://login.salesforce.com/services/oauth2/userinfo",
			"api_endpoint_args": None,
			"authorize_url": "https://login.salesforce.com/services/oauth2/authorize",
			"access_token_url": "https://login.salesforce.com/services/oauth2/token",
			"auth_url_data": json.dumps({"response_type": "code", "scope": "openid"}),
		}

		providers["fairlogin"] = {
			"provider_name": "fairlogin",
			"enable_social_login": 1,
			"base_url": "https://id.fairkom.net/auth/realms/fairlogin/",
			"custom_base_url": 0,
			"icon": "fa fa-key",
			"redirect_url": "/api/method/frappe.integrations.oauth2_logins.login_via_fairlogin",
			"api_endpoint": "https://id.fairkom.net/auth/realms/fairlogin/protocol/openid-connect/userinfo",
			"api_endpoint_args": None,
			"authorize_url": "https://id.fairkom.net/auth/realms/fairlogin/protocol/openid-connect/auth",
			"access_token_url": "https://id.fairkom.net/auth/realms/fairlogin/protocol/openid-connect/token",
			"auth_url_data": json.dumps({"response_type": "code", "scope": "openid"}),
		}

		# Initialize the doc and return, used in patch
		# Or can be used for creating key from controller
		if initialize and provider:
			for k, v in providers[provider].items():
				setattr(self, k, v)
			return

		return providers.get(provider) if provider else providers
