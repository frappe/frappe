# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_request_site_address

SCOPES = 'https://www.googleapis.com/auth/calendar/v3'

class GoogleCalendar(Document):

	def validate(self):
		if not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(_("Enable Google API in Google Settings."))

	def get_access_token(self):
		google_settings = frappe.get_doc("Google Settings")

		if not google_settings.enable:
			frappe.throw(_("Google Calendar Integration is disabled."))

		if not self.refresh_token:
			button_label = frappe.bold(_('Allow Google Calendar Access'))
			raise frappe.ValidationError(_("Click on {0} to generate Refresh Token.").format(button_label))

		data = {
			"client_id": google_settings.client_id,
			"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
			"refresh_token": self.get_password(fieldname="refresh_token", raise_exception=False),
			"grant_type": "refresh_token",
			"scope": SCOPES
		}

		try:
			r = requests.post("https://www.googleapis.com/oauth2/v4/token", data=data).json()
		except requests.exceptions.HTTPError:
			button_label = frappe.bold(_('Allow Google Calendar Access'))
			frappe.throw(_("Something went wrong during the token generation. Click on {0} to generate a new one.").format(button_label))

		return r.get("access_token")

@frappe.whitelist()
def authorize_access(g_calendar, reauthorize=None):
	"""
		If no Authorization code get it from Google and then request for Refresh Token.
		Google Contact Name is set to flags to set_value after Authorization Code is obtained.
	"""

	google_settings = frappe.get_doc("Google Settings")
	google_calendar = frappe.get_doc("Google Calendar", g_calendar)

	redirect_uri = get_request_site_address(True) + "?cmd=frappe.integrations.doctype.google_calendar.google_calendar.google_callback"

	if not google_calendar.authorization_code or reauthorize:
		frappe.cache().hset("google_calendar", "google_calendar", google_calendar.name)
		return google_callback(client_id=google_settings.client_id, redirect_uri=redirect_uri)
	else:
		try:
			data = {
				"code": google_calendar.authorization_code,
				"client_id": google_settings.client_id,
				"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
				"redirect_uri": redirect_uri,
				"grant_type": "authorization_code"
			}
			r = requests.post("https://www.googleapis.com/oauth2/v4/token", data=data).json()

			if "refresh_token" in r:
				frappe.db.set_value("Google Calendar", google_calendar.name, "refresh_token", r.get("refresh_token"))
				frappe.db.commit()

			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/desk#Form/Google%20Calendar/{}".format(google_calendar.name)

			frappe.msgprint(_("Google Calendar has been configured."))
		except Exception as e:
			frappe.throw(e)

@frappe.whitelist()
def google_callback(client_id=None, redirect_uri=None, code=None):
	"""
		Authorization code is sent to callback as per the API configuration
	"""
	if code is None:
		return {
			"url": "https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}".format(client_id, SCOPES, redirect_uri)
		}
	else:
		google_calendar = frappe.cache().hget("google_calendar", "google_calendar")
		frappe.db.set_value("Google Calendar", google_calendar, "authorization_code", code)
		frappe.db.commit()

		authorize_access(google_calendar)

class GoogleCalendarSync():
	def __init__(self, g_calendar):
		google_settings = frappe.get_doc("Google Settings")

		g_calendar = frappe.get_doc("Google Calendar", g_calendar)

		credentials_dict = {
			'refresh_token': g_calendar.refresh_token,
			'token_uri': 'https://www.googleapis.com/oauth2/v4/token',
			'client_id': google_settings.client_id,
			'client_secret': google_settings.get_password(fieldname='client_secret', raise_exception=False),
			'scopes':'https://www.googleapis.com/auth/calendar'
			}

		credentials = google.oauth2.credentials.Credentials(**credentials_dict)
		google_calendar = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials)

		self.check_remote_calendar()

	def check_remote_calendar(self):
		def _create_calendar():
			timezone = frappe.db.get_value("System Settings", None, "time_zone")
			calendar = {
				'summary': self.account.calendar_name,
				'timeZone': timezone
			}
			try:
				created_calendar = self.gcalendar.calendars().insert(body=calendar).execute()
				frappe.db.set_value("GCalendar Account", self.account.name, "gcalendar_id", created_calendar["id"])
			except Exception:
				frappe.log_error(frappe.get_traceback())

		try:
			if self.account.gcalendar_id is not None:
				try:
					self.gcalendar.calendars().get(calendarId=self.account.gcalendar_id).execute()
				except Exception:
					frappe.log_error(frappe.get_traceback())
			else:
				_create_calendar()
		except HttpError as err:
			if err.resp.status in [403, 500, 503]:
				time.sleep(5)
			elif err.resp.status in [404]:
				_create_calendar()
			else: raise


	def get(self, remote_objectname, fields=None, filters=None, start=0, page_length=10):
		return self.get_events(remote_objectname, filters, page_length)

	def insert(self, doctype, doc):
		if doctype == 'Events':
			d = frappe.get_doc("Event", doc["name"])
			if has_permission(d, self.account.name):
				try:
					doctype = "Event"
					e = self.insert_events(doctype, doc)
					return e
				except Exception:
					frappe.log_error(frappe.get_traceback(), "GCalendar Synchronization Error")


	def update(self, doctype, doc, migration_id):
		if doctype == 'Events':
			d = frappe.get_doc("Event", doc["name"])
			if has_permission(d, self.account.name):
				if migration_id is not None:
					try:
						doctype = "Event"
						return self.update_events(doctype, doc, migration_id)
					except Exception:
						frappe.log_error(frappe.get_traceback(), "GCalendar Synchronization Error")

	def delete(self, doctype, migration_id):
		if doctype == 'Events':
			try:
				return self.delete_events(migration_id)
			except Exception:
				frappe.log_error(frappe.get_traceback(), "GCalendar Synchronization Error")

	def get_events(self, remote_objectname, filters, page_length):
		page_token = None
		results = []
		events = {"items": []}
		while True:
			try:
				events = self.gcalendar.events().list(calendarId=self.account.gcalendar_id, maxResults=page_length,
					singleEvents=False, showDeleted=True, syncToken=self.account.next_sync_token or None).execute()
			except HttpError as err:
				if err.resp.status in [410]:
					events = self.gcalendar.events().list(calendarId=self.account.gcalendar_id, maxResults=page_length,
						singleEvents=False, showDeleted=True, timeMin=add_years(None, -1).strftime('%Y-%m-%dT%H:%M:%SZ')).execute()
				else:
					frappe.log_error(err.resp, "GCalendar Events Fetch Error")
			for event in events['items']:
				event.update({'account': self.account.name})
				event.update({'calendar_tz': events['timeZone']})
				results.append(event)

			page_token = events.get('nextPageToken')
			if not page_token:
				if events.get('nextSyncToken'):
					frappe.db.set_value("GCalendar Account", self.connector.username, "next_sync_token", events.get('nextSyncToken'))
				break
		return list(results)

	def insert_events(self, doctype, doc, migration_id=None):
		event = {
			'summary': doc.summary,
			'description': doc.description
		}

		dates = self.return_dates(doc)
		event.update(dates)

		if migration_id:
			event.update({"id": migration_id})

		if doc.repeat_this_event != 0:
			recurrence = self.return_recurrence(doctype, doc)
			if not not recurrence:
				event.update({"recurrence": ["RRULE:" + str(recurrence)]})

		try:
			remote_event = self.gcalendar.events().insert(calendarId=self.account.gcalendar_id, body=event).execute()
			return {self.name_field: remote_event["id"]}
		except Exception:
			frappe.log_error(frappe.get_traceback(), "GCalendar Synchronization Error")

	def update_events(self, doctype, doc, migration_id):
		try:
			event = self.gcalendar.events().get(calendarId=self.account.gcalendar_id, eventId=migration_id).execute()
			event = {
				'summary': doc.summary,
				'description': doc.description
			}

			if doc.event_type == "Cancel":
				event.update({"status": "cancelled"})

			dates = self.return_dates(doc)
			event.update(dates)

			if doc.repeat_this_event != 0:
				recurrence = self.return_recurrence(doctype, doc)
				if recurrence:
					event.update({"recurrence": ["RRULE:" + str(recurrence)]})

			try:
				updated_event = self.gcalendar.events().update(calendarId=self.account.gcalendar_id, eventId=migration_id, body=event).execute()
				return {self.name_field: updated_event["id"]}
			except Exception as e:
				frappe.log_error(e, "GCalendar Synchronization Error")
		except HttpError as err:
			if err.resp.status in [404]:
				self.insert_events(doctype, doc, migration_id)
			else:
				frappe.log_error(err.resp, "GCalendar Synchronization Error")

	def delete_events(self, migration_id):
		try:
			self.gcalendar.events().delete(calendarId=self.account.gcalendar_id, eventId=migration_id).execute()
		except HttpError as err:
			if err.resp.status in [410]:
				pass

	def return_dates(self, doc):
		timezone = frappe.db.get_value("System Settings", None, "time_zone")
		if doc.end_datetime is None:
			doc.end_datetime = doc.start_datetime
		if doc.all_day == 1:
			return {
				'start': {
					'date': doc.start_datetime.date().isoformat(),
					'timeZone': timezone,
				},
				'end': {
					'date': add_days(doc.end_datetime.date(), 1).isoformat(),
					'timeZone': timezone,
				}
			}
		else:
			return {
				'start': {
					'dateTime': doc.start_datetime.isoformat(),
					'timeZone': timezone,
				},
				'end': {
					'dateTime': doc.end_datetime.isoformat(),
					'timeZone': timezone,
				}
			}

	def return_recurrence(self, doctype, doc):
		e = frappe.get_doc(doctype, doc.name)
		if e.repeat_till is not None:
			end_date = datetime.combine(e.repeat_till, datetime.min.time()).strftime('UNTIL=%Y%m%dT%H%M%SZ')
		else:
			end_date = None

		day = []
		if e.repeat_on == "Every Day":
			if e.monday == 1:
				day.append("MO")
			if e.tuesday == 1:
				day.append("TU")
			if e.wednesday == 1:
				day.append("WE")
			if e.thursday == 1:
				day.append("TH")
			if e.friday == 1:
				day.append("FR")
			if e.saturday == 1:
				day.append("SA")
			if e.sunday == 1:
				day.append("SU")

			day = "BYDAY=" + ",".join(str(d) for d in day)
			frequency = "FREQ=WEEKLY"

		elif e.repeat_on == "Every Week":
			frequency = "FREQ=WEEKLY"
		elif e.repeat_on == "Every Month":
			frequency = "FREQ=MONTHLY;BYDAY=SU,MO,TU,WE,TH,FR,SA;BYSETPOS=-1"
			end_date = datetime.combine(add_days(e.repeat_till, 1), datetime.min.time()).strftime('UNTIL=%Y%m%dT%H%M%SZ')
		elif e.repeat_on == "Every Year":
			frequency = "FREQ=YEARLY"
		else:
			return None

		wst = "WKST=SU"

		elements = [frequency, end_date, wst, day]

		return ";".join(str(e) for e in elements if e is not None and not not e)
