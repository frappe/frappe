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
from frappe.utils import add_days, add_years, get_datetime, get_weekdays, now_datetime, add_to_date, get_time_zone
from dateutil import parser
from datetime import datetime, timedelta

SCOPES = "https://www.googleapis.com/auth/calendar/v3"

google_calendar_frequencies = {
	"RRULE:FREQ=DAILY": "Daily",
	"RRULE:FREQ=WEEKLY": "Weekly",
	"RRULE:FREQ=MONTHLY": "Monthly",
	"RRULE:FREQ=YEARLY": "Yearly"
}

google_calendar_days = {
	"MO": "monday",
	"TU": "tuesday",
	"WE": "wednesday",
	"TH": "thursday",
	"FR": "friday",
	"SA": "saturday",
	"SU": "sunday"
}

framework_frequencies = {
	"Daily": "RRULE:FREQ=DAILY;",
	"Weekly": "RRULE:FREQ=WEEKLY;",
	"Monthly": "RRULE:FREQ=MONTHLY;",
	"Yearly": "RRULE:FREQ=YEARLY;"
}

framework_days = {
	"monday": "MO",
	"tuesday": "TU",
	"wednesday": "WE",
	"thursday": "TH",
	"friday": "FR",
	"saturday": "SA",
	"sunday": "SU"
}

class GoogleCalendar(Document):

	def validate(self):
		validate_google_settings()

		if frappe.db.exists("Google Calendar", {"user": self.user, "calendar_name": self.calendar_name}) and \
			not frappe.db.get_value("Google Calendar", {"user": self.user, "calendar_name": self.calendar_name}, "name") == self.name:
			frappe.throw(_("Google Calendar already exists for user {0} and name {1}").format(self.user, self.calendar_name))

	def get_access_token(self):
		google_settings = validate_google_settings()

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

def validate_google_settings():
	google_settings = frappe.get_single("Google Settings")
	if not google_settings.enable:
		frappe.throw(_("Enable Google API in Google Settings."))

	if not google_settings.client_id or not google_settings.client_secret:
		frappe.throw(_("Enter Client Id and Client Secret in Google Settings."))

	return google_settings

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
				"code": google_calendar.get_password(fieldname="authorization_code", raise_exception=False),
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
		google_calendar_get_events(g.name)

def get_credentials(g_calendar):
	google_settings = frappe.get_doc("Google Settings")
	account = frappe.get_doc("Google Calendar", g_calendar)

	credentials_dict = {
		"token": account.get_access_token(),
		"refresh_token": account.get_password(fieldname="refresh_token", raise_exception=False),
		"token_uri": "https://www.googleapis.com/oauth2/v4/token",
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		"scopes": SCOPES
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
		if err.resp.status in [403, 404, 410, 500, 503]:
			time.sleep(5)
			_create_calendar(account)
		else:
			frappe.log_error(frappe.get_traceback(), _("Google Calendar - Could not create Calendar for {0}.").format(account.name))

def google_calendar_get_events(g_calendar, method=None, page_length=10):
	# Get Events from Google Calendar
	def _insert_event(account, event, recurrence=None):
		calendar_event = {
			"doctype": "Event",
			"subject": event.get("summary"),
			"description": event.get("description"),
			"google_calendar_event": 1,
			"google_calendar_id": account.google_calendar_id,
			"google_calendar_event_id": event.get("id"),
			"synced_from_google_calendar": 1
		}
		calendar_event.update(google_calendar_to_repeat_on(recurrence=recurrence, start=event.get("start"), end=event.get("end")))
		frappe.get_doc(calendar_event).insert(ignore_permissions=True)

	def _update_event(account, event, recurrence=None):
		calendar_event = frappe.get_doc("Event", {"google_calendar_event_id": event.get("id")})
		calendar_event.subject = event.get("summary")
		calendar_event.description = event.get("description")
		calendar_event.update(google_calendar_to_repeat_on(recurrence=recurrence, start=event.get("start"), end=event.get("end")))
		calendar_event.save(ignore_permissions=True)

	google_calendar, account = get_credentials({"name": g_calendar})

	if not account.pull_from_google_calendar:
		return

	results = []
	while True:
		try:
			# API Response listed at EOF
			sync_token = account.get_password(fieldname="next_sync_token", raise_exception=False) or None
			events = google_calendar.events().list(calendarId=account.google_calendar_id, maxResults=page_length,
				singleEvents=False, showDeleted=True, syncToken=sync_token).execute()
		except HttpError as err:
			if err.resp.status in [400, 404, 410, 500, 503]:
				time.sleep(5)
				events = google_calendar.events().list(calendarId=account.google_calendar_id, maxResults=page_length,
					singleEvents=False, showDeleted=True, timeMin=add_years(None, -1).strftime("%Y-%m-%dT%H:%M:%SZ")).execute()
			else:
				frappe.throw(_("Google Calendar - Could not fetch event from Google Calendar."))

		for event in events.get("items"):
			results.append(event)

		if not events.get("nextPageToken"):
			if events.get("nextSyncToken"):
				frappe.db.set_value("Google Calendar", account.name, "next_sync_token", events.get("nextSyncToken"))
				frappe.db.commit()
			break

	for idx, event in enumerate(results):
		frappe.publish_realtime("import_google_calendar", dict(progress=idx+1, total=len(results)), user=frappe.session.user)

		# If Google Calendar Event if confirmed, then create an Event
		if event.get("status") == "confirmed":
			recurrence = None
			if event.get("recurrence"):
				try:
					recurrence = event.get("recurrence")[0]
				except IndexError:
					pass

			if not frappe.db.exists("Event", {"google_calendar_event_id": event.get("id")}):
				_insert_event(account, event, recurrence)
			else:
				_update_event(account, event, recurrence)
		elif event.get("status") == "cancelled":
			# If any synced Google Calendar Event is cancelled, then close the Event
			frappe.db.set_value("Event", {"google_calendar_id": account.google_calendar_id, "google_calendar_event_id": event.get("id")}, "status", "Closed")
		else:
			pass

def google_calendar_insert_events(doc, method=None):
	# Insert Events to Google Calendar

	def _google_calendar_insert_events(google_calendar, account, event, doc):
		event = google_calendar.events().insert(calendarId=account.google_calendar_id, body=event).execute()
		frappe.db.set_value("Event", doc.name, "google_calendar_event", 1, update_modified=False)
		frappe.db.set_value("Event", doc.name, "google_calendar_id", account.google_calendar_id, update_modified=False)
		frappe.db.set_value("Event", doc.name, "google_calendar_event_id", event.get("id"), update_modified=False)

	if not frappe.db.exists("Google Calendar", {"user": doc.owner or frappe.session.user}) or doc.synced_from_google_calendar:
		return

	google_calendar, account = get_credentials({"user": doc.owner or frappe.session.user})

	if not account.push_to_google_calendar:
		return

	event = {
		"summary": doc.subject,
		"description": doc.description,
		"google_calendar_event": 1
	}
	event.update(google_calendar_format_date(doc.all_day, get_datetime(doc.starts_on), get_datetime(doc.ends_on)))

	if doc.repeat_on:
		event.update({"recurrence": unparse_recurrence(doc)})

	try:
		_google_calendar_insert_events(google_calendar, account, event, doc)
	except HttpError as err:
		if err.resp.status in [400, 404, 410, 500, 503]:
			time.sleep(2)
			_google_calendar_insert_events(google_calendar, account, event, doc)
		else:
			frappe.throw(_("Google Calendar - Could not insert event in Google Calendar {0}."),format(account.name))


def google_calendar_update_events(doc, method=None):
	# Update Events with Google Calendar

	def _google_calendar_update_events(google_calendar, account, doc):
		event = google_calendar.events().get(calendarId=account.google_calendar_id, eventId=doc.google_calendar_event_id).execute()
		event["summary"] = doc.subject
		event["description"] = doc.description
		event["recurrence"] = unparse_recurrence(doc)
		event.update(google_calendar_format_date(doc.all_day, get_datetime(doc.starts_on), get_datetime(doc.ends_on)))

		if doc.event_type == "Cancelled" or doc.status == "Closed":
			event["status"] = "cancelled"

		google_calendar.events().update(calendarId=account.google_calendar_id, eventId=doc.google_calendar_event_id, body=event).execute()

	# Workaround to avoid triggering updation when Event is being inserted since
	# creation and modified are same when inserting doc
	if not frappe.db.exists("Google Calendar", {"user": doc.owner or frappe.session.user}) or doc.modified == doc.creation:
		return

	google_calendar, account = get_credentials({"user": doc.owner or frappe.session.user})

	if not account.push_to_google_calendar:
		return

	try:
		_google_calendar_update_events(google_calendar, account, doc)
	except HttpError as err:
		if err.resp.status in [400, 404, 410, 500, 503]:
			time.sleep(2)
			_google_calendar_update_events(google_calendar, account, doc)
		else:
			frappe.throw(_("Google Calendar - Could not update Event {0} in Google Calendar.").format(doc.name))

def google_calendar_delete_events(doc, method=None):
	# Delete Events from Google Calendar

	def _google_calendar_delete_events(google_calendar, account, doc):
		event = google_calendar.events().get(calendarId=account.google_calendar_id, eventId=doc.google_calendar_event_id).execute()
		event["recurrence"] = None
		event["status"] = "cancelled"
		google_calendar.events().update(calendarId=account.google_calendar_id, eventId=doc.google_calendar_event_id, body=event).execute()

	if not frappe.db.exists("Google Calendar", {"user": doc.owner or frappe.session.user}):
		return

	google_calendar, account = get_credentials({"user": doc.owner or frappe.session.user})

	if not account.push_to_google_calendar:
		return

	try:
		_google_calendar_delete_events(google_calendar, account, doc)
	except HttpError as err:
		if err.resp.status in [400, 404, 410, 500, 503]:
			time.sleep(2)
			_google_calendar_delete_events(google_calendar, account, doc)
		else:
			frappe.throw(_("Google Calendar - Could not delete Event {0} from Google Calendar.").format(doc.name))

def google_calendar_to_repeat_on(start, end, recurrence=None):
	"""
		recurrence is in the form ['RRULE:FREQ=WEEKLY;BYDAY=MO,TU,TH']
		has the frequency and then the days on which the event recurs

		Both have been mapped in a dict for easier mapping.
	"""
	repeat_on = {
		"starts_on": get_datetime(start.get("date")) if start.get("date") else parser.parse(start.get("dateTime")).utcnow(),
		"ends_on": get_datetime(end.get("date")) if end.get("date") else parser.parse(end.get("dateTime")).utcnow(),
		"all_day": 1 if start.get("date") else 0,
		"repeat_this_event": 1 if recurrence else 0,
		"repeat_on": None,
		"repeat_till": None,
		"sunday": 0,
		"monday": 0,
		"tuesday": 0,
		"wednesday": 0,
		"thursday": 0,
		"friday": 0,
		"saturday": 0,
	}

	# recurrence rule "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,TH"
	if recurrence:
		# google_calendar_frequency = RRULE:FREQ=WEEKLY, byday = BYDAY=MO,TU,TH, until = 20191028
		google_calendar_frequency, until, byday = get_recurrence_parameter(recurrence)
		repeat_on["repeat_on"] = google_calendar_frequencies.get(google_calendar_frequency)

		if repeat_on["repeat_on"] == "Daily":
			repeat_on["ends_on"] = None
			repeat_on["repeat_till"] = datetime.strptime(until, "%Y%m%d") if until else None

		if byday and repeat_on["repeat_on"] == "Weekly":
			repeat_on["repeat_till"] = datetime.strptime(until, "%Y%m%d") if until else None
			byday = byday.split("=")[1].split(",")
			for repeat_day in byday:
				repeat_on[google_calendar_days[repeat_day]] = 1

		if byday and repeat_on["repeat_on"] == "Monthly":
			byday = byday.split("=")[1]
			repeat_day_week_number, repeat_day_name = None, None

			for num in ["-2", "-1", "1", "2", "3", "4", "5"]:
				if num in byday:
					repeat_day_week_number = num
					break

			for day in ["MO","TU","WE","TH","FR","SA","SU"]:
				if day in byday:
					repeat_day_name = google_calendar_days.get(day)
					break

			# Only Set starts_on for the event to repeat monthly
			start_date = parse_recurrence(int(repeat_day_week_number), repeat_day_name)
			repeat_on["starts_on"] = start_date
			repeat_on["ends_on"] = add_to_date(start_date, minutes=5)
			repeat_on["repeat_till"] = datetime.strptime(until, "%Y%m%d") if until else None

		if repeat_on["repeat_till"] == "Yearly":
			repeat_on["ends_on"] = None
			repeat_on["repeat_till"] = datetime.strptime(until, "%Y%m%d") if until else None

	return repeat_on

def google_calendar_format_date(all_day, starts_on, ends_on=None):
	if not ends_on:
		ends_on = starts_on + timedelta(minutes=10)

	date_format = {
		"start": {
			"dateTime": starts_on.isoformat(),
			"timeZone": get_time_zone(),
			},
		"end": {
			"dateTime": ends_on.isoformat(),
			"timeZone": get_time_zone(),
		}
	}

	if all_day:
		# If all_day event, Google Calendar takes date as a parameter and not dateTime
		date_format["start"].pop("dateTime")
		date_format["end"].pop("dateTime")

		date_format["start"].update({"date": starts_on.date().isoformat()})
		date_format["end"].update({"date": ends_on.date().isoformat()})

	return date_format

def parse_recurrence(repeat_day_week_number, repeat_day_name):
	# Returns (repeat_on) exact date for combination eg 4TH viz. 4th thursday of a month

	if repeat_day_week_number < 0:
		# Consider a month with 5 weeks and event is to be repeated in last week of every month, google caledar considers
		# a month has 4 weeks and hence itll return -1 for a month with 5 weeks.
		repeat_day_week_number = 4

	weekdays = get_weekdays()
	current_date = now_datetime()
	isset_day_name, isset_day_number = False, False

	# Set the proper day ie if recurrence is 4TH, then align the day to Thursday
	while not isset_day_name:
		isset_day_name = True if weekdays[current_date.weekday()].lower() == repeat_day_name else False
		current_date = add_days(current_date, 1) if not isset_day_name else current_date

	# One the day is set to Thursday, now set the week number ie 4
	while not isset_day_number:
		week_number = get_week_number(current_date)
		isset_day_number = True if week_number == repeat_day_week_number else False
		# check if  current_date week number is greater or smaller than repeat_day week number
		weeks = 1 if week_number < repeat_day_week_number else -1
		current_date = add_to_date(current_date, weeks=weeks) if not isset_day_number else current_date

	return current_date

def unparse_recurrence(doc):
	# Returns recurrence in Google Calendar format
	recurrence = framework_frequencies.get(doc.repeat_on)
	weekdays = get_weekdays()

	if doc.repeat_on == "Weekly":
		byday = [framework_days.get(day.lower()) for day in weekdays if doc.get(day.lower())]
		recurrence = recurrence + "BYDAY=" + ",".join(byday)
	elif doc.repeat_on == "Monthly":
		week_number = str(get_week_number(get_datetime(doc.starts_on)))
		week_day = weekdays[get_datetime(doc.starts_on).weekday()].lower()
		recurrence = recurrence + "BYDAY=" + week_number + framework_days.get(week_day)

	return [recurrence]

def get_week_number(dt):
	"""
		Returns the week number of the month for the specified date.
		https://stackoverflow.com/questions/3806473/python-week-number-of-the-month/16804556
	"""
	from math import ceil
	first_day = dt.replace(day=1)

	dom = dt.day
	adjusted_dom = dom + first_day.weekday()

	return int(ceil(adjusted_dom/7.0))

def get_recurrence_parameter(recurrence):
	recurrence = recurrence.split(";")
	frequency, until, byday = None, None, None

	for r in recurrence:
		if "RRULE:FREQ" in r:
			frequency = r
		elif "UNTIL" in r:
			until = r
		elif "BYDAY" in r:
			byday = r
		else:
			pass

	return frequency, until, byday

"""API Response
	{
		'kind': 'calendar#events',
		'etag': '"etag"',
		'summary': 'Test Calendar',
		'updated': '2019-07-25T06:09:34.681Z',
		'timeZone': 'Asia/Kolkata',
		'accessRole': 'owner',
		'defaultReminders': [],
		'nextSyncToken': 'token',
		'items': [
			{
				'kind': 'calendar#event',
				'etag': '"etag"',
				'id': 'id',
				'status': 'confirmed' or 'cancelled',
				'htmlLink': 'link',
				'created': '2019-07-25T06:08:21.000Z',
				'updated': '2019-07-25T06:09:34.681Z',
				'summary': 'asdf',
				'creator': {
					'email': 'email'
				},
				'organizer': {
					'email': 'email',
					'displayName': 'Test Calendar',
					'self': True
				},
				'start': {
					'dateTime': '2019-07-27T12:00:00+05:30', (if all day event the its 'date' instead of 'dateTime')
					'timeZone': 'Asia/Kolkata'
				},
				'end': {
					'dateTime': '2019-07-27T13:00:00+05:30', (if all day event the its 'date' instead of 'dateTime')
					'timeZone': 'Asia/Kolkata'
				},
				'recurrence': *recurrence,
				'iCalUID': 'uid',
				'sequence': 1,
				'reminders': {
					'useDefault': True
				}
			}
		]
	}
	*recurrence
		- Daily Event: ['RRULE:FREQ=DAILY']
		- Weekly Event: ['RRULE:FREQ=WEEKLY;BYDAY=MO,TU,TH']
		- Monthly Event: ['RRULE:FREQ=MONTHLY;BYDAY=4TH']
			- BYDAY: -2, -1, 1, 2, 3, 4 with weekdays (-2 edge case for April 2017 had 6 weeks in a month)
		- Yearly Event: ['RRULE:FREQ=YEARLY;']
		- Custom Event: ['RRULE:FREQ=WEEKLY;WKST=SU;UNTIL=20191028;BYDAY=MO,WE']"""