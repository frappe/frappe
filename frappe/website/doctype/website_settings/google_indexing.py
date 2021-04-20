# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt


from urllib.parse import quote

import google.oauth2.credentials
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import frappe
from frappe import _
from frappe.integrations.doctype.google_settings.google_settings import get_auth_url
from frappe.utils import get_request_site_address

SCOPES = "https://www.googleapis.com/auth/indexing"


@frappe.whitelist()
def authorize_access(reauthorize=None):
	"""If no Authorization code get it from Google and then request for Refresh Token."""

	google_settings = frappe.get_doc("Google Settings")
	website_settings = frappe.get_doc("Website Settings")

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.website.doctype.website_settings.google_indexing.google_callback"

	if not website_settings.indexing_authorization_code or reauthorize:
		return get_authentication_url(client_id=google_settings.client_id, redirect_uri=redirect_uri)
	else:
		try:
			data = {
				"code": website_settings.indexing_authorization_code,
				"client_id": google_settings.client_id,
				"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
				"redirect_uri": redirect_uri,
				"grant_type": "authorization_code"
			}
			res = requests.post(get_auth_url(), data=data).json()

			if "refresh_token" in res:
				frappe.db.set_value("Website Settings", website_settings.name, "indexing_refresh_token", res.get("refresh_token"))
				frappe.db.commit()

			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/app/Form/{0}".format(quote("Website Settings"))

			frappe.msgprint(_("Google Indexing has been configured."))
		except Exception as e:
			frappe.throw(e)


def get_authentication_url(client_id, redirect_uri):
	"""Return authentication url with the client id and redirect uri."""
	return {
		"url": "https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}".format(client_id, SCOPES, redirect_uri)
	}


@frappe.whitelist()
def google_callback(code=None):
	"""Authorization code is sent to callback as per the API configuration."""
	frappe.db.set_value("Website Settings", None, "indexing_authorization_code", code)
	frappe.db.commit()

	authorize_access()


def get_google_indexing_object():
	"""Returns an object of Google Indexing object."""
	google_settings = frappe.get_doc("Google Settings")
	account = frappe.get_doc("Website Settings")

	credentials_dict = {
		"token": account.get_access_token(),
		"refresh_token": account.get_password(fieldname="indexing_refresh_token", raise_exception=False),
		"token_uri": get_auth_url(),
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		"scopes": "https://www.googleapis.com/auth/indexing"
	}

	credentials = google.oauth2.credentials.Credentials(**credentials_dict)
	google_indexing = build(
		serviceName="indexing",
		version="v3",
		credentials=credentials,
		static_discovery=False
	)

	return google_indexing


def publish_site(url, operation_type="URL_UPDATED"):
	"""Send an update/remove url request."""

	google_indexing = get_google_indexing_object()
	body = {
		"url": url,
		"type": operation_type
	}
	try:
		google_indexing.urlNotifications().publish(body=body, x__xgafv='2').execute()
	except HttpError as e:
		frappe.log_error(message=e, title='API Indexing Issue')
