# -*- coding: utf-8 -*-
# Copyright (c) 2018, DOKOS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import get_request_site_address
import requests
import time
from frappe.utils.background_jobs import get_jobs

if frappe.conf.developer_mode:
	import os
	os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = 'https://www.googleapis.com/auth/calendar'
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"

class GCalendarSettings(Document):
	def sync(self):
		"""Create and execute Data Migration Run for GCalendar Sync plan"""
		frappe.has_permission('GCalendar Settings', throw=True)


		accounts = frappe.get_all("GCalendar Account", filters={'enabled': 1})

		queued_jobs = get_jobs(site=frappe.local.site, key='job_name')[frappe.local.site]
		for account in accounts:
			job_name = 'google_calendar_sync|{0}'.format(account.name)
			if job_name not in queued_jobs:
				frappe.enqueue('frappe.integrations.doctype.gcalendar_settings.gcalendar_settings.run_sync', queue='long', timeout=1500, job_name=job_name, account=account)
				time.sleep(5)

	def get_access_token(self):
		if not self.refresh_token:
			raise frappe.ValidationError(_("GCalendar is not configured."))
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
def sync():
	try:
		gcalendar_settings = frappe.get_doc('GCalendar Settings')
		if gcalendar_settings.enable == 1:
			gcalendar_settings.sync()
	except Exception:
		frappe.log_error(frappe.get_traceback())

def run_sync(account):
	exists = frappe.db.exists('Data Migration Run', dict(status=('in', ['Fail', 'Error'])))
	if exists:
		failed_run = frappe.get_doc("Data Migration Run", dict(status=('in', ['Fail', 'Error'])))
		failed_run.delete()

	started = frappe.db.exists('Data Migration Run', dict(status=('in', ['Started'])))
	if started:
		return

	try:
		doc = frappe.get_doc({
			'doctype': 'Data Migration Run',
			'data_migration_plan': 'GCalendar Sync',
			'data_migration_connector': 'Calendar Connector-' + account.name
		}).insert()
		try:
			doc.run()
		except Exception:
			frappe.log_error(frappe.get_traceback())
	except Exception:
		frappe.log_error(frappe.get_traceback())

@frappe.whitelist()
def google_callback(code=None, state=None, account=None):
	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.gcalendar_settings.gcalendar_settings.google_callback"
	if account is not None:
		frappe.cache().hset("gcalendar_account","GCalendar Account", account)
	doc = frappe.get_doc("GCalendar Settings")
	if code is None:
		return {
			'url': 'https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}'.format(doc.client_id, SCOPES, redirect_uri)
			}
	else:
		try:
			account = frappe.get_doc("GCalendar Account", frappe.cache().hget("gcalendar_account", "GCalendar Account"))
			data = {'code': code,
				'client_id': doc.client_id,
				'client_secret': doc.get_password(fieldname='client_secret',raise_exception=False),
				'redirect_uri': redirect_uri,
				'grant_type': 'authorization_code'}
			r = requests.post('https://www.googleapis.com/oauth2/v4/token', data=data).json()
			frappe.db.set_value("GCalendar Account", account.name, "authorization_code", code)
			if 'access_token' in r:
				frappe.db.set_value("GCalendar Account", account.name, "session_token", r['access_token'])
			if 'refresh_token' in r:
				frappe.db.set_value("GCalendar Account", account.name, "refresh_token", r['refresh_token'])
			frappe.db.commit()
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/integrations/gcalendar-success.html"
			return
		except Exception as e:
			frappe.throw(e.message)

@frappe.whitelist()
def refresh_token(token):
	if 'refresh_token' in token:
		frappe.db.set_value("GCalendar Settings", None, "refresh_token", token['refresh_token'])
	if 'access_token' in token:
		frappe.db.set_value("GCalendar Settings", None, "session_token", token['access_token'])
	frappe.db.commit()
