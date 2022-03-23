# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
import unittest
from icalendar import Calendar, Event,vDatetime
import uuid
import requests

from frappe.utils import (add_to_date, now_datetime, now_datetime)

from frappe.integrations.doctype.google_calendar.google_calendar import (get_event_id,insert_event_to_calendar,
	update_event_in_calendar,close_cancelled_events,parse_calendar_events, get_event_attendees,authorize_access )

class TestGoogleCalendar(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		create_user()

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
	
	def test_insert_event(self):
		account = frappe.get_doc("Google Calendar",{'name' : 'test user calendar'})
		event_list = frappe.db.count("Event")
		event = Event()
		event['DTSTART'] = vDatetime(now_datetime())
		event['DTEND'] = vDatetime(add_to_date(now_datetime(),hours=1))
		event['SUMMARY'] = "test event"
		event['UID'] = uuid.uuid4()
		event['DESCRIPTION'] ="test description"
		event['ATTENDEE'] = ['mailto:test1@example.com','mailto:test2@example.com','mailto:test3@example.com']
		insert_event_to_calendar(account,event,get_event_attendees(event),None)
		event_doc = frappe.get_doc('Event',{"google_calendar_event_id": get_event_id(event)}) 
		self.assertEqual(event_list+1,frappe.db.count("Event"))
		self.assertEqual(len(event['ATTENDEE']),len(event_doc.get('event_participants')))


	def test_update_event(self):
		account = frappe.get_doc("Google Calendar",{'name' : 'test user calendar'}) 
		event = Event()
		event['DTSTART'] = vDatetime(now_datetime())
		event['DTEND'] = vDatetime(add_to_date(now_datetime(),hours=1))
		event['SUMMARY'] = "test event"
		event['UID'] = uuid.uuid4()
		event['DESCRIPTION'] ="test description"
		insert_event_to_calendar(account,event,[],None)
		event['SUMMARY'] = "test now"
		event['DESCRIPTION'] ="test description now"
		update_event_in_calendar(account,event,[],None)
		event_doc = frappe.get_doc("Event",{"google_calendar_event_id": get_event_id(event)})
		self.assertEqual(event_doc.subject,event['SUMMARY'])
		self.assertEqual(event_doc.description,event['DESCRIPTION'])

	def test_close_event(self):
		account = frappe.get_doc("Google Calendar",{'name' : 'test user calendar'})
		event_list = []
		event = Event()
		initial_event_count = frappe.db.count("Event")
		event['DTSTART'] = vDatetime(now_datetime())
		event['DTEND'] = vDatetime(add_to_date(now_datetime(),hours=1))
		event['SUMMARY'] = "test event1"
		event['UID'] = uuid.uuid4()
		event['DESCRIPTION'] ="test description1"
		event_list.append(get_event_id(event))
		insert_event_to_calendar(account,event,[],None)
		event['SUMMARY'] = "test event2"
		event['UID'] = uuid.uuid4()
		event['DESCRIPTION'] ="test description2"
		event_list.append(get_event_id(event))
		insert_event_to_calendar(account,event,[],None)
		close_cancelled_events(event_list)
		event_doc = frappe.db.count("Event",{"status": "Closed"})
		self.assertEqual(initial_event_count,event_doc)

	def test_auth_call(self):
		auth_url = authorize_access(frappe.get_doc("Google Calendar",{'name' : 'test user calendar'}).name)
		response = requests.get(auth_url['url'])
		self.assertEqual(response.status_code,200)

	def test_parse_calendar_events(self):
		account = frappe.get_doc("Google Calendar",{'name' : 'test user calendar'})
		initial_event_count = frappe.db.count("Event")
		ical = Calendar.from_ical(get_ical_file())
		parse_calendar_events(ical,account)
		self.assertEqual(initial_event_count+3,frappe.db.count("Event"))

def create_user():
	new_user = frappe.get_doc(dict(doctype='User', email='test-for-type@example.com',
		first_name='Tester')).insert(ignore_if_duplicate=True)
	account = {
		"doctype": "Google Calendar",
		"enable":1, 
		"calendar_name":"test user calendar",
		"user":new_user.name,
		"pull_from_google_calendar":1, 
		"push_to_google_calendar":1
	}
	frappe.get_doc(account).insert(ignore_permissions=True)

def get_ical_file():
	return b'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
CALSCALE:test-for-type@example.com
X-WR-CALNAME:test-for-type@example.com
X-WR-TIMEZONE:Asia/Kolkata
BEGIN:VEVENT
SUMMARY:test event A
DTSTART:20220228T125128
DTEND:20220228T135128
UID:6cf1f95f-eda3-40a5-a8e8-92d5def6e808
RRULE:RRULE:FREQ=YEARLY\\;UNTIL=20210316T182959Z\\;BYDAY=WE
DESCRIPTION:test description A
STATUS:CONFIRMED
END:VEVENT
BEGIN:VEVENT
SUMMARY:test event B
DTSTART:20220228T145128
DTEND:20220228T155128
UID:ee047e0c-1fa5-4aac-a9ae-43eb88412052
RRULE:RRULE:FREQ=MONTHLY\\;UNTIL=20210316T182959Z\\;BYDAY=WE
DESCRIPTION:test description B
STATUS:CONFIRMED
END:VEVENT
BEGIN:VEVENT
SUMMARY:test event C
DTSTART:20220228T165128
DTEND:20220228T175128
UID:035d6963-2483-4d7d-8022-418516a97dc2
RRULE:RRULE:FREQ=WEEKLY\\;UNTIL=20210316T182959Z\\;BYDAY=WE
ATTENDEE:mailto:test1@example.com
ATTENDEE:mailto:test2@example.com
ATTENDEE:mailto:test3@example.com
DESCRIPTION:test description C
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
'''