# -*- coding: utf-8 -*-
# Copyright (c) 2019, ElasticRun and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from functools import wraps
import frappe
from frappe.model.document import get_controller
from frappe.utils.gevent_background.job import PROCESSING, SUCCESS, FAILURE, get_job_configs
from frappe.model.document import Document
from datetime import timedelta

from frappe.utils.data import cint
import pickle,base64

DEFAULT_CONFIG = {'max_retries' : 5,'retry_intervals' : [1,2,3,5,8]}

class JobRun(Document):
	def update_status(self, status):
		if self.status == status:
			return

		self.status = status
		if status == PROCESSING:
			self.started = frappe.utils.now_datetime()
		elif status in (SUCCESS, FAILURE):
			self.finished = frappe.utils.now_datetime()

		self.db_update()
		self.run_method("on_status_change")

	# @child_transaction()
	def load_from_db(self, *args, **kwargs):
		doc = super().load_from_db(*args, **kwargs)
		frappe.db.commit()
		return doc

	# @child_transaction()
	def db_insert(self):
		self.run_date = frappe.utils.nowdate()
		super().db_insert()
		frappe.db.commit()

	# @child_transaction()
	def db_update(self):
		super().db_update()
		frappe.db.commit()

	# @child_transaction()
	def db_set(self, *args, **kwargs):
		doc = super().db_set(*args, **kwargs)
		frappe.db.commit()
		return doc

	@classmethod
	def remove_old_logs(cls):
		while frappe.local.db.sql("""
			delete from `tabJob Run` where modified <= %(today)s - interval 4 day limit 100
		""", {'today': frappe.utils.nowdate()}):
			frappe.db.commit()

# def on_doctype_update():
# 	create_index('tabJob Run', ['method', 'run_date'])
# 	create_index('tabJob Run', ['status', 'retriable'])
# 	create_index('tabJob Run', ['parent'])

def remove_old_logs():
	get_controller('Job Run').remove_old_logs()

def get_valid_failed_jobs():
	failed_jobs = frappe.get_all("Job Run", fields=['name',
		"retry_count",
		"params","method",
		"current_interval_index",
		"next_retry_at",
	], filters={
		"status" : "Failure",
		"retriable": 1,
	})
	return failed_jobs

def get_unpicked_jobs():
	unpicked_jobs = frappe.get_all("Job Run", fields=['name',
		"retry_count",
		"params","method",
		"current_interval_index",
		"next_retry_at",
	], filters = [
		["status", "=", "Pending"],
		["retriable", "=", 1],
		["modified", "<", frappe.utils.now_datetime() - timedelta(hours = 1)],
		["modified", ">", frappe.utils.now_datetime() - timedelta(hours = 24)],
	])
	return unpicked_jobs

def get_stuck_jobs():
	stuck_jobs = frappe.get_all("Job Run", fields=['name',
		"retry_count",
		"params","method",
		"current_interval_index",
		"next_retry_at",
	], filters=[
		["status", "=", "Processing"],
		["retriable", "=", 1],
		["modified", "<", frappe.utils.now_datetime() - timedelta(hours = 1)],
		["modified", ">", frappe.utils.now_datetime() - timedelta(hours = 24)],
	], debug=1)
	return stuck_jobs

def retry_unpicked_jobs():
	jobs = get_unpicked_jobs()
	if jobs:
		retry_jobs(jobs)

def retry_failed_jobs():
	jobs = get_valid_failed_jobs()
	if jobs:
		retry_jobs(jobs)

def retry_stuck_jobs():
	jobs = get_stuck_jobs()
	if jobs:
		retry_jobs(jobs)

def retry_jobs(jobs, calling_func='retry_failed_jobs'):
	job_configs = get_job_configs()
	for job in jobs:
		job_config = job_configs.get(job.method, DEFAULT_CONFIG)
		frappe.utils.background_jobs.enqueue(
			retry_job,
			job=job,
			job_config=job_config,
			job_name=job.name,
		)

# function handling retry operation
def retry_job(job, job_config, print_messages=False):
	job = frappe.get_doc('Job Run', job.name)
	if not (
		validate_retry_count(job, job_config, print_messages)
		and validate_retry_interval(job, job_config, print_messages)
	):
		return

	params = pickle.loads(base64.b64decode(job.params)) if job.params else {}
	params['job_run_id'] = job.name
	set_next_retry_data(job, job_config)
	frappe.utils.background_jobs.enqueue(job.method, **params)

	if print_messages:
		frappe.msgprint("Job is enqueued for retry")

# function to serve retry button on front end
@frappe.whitelist()
def retry(jobrun_name):
	job = frappe.get_doc('Job Run', jobrun_name)
	if job.status != "Failure":
		frappe.msgprint("Invalid job status")
		return

	job_config = get_job_configs().get(job.method, None)
	if not job_config or not job.retriable:
		frappe.msgprint("Retry is disabled for this job")
		return

	retry_job(job, job_config, print_messages=True)

# if retried count >= max_retries
def validate_retry_count(job, job_config, print_messages):
	if job.retry_count >= job_config.get('max_retries'):
		job.status = "RETRIES EXHAUSTED"
		job.save(ignore_permissions=True)
		if print_messages:
			frappe.msgprint("Job is already retried configured max number of times")
		return False

	return True

def validate_retry_interval(job, job_config, print_messages):
	if job.next_retry_at and frappe.utils.now_datetime() < frappe.utils.get_datetime(job.next_retry_at):
		if print_messages:
			frappe.msgprint(f"Job will be next retried at {job.next_retry_at}")
		return False

	return True

def set_next_retry_data(job,job_config):
	next_interval, next_update_time = get_next_retry_info(job,job_config)
	# setting data for next retry attempt
	job.retry_count = job.retry_count + 1
	job.current_interval_index = next_interval
	job.next_retry_at = next_update_time
	job.db_update()

# if we have reached at the end of retry interval sequence,
# then we will retry it after n minutes everytime, where n is the last value in retry interval sequence
def get_next_retry_info(job,job_config):
	next_interval_index = job.current_interval_index
	if (next_interval_index + 1) < len(job_config.get('retry_intervals')):
		next_interval_index += 1
		next_interval = job_config.get('retry_intervals')[next_interval_index]
	else:
		next_interval = job_config.get('retry_intervals')[-1]

	# minutes_to_next_update = job_config.get('retry_intervals')[next_interval] or 0
	next_update_time = frappe.utils.now_datetime() + timedelta(minutes = cint(next_interval or 0))
	return (next_interval_index,next_update_time)

def child_transaction(**extra_args):
	extra_args['autocommit'] = True
	extra_args['read_only_session'] = False

	def decorator(fn):
		@wraps(fn)
		def decorated(*args, **kwargs):
			old_db = frappe.local.db
			props = old_db.get_props()
			props.update(extra_args)
			from frappe.database import get_db
			new_db = get_db(**props)
			frappe.local.db = new_db
			try:
				return fn(*args, **kwargs)
			finally:
				frappe.local.db = old_db

		return decorated
	return decorator
