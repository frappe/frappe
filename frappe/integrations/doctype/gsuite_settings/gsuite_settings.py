 # Copyright (c) 2017, Frappe Technologies and contributors
# -*- coding: utf-8 -*-
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_request_site_address
import requests
from json import dumps
from frappe.utils.response import json_handler

SCOPES = 'https://www.googleapis.com/auth/drive'

class GSuiteSettings(Document):

	def get_access_token(self):
		if not self.refresh_token:
			raise frappe.ValidationError(_("Google GSuite is not configured."))
		data = {
			'client_id': self.client_id,
			'client_secret': self.get_password(fieldname='client_secret',raise_exception=False),
			'refresh_token': self.get_password(fieldname='refresh_token',raise_exception=False),
			'grant_type': "refresh_token",
			'scope': SCOPES
		}
		try:
			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()
		except requests.exceptions.HTTPError:
			frappe.throw(_("Something went wrong during the token generation. Please request again an authorization code."))
		return r.get('access_token')

@frappe.whitelist()
def gsuite_callback(code=None):
	doc = frappe.get_doc("GSuite Settings")
	if code is None:
		return {
			'url': 'https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&client_id={}&scope={}&redirect_uri={}?cmd=frappe.integrations.doctype.gsuite_settings.gsuite_settings.gsuite_callback'.format(doc.client_id, SCOPES, get_request_site_address(True))
			}
	else:
		try:
			data = {'code': code,
				'client_id': doc.client_id,
				'client_secret': doc.get_password(fieldname='client_secret',raise_exception=False),
				'redirect_uri': get_request_site_address(True) + '?cmd=frappe.integrations.doctype.gsuite_settings.gsuite_settings.gsuite_callback',
				'grant_type': 'authorization_code'}
			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()
			frappe.db.set_value("Gsuite Settings", None, "authorization_code", code)
			if 'refresh_token' in r:
				frappe.db.set_value("Gsuite Settings", None, "refresh_token", r['refresh_token'])
			frappe.db.commit()
			return
		except Exception as e:
			frappe.throw(e.message)

def run_gsuite_script(option, filename = None, template_id = None, destination_id = None, json_data = None):
	gdoc = frappe.get_doc('GSuite Settings')
	if gdoc.script_url:
		data = {
			'exec': option,
			'filename': filename,
			'template': template_id,
			'destination': destination_id,
			'vars' : json_data
		}
		headers = {'Authorization': 'Bearer {}'.format( gdoc.get_access_token() )}

		try:
			r = requests.post(gdoc.script_url, headers=headers, data=dumps(data, default=json_handler, separators=(',',':')))
		except Exception as e:
			frappe.throw(e.message)

		try:
			r = r.json()
		except:
			# if request doesn't return json show HTML ask permissions or to identify the error on google side
			frappe.throw(r.text)

		return r
	else:
		frappe.throw(_('Please set script URL on Gsuite Settings'))

@frappe.whitelist()
def run_script_test():
	r = run_gsuite_script('test')
	return r['test']
