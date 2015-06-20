# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals


import frappe
import os
import time
from functools import wraps
from frappe.utils import get_site_path
import json
from frappe import conf

END_LINE = '<!-- frappe: end-file -->'
TASK_LOG_MAX_AGE = 86400  # 1 day in seconds
redis_server = None


def handler(f):
	cmd = f.__module__ + '.' + f.__name__

	def _run(args, set_in_response=True):
		from frappe.tasks import run_async_task
		args = frappe._dict(args)
		task = run_async_task.delay(frappe.local.site,
			(frappe.session and frappe.session.user) or 'Administrator', cmd, args)
		if set_in_response:
			frappe.local.response['task_id'] = task.id
		return task.id

	@wraps(f)
	def _f(*args, **kwargs):
		from frappe.tasks import run_async_task
		task = run_async_task.delay(frappe.local.site,
			(frappe.session and frappe.session.user) or 'Administrator', cmd,
				frappe.local.form_dict)
		frappe.local.response['task_id'] = task.id
		return {
			"status": "queued",
			"task_id": task.id
		}
	_f.async = True
	_f._f = f
	_f.run = _run
	frappe.whitelisted.append(f)
	frappe.whitelisted.append(_f)
	return _f


def run_async_task(method, args, reference_doctype=None, reference_name=None, set_in_response=True):
	if frappe.local.request and frappe.local.request.method == "GET":
		frappe.throw("Cannot run task in a GET request")
	task_id = method.run(args, set_in_response=set_in_response)
	task = frappe.new_doc("Async Task")
	task.celery_task_id = task_id
	task.status = "Queued"
	task.reference_doctype = reference_doctype
	task.reference_name = reference_name
	task.save()
	return task_id


@frappe.whitelist()
def get_pending_tasks_for_doc(doctype, docname):
	return frappe.db.sql_list("select name from `tabAsync Task` where status in ('Queued', 'Running') and reference_doctype='%s' and reference_name='%s'" % (doctype, docname))


@handler
def ping():
	from time import sleep
	sleep(6)
	return "pong"


@frappe.whitelist()
def get_task_status(task_id):
	from frappe.celery_app import get_celery
	c = get_celery()
	a = c.AsyncResult(task_id)
	frappe.local.response['response'] = a.result
	return {
		"state": a.state,
		"progress": 0
	}


def set_task_status(task_id, status, response=None):
	frappe.db.set_value("Async Task", task_id, "status", status)
	if not response:
		response = {}
	response.update({
		"status": status,
		"task_id": task_id
	})
	emit_via_redis("task_status_change", response, room="task:" + task_id)


def remove_old_task_logs():
	logs_path = get_site_path('task-logs')

	def full_path(_file):
		return os.path.join(logs_path, _file)

	files_to_remove = [full_path(_file) for _file in os.listdir(logs_path)]
	files_to_remove = [_file for _file in files_to_remove if is_file_old(_file) and os.path.isfile(_file)]
	for _file in files_to_remove:
		os.remove(_file)


def is_file_old(file_path):
	return ((time.time() - os.stat(file_path).st_mtime) > TASK_LOG_MAX_AGE)


def emit_via_redis(event, message, room=None):
	r = get_redis_server()
	r.publish('events', json.dumps({'event': event, 'message': message, 'room': room}))


def put_log(task_id, line_no, line):
	r = get_redis_server()
	print "task_log:" + task_id
	r.hset("task_log:" + task_id, line_no, line)


def get_redis_server():
	"""Returns memcache connection."""
	global redis_server
	if not redis_server:
		from redis import Redis
		redis_server = Redis.from_url(conf.get("cache_redis_server") or "redis://localhost:12311")
	return redis_server


class FileAndRedisStream(file):
	def __init__(self, *args, **kwargs):
		ret = super(FileAndRedisStream, self).__init__(*args, **kwargs)
		self.count = 0
		return ret

	def write(self, data):
		ret = super(FileAndRedisStream, self).write(data)
		if frappe.local.task_id:
			emit_via_redis('task_progress', {
				"message": {
					"lines": {self.count: data}
				},
				"task_id": frappe.local.task_id
			}, room="task_progress:" + frappe.local.task_id)

			put_log(frappe.local.task_id, self.count, data)
			self.count += 1
		return ret


def get_std_streams(task_id):
	stdout = FileAndRedisStream(get_task_log_file_path(task_id, 'stdout'), 'w')
	# stderr = FileAndRedisStream(get_task_log_file_path(task_id, 'stderr'), 'w')
	return stdout, stdout


def get_task_log_file_path(task_id, stream_type):
	logs_dir = frappe.utils.get_site_path('task-logs')
	return os.path.join(logs_dir, task_id + '.' + stream_type)


@frappe.whitelist(allow_guest=True)
def can_subscribe_doc(doctype, docname, sid):
	from frappe.sessions import Session
	from frappe.exceptions import PermissionError
	session = Session(None).get_session_data()
	if not frappe.has_permission(user=session.user, doctype=doctype, doc=docname, ptype='read'):
		raise PermissionError()
	return True
