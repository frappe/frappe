# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE


from contextlib import suppress
from datetime import date, datetime, timedelta
from math import ceil
from typing import TYPE_CHECKING, TypedDict
from zoneinfo import ZoneInfo

import google.oauth2.credentials
import requests
from dateutil import parser
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import frappe
from frappe import _, _lt
from frappe.integrations.google_oauth import GoogleOAuth
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	add_to_date,
	get_datetime,
	get_request_site_address,
	get_system_timezone,
	get_weekdays,
	now_datetime,
)
from frappe.utils.password import set_encrypted_password

if TYPE_CHECKING:
	from frappe.desk.doctype.event.event import Event


class RecurrenceParameters(TypedDict):
	frequency: str | None
	until: datetime | None
	byday: list[str]


SCOPES = "https://www.googleapis.com/auth/calendar"

google_calendar_frequencies = {
	"RRULE:FREQ=DAILY": "Daily",
	"RRULE:FREQ=WEEKLY": "Weekly",
	"RRULE:FREQ=MONTHLY": "Monthly",
	"RRULE:FREQ=YEARLY": "Yearly",
}

google_calendar_days = {
	"MO": "monday",
	"TU": "tuesday",
	"WE": "wednesday",
	"TH": "thursday",
	"FR": "friday",
	"SA": "saturday",
	"SU": "sunday",
}

framework_frequencies = {
	"Daily": "RRULE:FREQ=DAILY;",
	"Weekly": "RRULE:FREQ=WEEKLY;",
	"Monthly": "RRULE:FREQ=MONTHLY;",
	"Yearly": "RRULE:FREQ=YEARLY;",
}

framework_days = {
	"monday": "MO",
	"tuesday": "TU",
	"wednesday": "WE",
	"thursday": "TH",
	"friday": "FR",
	"saturday": "SA",
	"sunday": "SU",
}


allow_google_calendar_label = _lt("Allow Google Calendar Access")


class GoogleCalendar(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		authorization_code: DF.Password | None
		calendar_name: DF.Data
		enable: DF.Check
		google_calendar_id: DF.Data | None
		next_sync_token: DF.Password | None
		pull_from_google_calendar: DF.Check
		sync_as_public: DF.Check
		push_to_google_calendar: DF.Check
		refresh_token: DF.Password | None
		user: DF.Link
	# end: auto-generated types

	def validate(self):
		google_settings = frappe.get_cached_doc("Google Settings")
		if not google_settings.enable:
			frappe.throw(_("Enable Google API in Google Settings."))

		if not google_settings.client_id or not google_settings.client_secret:
			frappe.throw(_("Enter Client Id and Client Secret in Google Settings."))

		return google_settings

	def get_access_token(self):
		google_settings = self.validate()

		if not self.refresh_token:
			raise frappe.ValidationError(
				_("Click on {0} to generate Refresh Token.").format(frappe.bold(allow_google_calendar_label))
			)

		data = {
			"client_id": google_settings.client_id,
			"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
			"refresh_token": self.get_password(fieldname="refresh_token", raise_exception=False),
			"grant_type": "refresh_token",
			"scope": SCOPES,
		}

		try:
			r = requests.post(GoogleOAuth.OAUTH_URL, data=data).json()
		except requests.exceptions.HTTPError:
			frappe.throw(
				_(
					"Something went wrong during the token generation. Click on {0} to generate a new one."
				).format(frappe.bold(allow_google_calendar_label))
			)

		return r.get("access_token")


@frappe.whitelist()
def authorize_access(g_calendar: str, reauthorize: bool = False):
	"""
	If no Authorization code get it from Google and then request for Refresh Token.
	Google Calendar Name is set to flags to set_value after Authorization Code is obtained.
	"""
	google_calendar = frappe.get_doc("Google Calendar", g_calendar)
	google_calendar.check_permission("write")

	google_settings = frappe.get_cached_doc("Google Settings")

	redirect_uri = (
		f"{get_request_site_address(full_address=True)}"
		f"?cmd={google_callback.__module__}.{google_callback.__qualname__}"
	)

	if not google_calendar.authorization_code or reauthorize:
		frappe.cache.hset("google_calendar", "google_calendar", google_calendar.name)
		return get_authentication_url(client_id=google_settings.client_id, redirect_uri=redirect_uri)

	data = {
		"code": google_calendar.get_password(fieldname="authorization_code", raise_exception=False),
		"client_id": google_settings.client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
		"redirect_uri": redirect_uri,
		"grant_type": "authorization_code",
	}

	try:
		r = requests.post(GoogleOAuth.OAUTH_URL, data=data).json()
	except Exception as e:
		frappe.throw(e)

	if "refresh_token" in r:
		frappe.db.set_value("Google Calendar", google_calendar.name, "refresh_token", r["refresh_token"])
		frappe.db.commit()

	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = google_calendar.get_url()

	frappe.msgprint(_("Google Calendar has been configured."), indicator="green")


def get_authentication_url(client_id=None, redirect_uri=None):
	return {
		"url": (
			"https://accounts.google.com/o/oauth2/v2/auth?"
			f"access_type=offline&response_type=code&prompt=consent&client_id={client_id}"
			f"&include_granted_scopes=true&scope={SCOPES}&redirect_uri={redirect_uri}"
		)
	}


@frappe.whitelist()
def google_callback(code=None):
	"""
	Authorization code is sent to callback as per the API configuration
	"""
	google_calendar = frappe.cache.hget("google_calendar", "google_calendar")
	frappe.db.set_value("Google Calendar", google_calendar, "authorization_code", code)
	frappe.db.commit()

	authorize_access(google_calendar)


@frappe.whitelist()
def sync(g_calendar: str | None = None):
	filters = {"enable": 1, "pull_from_google_calendar": 1}
	user_messages = []

	if g_calendar:
		filters.update({"name": g_calendar})

	for g in frappe.get_list("Google Calendar", filters=filters, pluck="name"):
		user_messages.append(sync_events_from_google_calendar(g))

	return user_messages


def get_google_calendar_object(g_calendar):
	"""Return an object of Google Calendar along with Google Calendar doc."""
	google_settings = frappe.get_cached_doc("Google Settings")
	account: GoogleCalendar = frappe.get_doc("Google Calendar", g_calendar)

	credentials = google.oauth2.credentials.Credentials(
		token=account.get_access_token(),
		refresh_token=account.get_password(fieldname="refresh_token", raise_exception=False),
		token_uri=GoogleOAuth.OAUTH_URL,
		client_id=google_settings.client_id,
		client_secret=google_settings.get_password(fieldname="client_secret", raise_exception=False),
		scopes=[SCOPES],
	)
	google_calendar = build(
		serviceName="calendar", version="v3", credentials=credentials, static_discovery=False
	)

	check_google_calendar(account.reload(), google_calendar)

	return google_calendar, account.reload()


def check_google_calendar(account: GoogleCalendar, google_calendar):
	"""
	Checks if Google Calendar is present with the specified name.
	If not, creates one.
	"""
	if account.google_calendar_id:
		try:
			return google_calendar.calendars().get(calendarId=account.google_calendar_id).execute()
		except HttpError as err:
			frappe.throw(
				_("Google Calendar - Could not find Calendar for {0}, error code {1}.").format(
					account.name, err.resp.status
				)
			)

	# If no Calendar ID create a new Calendar
	calendar = {
		"summary": account.calendar_name,
		"timeZone": frappe.get_system_settings("time_zone"),
	}
	try:
		created_calendar = google_calendar.calendars().insert(body=calendar).execute()
	except HttpError as err:
		frappe.throw(
			_("Google Calendar - Could not create Calendar for {0}, error code {1}.").format(
				account.name, err.resp.status
			)
		)
	account.db_set("google_calendar_id", created_calendar.get("id"))
	frappe.db.commit()


def sync_events_from_google_calendar(g_calendar, method=None):
	"""Sync Events from Google Calendar in Framework Calendar.

	Google Calendar returns nextSyncToken when all the events in Google Calendar are fetched.
	nextSyncToken is returned at the very last page
	https://developers.google.com/calendar/v3/sync
	"""
	google_calendar, account = get_google_calendar_object(g_calendar)

	if not account.pull_from_google_calendar:
		return

	sync_token = account.get_password(fieldname="next_sync_token", raise_exception=False) or None
	events = frappe._dict()
	results = []
	while True:
		try:
			# API Response listed at EOF
			events = (
				google_calendar.events()
				.list(
					calendarId=account.google_calendar_id,
					maxResults=2000,
					pageToken=events.get("nextPageToken"),
					singleEvents=False,
					showDeleted=True,
					syncToken=sync_token,
				)
				.execute()
			)
		except HttpError as err:
			msg = _("Google Calendar - Could not fetch event from Google Calendar, error code {0}.").format(
				err.resp.status
			)

			if err.resp.status == 410:
				set_encrypted_password("Google Calendar", account.name, "", "next_sync_token")
				frappe.db.commit()
				msg += " " + _("Sync token was invalid and has been reset, Retry syncing.")
				frappe.msgprint(msg, title="Invalid Sync Token", indicator="blue")
			else:
				frappe.throw(msg)

		results.extend(event for event in events.get("items", []))
		if not events.get("nextPageToken"):
			if events.get("nextSyncToken"):
				account.next_sync_token = events.get("nextSyncToken")
				account.save()
			break

	for idx, event in enumerate(results):
		frappe.publish_realtime(
			"import_google_calendar", {"progress": idx + 1, "total": len(results)}, user=frappe.session.user
		)

		# If Google Calendar Event if confirmed, then create an Event
		if event.get("status") == "confirmed":
			recurrence = None
			if event.get("recurrence"):
				with suppress(IndexError):
					recurrence = event.get("recurrence")[0]

			# NOTE: Skip if event is already synced; Frappe doesn't track individual
			# instances of recurring events, so we need to check if the event is already
			# synced in Frappe Calendar
			if event.get("recurringEventId"):
				...
			elif not frappe.db.exists("Event", {"google_calendar_event_id": event.get("id")}):
				insert_event_to_calendar(account, event, recurrence)
			else:
				update_event_in_calendar(account, event, recurrence)

		# If any synced Google Calendar Event is cancelled, then close the Event
		elif event.get("status") == "cancelled":
			event_name = frappe.db.get_value(
				"Event",
				{
					"google_calendar_id": account.google_calendar_id,
					"google_calendar_event_id": event.get("id"),
				},
			)
			frappe.db.set_value(
				"Event",
				event_name,
				"status",
				"Closed",
			)
			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Info",
					"reference_doctype": "Event",
					"reference_name": event_name,
					"content": " - Event deleted from Google Calendar.",
				}
			).insert(ignore_permissions=True)

	if not results:
		return _("No Google Calendar Event to sync.")
	elif len(results) == 1:
		return _("1 Google Calendar Event synced.")
	else:
		return _("{0} Google Calendar Events synced.").format(len(results))


def insert_event_to_calendar(account, event, recurrence=None):
	"""
	Inserts event in Frappe Calendar during Sync
	"""
	calendar_event = {
		"doctype": "Event",
		"subject": event.get("summary") or "No Title",
		"description": event.get("description"),
		"google_calendar_event": 1,
		"google_calendar": account.name,
		"google_calendar_id": account.google_calendar_id,
		"google_calendar_event_id": event.get("id"),
		"google_meet_link": event.get("hangoutLink"),
		"pulled_from_google_calendar": 1,
		"event_type": "Public" if account.sync_as_public else "Private",
	} | google_calendar_to_repeat_on(recurrence=recurrence, start=event.get("start"), end=event.get("end"))

	e: Event = frappe.get_doc(calendar_event)
	update_participants_in_event(calendar_event=e, google_event=event)
	e.insert(ignore_permissions=True)
	e.db_set("owner", account.user, update_modified=False)


def update_participants_in_event(calendar_event: "Event", google_event: dict):
	google_event_participants = [
		attendee["email"] for attendee in google_event.get("attendees", []) if not attendee.get("self")
	]
	in_system_participants = frappe.get_all(
		"User", filters={"email": ("in", google_event_participants)}, pluck="email"
	)

	existing_calendar_participants = [
		participant.reference_docname
		for participant in calendar_event.event_participants
		if participant.reference_doctype == "User"
	]

	for participant in in_system_participants:
		if participant not in existing_calendar_participants:
			calendar_event.add_participant("User", participant)

	# Add a Guest user to indicate participants not in the system
	if len(in_system_participants) < len(google_event_participants):
		calendar_event.add_participant("User", "Guest")


def update_event_in_calendar(account, event, recurrence=None):
	"""
	Updates Event in Frappe Calendar if any existing Google Calendar Event is updated
	"""
	calendar_event = frappe.get_doc("Event", {"google_calendar_event_id": event.get("id")})
	calendar_event.subject = event.get("summary")
	calendar_event.description = event.get("description")
	calendar_event.google_meet_link = event.get("hangoutLink")
	calendar_event.update(
		google_calendar_to_repeat_on(recurrence=recurrence, start=event.get("start"), end=event.get("end"))
	)
	update_participants_in_event(calendar_event, event)
	calendar_event.save(ignore_permissions=True)


def insert_event_in_google_calendar(doc, method=None):
	"""
	Insert Events in Google Calendar if sync_with_google_calendar is checked.
	"""
	if (
		not doc.sync_with_google_calendar
		or doc.pulled_from_google_calendar
		or not frappe.db.exists("Google Calendar", {"name": doc.google_calendar})
	):
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	event = {"summary": doc.subject, "description": doc.description, "google_calendar_event": 1}
	event.update(
		format_date_according_to_google_calendar(
			doc.all_day, get_datetime(doc.starts_on), get_datetime(doc.ends_on) if doc.ends_on else None
		)
	)

	if doc.repeat_on:
		event.update({"recurrence": repeat_on_to_google_calendar_recurrence_rule(doc)})

	event.update({"attendees": get_attendees(doc)})

	conference_data_version = 0

	if doc.add_video_conferencing:
		event.update({"conferenceData": get_conference_data(doc)})
		conference_data_version = 1

	try:
		event = (
			google_calendar.events()
			.insert(
				calendarId=doc.google_calendar_id,
				body=event,
				conferenceDataVersion=conference_data_version,
				sendUpdates="all",
			)
			.execute()
		)

		frappe.db.set_value(
			"Event",
			doc.name,
			{"google_calendar_event_id": event.get("id"), "google_meet_link": event.get("hangoutLink")},
			update_modified=False,
		)

		frappe.msgprint(_("Event Synced with Google Calendar."))
	except HttpError as err:
		frappe.throw(
			_("Google Calendar - Could not insert event in Google Calendar {0}, error code {1}.").format(
				account.name, err.resp.status
			)
		)


def update_event_in_google_calendar(doc, method=None):
	"""
	Updates Events in Google Calendar if any existing event is modified in Frappe Calendar
	"""
	# Workaround to avoid triggering updation when Event is being inserted since
	# creation and modified are same when inserting doc
	if (
		not doc.sync_with_google_calendar
		or doc.modified == doc.creation
		or not frappe.db.exists("Google Calendar", {"name": doc.google_calendar})
	):
		return

	if doc.sync_with_google_calendar and not doc.google_calendar_event_id:
		# If sync_with_google_calendar is checked later, then insert the event rather than updating it.
		insert_event_in_google_calendar(doc)
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	try:
		event = (
			google_calendar.events()
			.get(calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id)
			.execute()
		)

		event["summary"] = doc.subject
		event["description"] = doc.description
		event["recurrence"] = repeat_on_to_google_calendar_recurrence_rule(doc)
		event["status"] = (
			"cancelled" if doc.status == "Cancelled" or doc.status == "Closed" else event.get("status")
		)
		event.update(
			format_date_according_to_google_calendar(
				doc.all_day, get_datetime(doc.starts_on), get_datetime(doc.ends_on) if doc.ends_on else None
			)
		)

		conference_data_version = 0

		if doc.add_video_conferencing:
			event.update({"conferenceData": get_conference_data(doc)})
			conference_data_version = 1
		elif doc.get_doc_before_save().add_video_conferencing or event.get("hangoutLink"):
			# remove google meet from google calendar event, if turning off add_video_conferencing
			event.update({"conferenceData": None})
			conference_data_version = 1

		event.update({"attendees": get_attendees(doc)})

		event = (
			google_calendar.events()
			.update(
				calendarId=doc.google_calendar_id,
				eventId=doc.google_calendar_event_id,
				body=event,
				conferenceDataVersion=conference_data_version,
				sendUpdates="all",
			)
			.execute()
		)

		# if add_video_conferencing enabled or disabled during update, overwrite
		frappe.db.set_value(
			"Event",
			doc.name,
			{"google_meet_link": event.get("hangoutLink")},
			update_modified=False,
		)
		doc.notify_update()

		frappe.msgprint(_("Event Synced with Google Calendar."))
	except HttpError as err:
		frappe.throw(
			_("Google Calendar - Could not update Event {0} in Google Calendar, error code {1}.").format(
				doc.name, err.resp.status
			)
		)


def delete_event_from_google_calendar(doc, method=None):
	"""
	Delete Events from Google Calendar if Frappe Event is deleted.
	"""

	if not frappe.db.exists("Google Calendar", {"name": doc.google_calendar, "push_to_google_calendar": 1}):
		return

	google_calendar, _ = get_google_calendar_object(doc.google_calendar)

	try:
		event = (
			google_calendar.events()
			.get(calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id)
			.execute()
		)
		event["recurrence"] = None
		event["status"] = "cancelled"

		google_calendar.events().update(
			calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id, body=event
		).execute()
	except HttpError as err:
		frappe.msgprint(
			_("Google Calendar - Could not delete Event {0} from Google Calendar, error code {1}.").format(
				doc.name, err.resp.status
			)
		)


def parse_google_calendar_date(dt):
	if dt.get("date"):
		return get_datetime(dt.get("date"))
	return parser.parse(dt.get("dateTime")).astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def google_calendar_to_repeat_on(*, start, end, recurrence=None):
	"""
	recurrence is in the form ['RRULE:FREQ=WEEKLY;BYDAY=MO,TU,TH']
	has the frequency and then the days on which the event recurs

	Both have been mapped in a dict for easier mapping.
	"""

	repeat_on = {
		"starts_on": parse_google_calendar_date(start),
		"ends_on": parse_google_calendar_date(end),
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
	if not recurrence:
		return repeat_on

	# google_calendar_frequency = RRULE:FREQ=WEEKLY, byday = BYDAY=MO,TU,TH, until = 20191028
	google_calendar_frequency, until, byday = get_recurrence_parameters(recurrence)
	repeat_on["repeat_on"] = google_calendar_frequencies.get(google_calendar_frequency)

	if repeat_on["repeat_on"] == "Daily":
		repeat_on["ends_on"] = None
		repeat_on["repeat_till"] = until

	if byday and repeat_on["repeat_on"] == "Weekly":
		repeat_on["repeat_till"] = until
		for repeat_day in byday:
			repeat_on[google_calendar_days[repeat_day]] = 1

	if byday and repeat_on["repeat_on"] == "Monthly":
		byday = byday[0]
		repeat_day_week_number, repeat_day_name = None, None

		for num in ["-2", "-1", "1", "2", "3", "4", "5"]:
			if num in byday:
				repeat_day_week_number = num
				break

		for day in ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]:
			if day in byday:
				repeat_day_name = google_calendar_days.get(day)
				break

		# Only Set starts_on for the event to repeat monthly
		start_date = parse_google_calendar_recurrence_rule(int(repeat_day_week_number), repeat_day_name)
		repeat_on["starts_on"] = start_date
		repeat_on["ends_on"] = add_to_date(start_date, minutes=5)
		repeat_on["repeat_till"] = until

	if repeat_on["repeat_till"] == "Yearly":
		repeat_on["ends_on"] = None
		repeat_on["repeat_till"] = until

	return repeat_on


def format_date_according_to_google_calendar(all_day, starts_on, ends_on=None):
	if not ends_on:
		ends_on = starts_on + timedelta(minutes=10)

	date_format = {
		"start": {
			"dateTime": starts_on.isoformat(),
			"timeZone": get_system_timezone(),
		},
		"end": {
			"dateTime": ends_on.isoformat(),
			"timeZone": get_system_timezone(),
		},
	}

	if all_day:
		# If all_day event, Google Calendar takes date as a parameter and not dateTime
		date_format["start"].pop("dateTime")
		date_format["end"].pop("dateTime")

		date_format["start"].update({"date": starts_on.date().isoformat()})
		date_format["end"].update({"date": ends_on.date().isoformat()})

	return date_format


def parse_google_calendar_recurrence_rule(repeat_day_week_number, repeat_day_name):
	"""Return (repeat_on) exact date for combination eg 4TH viz. 4th thursday of a month."""
	if repeat_day_week_number < 0:
		# Consider a month with 5 weeks and event is to be repeated in last week of every month, google caledar considers
		# a month has 4 weeks and hence it'll return -1 for a month with 5 weeks.
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


def repeat_on_to_google_calendar_recurrence_rule(doc):
	"""Return event (repeat_on) in Google Calendar format ie RRULE:FREQ=WEEKLY;BYDAY=MO,TU,TH."""
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


def get_week_number(dt: date):
	"""Return the week number of the month for the specified date.

	https://stackoverflow.com/questions/3806473/python-week-number-of-the-month/16804556
	"""
	first_day = dt.replace(day=1)

	dom = dt.day
	adjusted_dom = dom + first_day.weekday()

	return ceil(adjusted_dom / 7.0)


def get_recurrence_parameters(recurrence: str) -> RecurrenceParameters:
	recurrence = recurrence.split(";")
	frequency, until, byday = None, None, []

	for token in recurrence:
		if "RRULE:FREQ" in token:
			frequency = token

		elif "UNTIL" in token:
			_until = token.replace("UNTIL=", "").rstrip("Z")
			fmt = "%Y%m%dT%H%M%S" if "T" in _until else "%Y%m%d"
			until = datetime.strptime(_until, fmt)

		elif "BYDAY" in token:
			byday = token.split("=", 1)[1].split(",")

	return frequency, until, byday


def get_conference_data(doc):
	return {
		"createRequest": {"requestId": doc.name, "conferenceSolutionKey": {"type": "hangoutsMeet"}},
		"notes": doc.description,
	}


def get_attendees(doc):
	"""Return a list of dicts with attendee emails, if available in event_participants table."""
	attendees, email_not_found = [], []

	for participant in doc.event_participants:
		if participant.get("email"):
			attendees.append({"email": participant.email})
		else:
			email_not_found.append({"dt": participant.reference_doctype, "dn": participant.reference_docname})

	if email_not_found:
		frappe.msgprint(
			_("Google Calendar - Contact / email not found. Did not add attendee for -<br>{0}").format(
				"<br>".join(f"{d.get('dt')} {d.get('dn')}" for d in email_not_found)
			),
			alert=True,
			indicator="yellow",
		)

	return attendees


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
				'hangoutLink': 'https://meet.google.com/mee-ting-uri',
				'conferenceData': {
					'createRequest': {
						'requestId': 'EV00001',
						'conferenceSolutionKey': {
							'type': 'hangoutsMeet'
						},
						'status': {
							'statusCode': 'success'
						}
					},
					'entryPoints': [
						{
							'entryPointType': 'video',
							'uri': 'https://meet.google.com/mee-ting-uri',
							'label': 'meet.google.com/mee-ting-uri'
						}
					],
					'conferenceSolution': {
						'key': {
							'type': 'hangoutsMeet'
						},
						'name': 'Google Meet',
						'iconUri': 'https://fonts.gstatic.com/s/i/productlogos/meet_2020q4/v6/web-512dp/logo_meet_2020q4_color_2x_web_512dp.png'
					},
					'conferenceId': 'mee-ting-uri'
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
