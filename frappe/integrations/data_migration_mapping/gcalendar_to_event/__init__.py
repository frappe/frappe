#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from datetime import datetime, timedelta
from dateutil.parser import parse
from pytz import timezone
from frappe.utils import add_days


def pre_process(events):
	if events["status"] == "cancelled":
		if frappe.db.exists("Event", dict(gcalendar_sync_id=events["id"])):
			e = frappe.get_doc("Event", dict(gcalendar_sync_id=events["id"]))
			frappe.delete_doc("Event", e.name)
		return {}

	elif events["status"] == "confirmed":
		if 'date' in events["start"]:
			datevar = 'date'
			start_dt = parse(events["start"]['date'])
			end_dt = add_days(parse(events["end"]['date']), -1)
		elif 'dateTime' in events["start"]:
			datevar = 'dateTime'
			start_dt = parse(events["start"]['dateTime'])
			end_dt = parse(events["end"]['dateTime'])

		if start_dt.tzinfo is None or start_dt.tzinfo.utcoffset(start_dt) is None:
			if "timeZone" in events["start"]:
				event_tz = events["start"]["timeZone"]
			else:
				event_tz = events["calendar_tz"]
			start_dt = timezone(event_tz).localize(start_dt)

		if end_dt.tzinfo is None or end_dt.tzinfo.utcoffset(end_dt) is None:
			if "timeZone" in events["end"]:
				event_tz = events["end"]["timeZone"]
			else:
				event_tz = events["calendar_tz"]
			end_dt = timezone(event_tz).localize(end_dt)

		default_tz = frappe.db.get_value("System Settings", None, "time_zone")

		event = {
			'id': events["id"],
			'summary': events["summary"],
			'start_datetime': start_dt.astimezone(timezone(default_tz)).strftime('%Y-%m-%d %H:%M:%S'),
			'end_datetime': end_dt.astimezone(timezone(default_tz)).strftime('%Y-%m-%d %H:%M:%S'),
			'account': events['account']
		}

		if "recurrence" in events:
			recurrence = get_recurrence_event_fields_value(events['recurrence'][0], events["start"][datevar])

			event.update(recurrence)

		if 'description' in events:
			event.update({'description': events["description"]})
		else:
			event.update({'description': ""})

		if datevar == 'date':
			event.update({'all_day': 1})

		return event


def get_recurrence_event_fields_value(recur_rule, starts_on):
	repeat_on = ""
	repeat_till = ""
	repeat_days = {}
	# get recurrence rule from string
	for _str in recur_rule.split(";"):
		if "RRULE:FREQ" in _str:
			repeat_every = _str.split("=")[1]
			if repeat_every == "DAILY": repeat_on = "Daily"
			elif repeat_every == "WEEKLY": repeat_on = "Weekly"
			elif repeat_every == "MONTHLY": repeat_on = "Monthly"
			else: repeat_on = "Yearly"
		elif "UNTIL" in _str:
			# get repeat till
			date = parse(_str.split("=")[1])
			repeat_till = get_repeat_till_date(date)
		elif "COUNT" in _str:
			# get repeat till
			date = parse(starts_on)
			repeat_till = get_repeat_till_date(date, count=_str.split("=")[1], repeat_on=repeat_on)
		elif "BYDAY" in _str:
			days = _str.split("=")[1]
			repeat_days.update({
				"sunday": 1 if "SU" in days else 0,
				"monday": 1 if "MO" in days else 0,
				"tuesday": 1 if "TU" in days else 0,
				"wednesday": 1 if "WD" in days else 0,
				"thursday": 1 if "TH" in days else 0,
				"friday": 1 if "FR" in days else 0,
				"saturday": 1 if "SA" in days else 0,
			})
			repeat_on = "Weekly"

	recurrence = {
		"repeat_on": repeat_on,
		"repeat_till": repeat_till,
		"repeat_this_event": 1
	}

	if repeat_days:
		recurrence.update(repeat_days)

	return recurrence


def get_repeat_till_date(date, count=None, repeat_on=None):
	if count:
		if repeat_on == "Daily":
			# add days
			date = date + timedelta(days=int(count))
		elif repeat_on == "Weekly":
			# add weeks
			date = date + timedelta(weeks=int(count))
		elif repeat_on == "Monthly":
			# add months
			date = add_months(date, int(count))
		elif repeat_on == "Yearly":
			# add years
			date = add_months(date, int(count) * 12)
		else:
			# set default value
			date = add_months(date, int(count))

	return date.strftime("%Y-%m-%d")

def add_months(date, count):
	import calendar

	month = date.month - 1 + count
	year = date.year + month / 12
	month = month % 12 + 1
	day = min(date.day,calendar.monthrange(year,month)[1])
	return datetime(year,month,day)
