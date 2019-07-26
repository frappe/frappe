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
from frappe.utils import add_days, add_years

SCOPES = "https://www.googleapis.com/auth/calendar/v3"

class GoogleCalendar(Document):

	def validate_google_settings(self):
		google_settings = frappe.get_single("Google Settings")
		if not google_settings.enable:
			frappe.throw(_("Enable Google API in Google Settings."))

		if not google_settings.client_id or not google_settings.client_secret:
			frappe.throw(_("Enter Client Id and Client Secret in Google Settings."))

		return google_settings

	def validate(self):
		self.validate_google_settings()

		if frappe.db.exists("Google Calendar", {"user": self.user, "calendar_name": self.calendar_name}) and \
			not frappe.db.get_value("Google Calendar", {"user": self.user, "calendar_name": self.calendar_name}, "name") == self.name:
			frappe.throw(_("Google Calendar already exists for user {0} and name {1}").format(self.user, self.calendar_name))

	def get_access_token(self):
		google_settings = self.validate_google_settings()

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

	account.load_from_db()
	return google_calendar, account

def check_remote_calendar(account, google_calendar):
	def _create_calendar(account):
		calendar = {
			"summary": account.calendar_name,
			"timeZone": frappe.db.get_single_value("System Settings", "time_zone")
		}
		try:
			created_calendar = google_calendar.calendars().insert(body=calendar).execute()
			frappe.db.set_value("Google Calendar", account.name, "google_calendar_id", created_calendar.get("id"))
			frappe.db.commit()
		except Exception:
			frappe.log_error(frappe.get_traceback())

	try:
		if account.google_calendar_id:
			try:
				account.load_from_db()
				google_calendar.calendars().get(calendarId=account.google_calendar_id).execute()
			except Exception:
				frappe.log_error(frappe.get_traceback())
		else:
			_create_calendar(account)
	except HttpError as err:
		if err.resp.status in [403, 404, 500, 503]:
			time.sleep(5)
			_create_calendar(account)
		else:
			frappe.log_error(frappe.get_traceback(), _("Google Calendar Synchronization Error."))


def get_events(doc, method=None, page_length=10):
	"""
		Sync Events with Google Calendar
	"""
	if not doc.pull_from_google_calendar:
		return

	google_calendar, account = get_credentials(doc.name)
	page_token = None
	results = []

	print("1")
	while True:
		try:
			"""
				API Response
				{
					'kind': 'calendar#events',
					'etag': '"etag"',
					'summary': 'Test Calendar',
					'updated': '2019-07-24T17:46:24.366Z',
					'timeZone': 'Asia/Kolkata',
					'accessRole': 'owner',
					'defaultReminders': [],
					'nextSyncToken': 'nextSyncToken',
					'items': [
						{
							'kind': 'calendar#event',
							'etag': '"etag"',
							'id': 'id',
							'status': 'confirmed',
							'htmlLink': 'https://www.google.com/calendar/event?eid=eid',
							'created': '2019-07-24T17:46:24.000Z',
							'updated': '2019-07-24T17:46:24.366Z',
							'summary': 'qusk',
							'creator': {
								'email': 'himanshu@iwebnotes.com'
							},
							'organizer': {
								'email': 'calendar_id',
								'displayName': 'Test Calendar',
								'self': True
							},
							'start': {
								'dateTime': '2019-07-26T20:00:00+05:30'
							},
							'end': {
								'dateTime': '2019-07-26T21:00:00+05:30'
							},
							'iCalUID': 'UID',
							'sequence': 0,
							'recurrence': ['RRULE:FREQ=DAILY'],
							'reminders': {
								'useDefault': True
							}
						}
					]
				}
			"""
			events = google_calendar.events().list(calendarId=account.google_calendar_id, maxResults=page_length,
				singleEvents=False, showDeleted=True, syncToken=account.next_sync_token or None).execute()
			print("2")
			print(events)
		except HttpError as err:
			if err.resp.status in [404, 410]:
				events = google_calendar.events().list(calendarId=account.google_calendar_id, maxResults=page_length,
					singleEvents=False, showDeleted=True, timeMin=add_years(None, -1).strftime("%Y-%m-%dT%H:%M:%SZ")).execute()
				print("3")
				print(events)
			else:
				frappe.log_error(err.resp, "Google Calendar Events Fetch Error.")

		for event in events.get("items"):
			results.append(event)

		if not events.get("nextPageToken"):
			if events.get("nextSyncToken"):
				frappe.db.set_value("Google Calendar", account.name, "next_sync_token", events.get("nextSyncToken"))
				frappe.db.commit()
			break

	print(results)
	for idx, event in enumerate(results):
		frappe.publish_realtime('import_google_calendar', dict(progress=idx+1, total=len(list(results))), user=frappe.session.user)
		return_recurrence(event.get("recurrence"))
		# if not frappe.db.exists("Event", {"subject": event.get("summary")}):
		# 	frappe.get_doc({
		# 		"doctype": "Event",
		# 		"subject": event.get("summary"),
		# 		"description": event.get("description"),
		# 		"start_on": event.get("start").get("dateTime"),
		# 		"ends_on": event.get("end").get("dateTime"),
		# 		"all_day": event.get("all_day"),
		# 		"repeat_this_event": event.get("repeat_this_event"),
		# 		"repeat_on": event.get("repeat_on"),
		# 		"repeat_till": event.get("repeat_till"),
		# 		"sunday": event.get("sunday"),
		# 		"monday": event.get("monday"),
		# 		"tuesday": event.get("tuesday"),
		# 		"wednesday": event.get("wednesday"),
		# 		"thursday": event.get("thursday"),
		# 		"friday": event.get("friday"),
		# 		"saturday": event.get("saturday"),
		# 		"google_calendar_id": account.google_calendar_id,
		# 		"google_event_id": event.get("id"),
		# 	}).insert(ignore_permissions=True)

def insert_events(doc, method=None):
	"""
		Insert Events with Google Calendar
	"""
	if not doc.push_to_google_calendar:
		return

	google_calendar, account = get_credentials(doc.name)

	event = {
		"summary": doc.summary,
		"description": doc.description
	}

	dates = return_dates(doc)
	event.update(dates)

	if migration_id:
		event.update({"id": doc.name})

	if doc.repeat_this_event != 0:
		recurrence = return_recurrence(doc)
		if recurrence:
			event.update({"recurrence": ["RRULE:" + str(recurrence)]})

	try:
		remote_event = google_calendar.events().insert(calendarId=account.google_calendar_id, body=event).execute()
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

		dates = return_dates(doc)
		event.update(dates)

		if doc.repeat_this_event != 0:
			recurrence = return_recurrence(doc)
			if recurrence:
				event.update({"recurrence": ["RRULE:" + str(recurrence)]})

		try:
			updated_event = google_calendar.events().update(calendarId=account.google_calendar_id, eventId=doc.name, body=event).execute()
		except Exception as e:
			frappe.log_error(e, "Google Calendar Synchronization Error.")
	except HttpError as err:
		if err.resp.status in [404]:
			pass
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

def return_recurrence_for_google_calendar(recurrence):
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

def parse_recurrence(recureence):
	pass


"""
	- Recurrence Daily
	{
		'kind': 'calendar#events',
		'etag': '"p32k8vl58mj7u60g"',
		'summary': 'Test Calendar',
		'updated': '2019-07-25T06:09:34.681Z',
		'timeZone': 'Asia/Kolkata',
		'accessRole': 'owner',
		'defaultReminders': [],
		'nextSyncToken': 'CKiP1Ki0z-MCEKiP1Ki0z-MCGAU=',
		'items': [
			{
				'kind': 'calendar#event',
				'etag': '"3128069949362000"',
				'id': '6okmku7u8o4itknb7l1alu94ns',
				'status': 'confirmed',
				'htmlLink': 'https://www.google.com/calendar/event?eid=Nm9rbWt1N3U4bzRpdGtuYjdsMWFsdTk0bnNfMjAxOTA3MjdUMDYzMDAwWiBpd2Vibm90ZXMuY29tX2hqODFkZDA4aHJwaWNsbWY0anI3OWJzNG44QGc',
				'created': '2019-07-25T06:08:21.000Z',
				'updated': '2019-07-25T06:09:34.681Z',
				'summary': 'asdf',
				'creator': {
					'email': 'himanshu@iwebnotes.com'
				},
				'organizer': {
					'email': 'iwebnotes.com_hj81dd08hrpiclmf4jr79bs4n8@group.calendar.google.com',
					'displayName': 'Test Calendar',
					'self': True
				},
				'start': {
					'dateTime': '2019-07-27T12:00:00+05:30',
					'timeZone': 'Asia/Kolkata'
				},
				'end': {
					'dateTime': '2019-07-27T13:00:00+05:30',
					'timeZone': 'Asia/Kolkata'
				},
				'recurrence': ['RRULE:FREQ=DAILY'],
				'iCalUID': '6okmku7u8o4itknb7l1alu94ns@google.com',
				'sequence': 1,
				'reminders': {
					'useDefault': True
				}
			}
		]
	}
	- Recurrence Weekly
	{
		'kind': 'calendar#events',
		'etag': '"p320afgm8nv7u60g"',
		'summary': 'Test Calendar',
		'updated': '2019-07-25T06:59:54.288Z',
		'timeZone': 'Asia/Kolkata',
		'accessRole': 'owner',
		'defaultReminders': [],
		'nextSyncToken': 'CICnwsi_z-MCEICnwsi_z-MCGAU=',
		'items': [
			{
				'kind': 'calendar#event',
				'etag': '"3128075988576000"',
				'id': '33n5br0htu51suqih4k8990181',
				'status': 'confirmed',
				'htmlLink': 'https://www.google.com/calendar/event?eid=MzNuNWJyMGh0dTUxc3VxaWg0azg5OTAxODFfMjAxOTA3MjVUMTIzMDAwWiBpd2Vibm90ZXMuY29tX25mOHAyaTFnazU5NDI2dTBsNzA4amU0OWVjQGc',
				'created': '2019-07-25T06:59:47.000Z',
				'updated': '2019-07-25T06:59:54.288Z',
				'summary': 'Event',
				'creator': {
					'email': 'himanshu@iwebnotes.com'
				},
				'organizer': {
					'email': 'iwebnotes.com_nf8p2i1gk59426u0l708je49ec@group.calendar.google.com',
					'displayName': 'Test Calendar',
					'self': True
				},
				'start': {
					'dateTime': '2019-07-25T18:00:00+05:30',
					'timeZone': 'Asia/Kolkata'
				},
				'end': {
					'dateTime': '2019-07-25T19:00:00+05:30',
					'timeZone': 'Asia/Kolkata'
				},
				'recurrence': ['RRULE:FREQ=WEEKLY;BYDAY=TH'],
				'iCalUID': '33n5br0htu51suqih4k8990181@google.com',
				'sequence': 1,
				'reminders': {
					'useDefault': True
				}
			}
		]
	}
	- Recurrence Monthly on a Day
	{
		'kind': 'calendar#events',
		'etag': '"p32oajev9ob7u60g"',
		'summary': 'Test Calendar',
		'updated': '2019-07-25T07:14:28.686Z',
		'timeZone': 'Asia/Kolkata',
		'accessRole': 'owner',
		'defaultReminders': [],
		'nextSyncToken': 'CLCpu-nCz-MCELCpu-nCz-MCGAU=',
		'items': [
			{
				'kind': 'calendar#event',
				'etag': '"3128077737372000"',
				'id': '4up16101ptr37i5594asp0e692',
				'status': 'confirmed',
				'htmlLink': 'https://www.google.com/calendar/event?eid=NHVwMTYxMDFwdHIzN2k1NTk0YXNwMGU2OTJfMjAxOTA3MjVUMTMzMDAwWiBpd2Vibm90ZXMuY29tX25mOHAyaTFnazU5NDI2dTBsNzA4amU0OWVjQGc',
				'created': '2019-07-25T07:14:08.000Z',
				'updated': '2019-07-25T07:14:28.686Z',
				'summary': 'monthly 4 thusday',
				'creator': {
					'email': 'himanshu@iwebnotes.com'
				},
				'organizer': {
					'email': 'iwebnotes.com_nf8p2i1gk59426u0l708je49ec@group.calendar.google.com',
					'displayName': 'Test Calendar',
					'self': True
				},
				'start': {
					'dateTime': '2019-07-25T19:00:00+05:30',
					'timeZone': 'Asia/Kolkata'
				},
				'end': {
					'dateTime': '2019-07-25T20:00:00+05:30',
					'timeZone': 'Asia/Kolkata'
				},
				'recurrence': ['RRULE:FREQ=MONTHLY;BYDAY=4TH'],
				'iCalUID': '4up16101ptr37i5594asp0e692@google.com',
				'sequence': 1,
				'reminders': {
					'useDefault': True
				}
			}
		]
	}
"""