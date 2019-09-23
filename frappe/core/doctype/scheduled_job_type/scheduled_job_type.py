# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe, json
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime
from datetime import datetime
from croniter import croniter
from frappe.utils.background_jobs import enqueue

CRON_MAP = {
	"Yearly": "0 0 1 1 *",
	"Annual": "0 0 1 1 *",
	"Monthly": "0 0 1 * *",
	"Monthly Long": "0 0 1 * *",
	"Weekly": "0 0 * * 0",
	"Weekly Long": "0 0 * * 0",
	"Daily": "0 0 * * *",
	"Daily Long": "0 0 * * *",
	"Hourly": "0 * * * *",
	"Hourly Long": "0 * * * *",
	"All": "0/" + str((frappe.get_conf().scheduler_interval or 240) // 60) + " * * * *",
}

class ScheduledJobType(Document):
	def autoname(self):
		self.name = '.'.join(self.method.split('.')[-2:])

	def validate(self):
		if self.queue != 'All':
			# force logging for all events other than continuous ones (ALL)
			self.create_log = 1

	def enqueue(self):
		# enqueue event if last execution is done
		if self.is_event_due():
			self.update_last_execution()
			frappe.flags.enqueued_jobs.append(self.method)
			enqueue('frappe.core.doctype.scheduled_job_type.scheduled_job_type.run_scheduled_job',
				job_type=self.method)

	def is_event_due(self, current_time = None):
		'''Return true if event is due based on time lapsed since last execution'''
		# save last execution in expected execution time as per cron
		self.last_execution = self.get_next_execution()

		# if the next scheduled event is before NOW, then its due!
		return self.last_execution <= (current_time or now_datetime())

	def get_next_execution(self):
		if not self.cron_format:
			self.cron_format = CRON_MAP[self.queue]

		return croniter(self.cron_format,
			get_datetime(self.last_execution)).get_next(datetime)

	def execute(self):
		try:
			frappe.logger(__name__).info('Started Scheduled Job: {0} for {1}'.format(self.method, frappe.local.site))
			frappe.get_attr(self.method)()
			frappe.db.commit()
			frappe.logger(__name__).info('Completed Scheduled Job: {0} for {1}'.format(self.method, frappe.local.site))
		except Exception:
			frappe.db.rollback()
			frappe.log_error('{} failed'.format(self.method))
			frappe.logger(__name__).info('Failed Scheduled Job: {0} for {1}'.format(self.method, frappe.local.site))


	def update_last_execution(self):
		self.db_set('last_execution', self.last_execution, update_modified=False)
		frappe.db.commit()

	def get_queue_name(self):
		return self.queue.replace(' ', '_').lower()

@frappe.whitelist()
def execute_event(doc):
	frappe.only_for('System Manager')
	doc = json.loads(doc)
	frappe.get_doc('Scheduled Job Type', doc.get('name')).execute()

def run_scheduled_job(job_type):
	'''This is a wrapper function that runs a hooks.scheduler_events method'''
	frappe.get_doc('Scheduled Job Type', dict(method=job_type)).execute()

def sync_jobs():
	frappe.reload_doc('core', 'doctype', 'scheduled_job_type')
	all_events = []
	scheduler_events = frappe.get_hooks("scheduler_events")
	insert_events(all_events, scheduler_events)
	clear_events(all_events, scheduler_events)

def insert_events(all_events, scheduler_events):
	for event_type in scheduler_events:
		events = scheduler_events.get(event_type)
		if isinstance(events, dict):
			insert_cron_event(events, all_events)
		else:
			# hourly, daily etc
			insert_event_list(events, event_type, all_events)

def insert_cron_event(events, all_events):
	for cron_format in events:
		for event in events.get(cron_format):
			all_events.append(event)
			insert_single_event('Cron', event, cron_format)

def insert_event_list(events, event_type, all_events):
	for event in events:
		all_events.append(event)
		queue = event_type.replace('_', ' ').title()
		insert_single_event(queue, event)

def insert_single_event(queue, event, cron_format = None):
	if not frappe.db.exists('Scheduled Job Type', dict(method=event)):
		frappe.get_doc(dict(
			doctype = 'Scheduled Job Type',
			method = event,
			cron_format = cron_format,
			queue = queue
		)).insert()

def clear_events(all_events, scheduler_events):
	for event in frappe.get_all('Scheduled Job Type', ('name', 'method')):
		if event.method not in all_events:
			frappe.db.delete_doc('Scheduled Job Type', event.name)
