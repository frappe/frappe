# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
import googleapiclient.discovery
import google.oauth2.credentials
import time
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_request_site_address
from googleapiclient.errors import HttpError

SCOPES = "https://www.googleapis.com/auth/calendar/v3"

class GoogleCalendar(Document):

	def validate(self):
		if not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(_("Enable Google API in Google Settings."))

	def get_access_token(self):
		google_settings = frappe.get_doc("Google Settings")

		if not google_settings.enable:
			frappe.throw(_("Google Calendar Integration is disabled."))

		if not self.refresh_token:
			button_label = frappe.bold(_("Allow Google Calendar Access"))
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
			button_label = frappe.bold(_("Allow Google Calendar Access"))
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

@frappe.whitelist()
def sync(g_calendar=None):
	filters = {"enable": 1}

	if g_calendar:
		filters.update({"name": g_calendar})

	google_calendars = frappe.get_list("Google Calendar", filters=filters)

	for g in google_calendars:
		get_events(frappe.get_doc("Google Calendar", g.name))

def get_credentials(g_calendar):
	google_settings = frappe.get_doc("Google Settings")
	account = frappe.get_doc("Google Calendar", g_calendar)

	credentials_dict = {
		"token": account.get_access_token(),
		"refresh_token": account.refresh_token,
		"token_uri": "https://www.googleapis.com/oauth2/v4/token",
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		"scopes":"https://www.googleapis.com/auth/calendar"
	}

	credentials = google.oauth2.credentials.Credentials(**credentials_dict)
	google_calendar = googleapiclient.discovery.build("calendar", "v3", credentials=credentials)

	check_remote_calendar(account, google_calendar)

	return google_calendar, account

def check_remote_calendar(account, google_calendar):
	def _create_calendar():
		calendar = {
			"summary": account.calendar_name,
			"timeZone": frappe.db.get_value("System Settings", None, "time_zone")
		}
		try:
			created_calendar = google_calendar.calendars().insert(body=calendar).execute()
			frappe.db.set_value("Google Calendar", account.name, "google_calendar_id", created_calendar["id"])
			frappe.db.commit()
		except Exception:
			frappe.log_error(frappe.get_traceback())

	try:
		if not account.google_calendar_id:
			try:
				google_calendar.calendars().get(calendarId=account.google_calendar_id).execute()
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

def get_events(doc, method=None, page_length=10):
	"""
		Sync Events with Google Calendar
	"""
	google_calendar, account = get_credentials(doc.name)
	page_token = None
	results = []
	events = {
		"items": []
	}

	while True:
		try:
			events = google_calendar.events().list(calendarId=account.google_calendar_id, maxResults=page_length,
				singleEvents=False, showDeleted=True, syncToken=account.next_sync_token or None).execute()
		except HttpError as err:
			if err.resp.status in [410]:
				events = google_calendar.events().list(calendarId=account.google_calendar_id, maxResults=page_length,
					singleEvents=False, showDeleted=True, timeMin=add_years(None, -1).strftime("%Y-%m-%dT%H:%M:%SZ")).execute()
			else:
				frappe.log_error(err.resp, "Google Calendar Events Fetch Error.")

		for event in events["items"]:
			event.update({"account": account.name})
			event.update({"calendar_tz": events["timeZone"]})
			results.append(event)
			page_token = events.get("nextPageToken")

		if not page_token:
			if events.get("nextSyncToken"):
				frappe.db.set_value("Google Calendar", account.name, "next_sync_token", events.get("nextSyncToken"))
				frappe.db.commit()
			break

	for idx, event in enumerate(list(results)):
		frappe.publish_realtime('import_google_calendar', dict(progress=idx+1, total=len(list(results))), user=frappe.session.user)

		frappe.get_doc({
			"doctype": "Event",
			"description": event.get("description"),
			"start_datetime": event.get("start_on"),
			"end_datetime": event.get("ends_on"),
			"all_day": event.get("all_day"),
			"repeat_this_event": event.get("repeat_this_event"),
			"repeat_on": event.get("repeat_on"),
			"repeat_till": event.get("repeat_till"),
			"sunday": event.get("sunday"),
			"monday": event.get("monday"),
			"tuesday": event.get("tuesday"),
			"wednesday": event.get("wednesday"),
			"thursday": event.get("thursday"),
			"friday": event.get("friday"),
			"saturday": event.get("saturday"),
			"google_calendar_id": event.get("id")
		}).insert()

def insert_events(doc, method=None):
	"""
		Insert Events with Google Calendar
	"""
	google_calendar, account = get_credentials(doc.name)

	event = {
		"summary": doc.summary,
		"description": doc.description
	}

	dates = self.return_dates(doc)
	event.update(dates)

	if migration_id:
		event.update({"id": doc.name})

	if doc.repeat_this_event != 0:
		recurrence = self.return_recurrence(doctype, doc)
		if recurrence:
			event.update({"recurrence": ["RRULE:" + str(recurrence)]})

	try:
		remote_event = google_calendar.events().insert(calendarId=account.google_calendar_id, body=event).execute()
		return {self.name_field: remote_event["id"]}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("Google Calendar Synchronization Error."))

def update_events(doc, method=None):
	"""
		Update Events with Google Calendar
	"""
	google_calendar, account = get_credentials(doc.name)

	try:
		event = google_calendar.events().get(calendarId=account.google_calendar_id, eventId=doc.name).execute()
		event = {
			"summary": doc.summary,
			"description": doc.description
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
			updated_event = google_calendar.events().update(calendarId=account.google_calendar_id, eventId=doc.name, body=event).execute()
			return {self.name_field: updated_event["id"]}
		except Exception as e:
			frappe.log_error(e, "Google Calendar Synchronization Error.")
	except HttpError as err:
		if err.resp.status in [404]:
			self.insert_events(doctype, doc)
		else:
			frappe.log_error(err.resp, "Google Calendar Synchronization Error.")

def delete_events(doc, method=None):
	"""
		Delete Events with Google Calendar
	"""
	google_calendar, account = get_credentials(doc.name)

	try:
		google_calendar.events().delete(calendarId=account.google_calendar_id, eventId=doc.name).execute()
	except HttpError as err:
		if err.resp.status in [410]:
			pass

def return_dates(doc):
	timezone = frappe.db.get_single_value("System Settings", "time_zone")
	if not doc.end_datetime:
		doc.end_datetime = doc.start_datetime
	if doc.all_day == 1:
		return {
			"start": {
				"date": doc.start_datetime.date().isoformat(),
				"timeZone": timezone,
			},
			"end": {
				"date": add_days(doc.end_datetime.date(), 1).isoformat(),
				"timeZone": timezone,
			}
		}
	else:
		return {
			"start": {
				"dateTime": doc.start_datetime.isoformat(),
				"timeZone": timezone,
			},
			"end": {
				"dateTime": doc.end_datetime.isoformat(),
				"timeZone": timezone,
			}
		}

def return_recurrence(doc):
	e = frappe.get_doc("Event", doc.name)
	if not e.repeat_till:
		end_date = datetime.combine(e.repeat_till, datetime.min.time()).strftime("UNTIL=%Y%m%dT%H%M%SZ")
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
		end_date = datetime.combine(add_days(e.repeat_till, 1), datetime.min.time()).strftime("UNTIL=%Y%m%dT%H%M%SZ")
	elif e.repeat_on == "Every Year":
		frequency = "FREQ=YEARLY"
	else:
		return None

	wst = "WKST=SU"
	elements = [frequency, end_date, wst, day]

	return ";".join(str(e) for e in elements if e is not None and not not e)
