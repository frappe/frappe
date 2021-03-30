# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class GoogleSettings(Document):
	pass

def get_auth_url():
	return "https://www.googleapis.com/oauth2/v4/token"


@frappe.whitelist(allow_guest=True)
def get_file_picker_settings():
	"""Return all the data FileUploader needs to start the Google Drive Picker."""
	if frappe.session.user == 'Guest':
		return {'enabled': False}

	google_settings = frappe.get_single("Google Settings")
	if not (google_settings.enable and google_settings.google_drive_picker_enabled):
		return {'enabled': False}

	return {
		'enabled': True,
		'appId': google_settings.app_id,
		'developerKey': google_settings.api_key,
		'clientId': google_settings.client_id
	}
