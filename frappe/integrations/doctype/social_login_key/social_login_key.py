# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
import frappe.integrations.doctype.social_login_key.exceptions as slk_exceptions
from frappe import _
from frappe.model.document import Document

ICON_FILE_PATHS = {
	"Azure B2C": "/assets/frappe/icons/social/azure_b2c.svg",
	"Facebook": "/assets/frappe/icons/social/facebook.svg",
	"fairlogin": "/assets/frappe/icons/social/fair.svg",
	"Frappe": "/assets/frappe/icons/social/frappe.svg",
	"GitHub": "/assets/frappe/icons/social/github.svg",
	"Google": "/assets/frappe/icons/social/google.svg",
	"Office 365": "/assets/frappe/icons/social/office_365.svg",
	"Salesforce": "/assets/frappe/icons/social/salesforce.svg",
}


class SocialLoginKey(Document):
	def autoname(self):
		self.name = frappe.scrub(self.provider_name)

	def validate(self):
		self.set_icon()
		self.validate_data()
		if self.social_login_provider == "Azure B2C":
			self.set_azure_urls()

	def validate_data(self):
		if self.custom_base_url and not self.base_url:
			frappe.throw(
				_("Please enter Base URL"), exc=slk_exceptions.BaseUrlNotSetError
			)
		if not self.authorize_url:
			frappe.throw(
				_("Please enter Authorize URL"),
				exc=slk_exceptions.AuthorizeUrlNotSetError,
			)
		if not self.access_token_url:
			frappe.throw(
				_("Please enter Access Token URL"),
				exc=slk_exceptions.AccessTokenUrlNotSetError,
			)
		if not self.redirect_url:
			frappe.throw(
				_("Please enter Redirect URL"),
				exc=slk_exceptions.RedirectUrlNotSetError,
			)
		if self.enable_social_login and not self.client_id:
			frappe.throw(
				_("Please enter Client ID before social login is enabled"),
				exc=slk_exceptions.ClientIDNotSetError,
			)
		if self.enable_social_login and not self.client_secret:
			frappe.throw(
				_("Please enter Client Secret before social login is enabled"),
				exc=slk_exceptions.ClientSecretNotSetError,
			)

	def set_icon(self):
		if self.provider_name in ICON_FILE_PATHS:
			self.icon = ICON_FILE_PATHS[self.provider_name]

	def set_azure_urls(self):
		azure_oauth_urls = self.get_azure_oauth_urls()
		self.authorize_url = azure_oauth_urls.get("authorize_url")
		self.access_token_url = azure_oauth_urls.get("access_token_url")

	@frappe.whitelist()
	def get_social_login_provider(self, provider, initialize=False):
		providers = get_social_login_providers()

		# Initialize the doc and return, used in patch
		# Or can be used for creating key from controller
		if initialize and provider:
			for k, v in providers[provider].items():
				setattr(self, k, v)
			return

		return providers.get(provider) if provider else providers

	@frappe.whitelist()
	def get_azure_oauth_urls(self):
		azure_provider = self.get_social_login_provider("Azure B2C")

		return {
			"authorize_url": azure_provider.get("authorize_url", str()).format(
				tenant_id=self.azure_tenant_id
			),
			"access_token_url": azure_provider.get("access_token_url", str()).format(
				tenant_id=self.azure_tenant_id
			),
		}


def get_social_login_providers():
	providers_file_path = frappe.get_app_path(
		"frappe",
		"integrations",
		"doctype",
		"social_login_key",
		"social_login_providers.json",
	)

	return json.loads(open(providers_file_path).read())
