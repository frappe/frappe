# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE


from urllib.parse import quote

from googleapiclient.errors import HttpError

import frappe
from frappe import _
from frappe.integrations.google_oauth import GoogleOAuth
from frappe.utils import get_request_site_address


@frappe.whitelist(methods=["POST", "GET"])
def authorize_access(reauthorize=False, code=None):
	"""If no Authorization code get it from Google and then request for Refresh Token."""

	oauth_code = (
		frappe.db.get_value("Website Settings", "Website Settings", "indexing_authorization_code")
		if not code
		else code
	)

	oauth_obj = GoogleOAuth("indexing")

	if not oauth_code or reauthorize:
		return oauth_obj.get_authentication_url(
			get_request_site_address(True),
			state={
				"method": "frappe.website.doctype.website_settings.google_indexing.authorize_access",
				"redirect": "/app/Form/{0}".format(quote("Website Settings")),
			},
		)

	frappe.db.set_value("Website Settings", None, "indexing_authorization_code", oauth_code)
	res = oauth_obj.authorize(oauth_code, get_request_site_address(True))
	frappe.db.set_value(
		"Website Settings", "Website Settings", "indexing_refresh_token", res.get("refresh_token")
	)


def get_google_indexing_object():
	"""Returns an object of Google Indexing object."""
	account = frappe.get_doc("Website Settings")
	oauth_obj = GoogleOAuth("indexing")

	return oauth_obj.get_google_service_object(
		account.get_access_token(),
		account.get_password(fieldname="indexing_refresh_token", raise_exception=False),
	)


def publish_site(url, operation_type="URL_UPDATED"):
	"""Send an update/remove url request."""

	google_indexing = get_google_indexing_object()
	body = {"url": url, "type": operation_type}
	try:
		google_indexing.urlNotifications().publish(body=body, x__xgafv="2").execute()
	except HttpError as e:
		frappe.log_error(message=e, title="API Indexing Issue")
