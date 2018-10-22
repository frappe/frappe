# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import json
import os
from six import iteritems
import logging

from werkzeug.wrappers import Request
from werkzeug.local import LocalManager
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.contrib.profiler import ProfilerMiddleware
from werkzeug.wsgi import SharedDataMiddleware

import frappe
import frappe.handler
import frappe.auth
import frappe.api
import frappe.utils.response
import frappe.website.render
from frappe.utils import get_site_name
from frappe.middlewares import RecorderMiddleware, StaticDataMiddleware
from frappe.utils.error import make_error_snapshot
from frappe.core.doctype.communication.comment import update_comments_in_parent_after_request
from frappe import _

# imports - third-party imports
import pymysql
from pymysql.constants import ER

# imports - module imports

local_manager = LocalManager([frappe.local])

_site = None
_sites_path = os.environ.get("SITES_PATH", ".")

class RequestContext(object):

	def __init__(self, environ):
		self.request = Request(environ)

	def __enter__(self):
		init_request(self.request)

	def __exit__(self, type, value, traceback):
		frappe.destroy()

def recorder(function):
	def wrapper(*args, **kwargs):
		# Execute wrapped function as is
		# Record arguments as well as return value
		result = function(*args, **kwargs)

		import traceback
		stack = "".join(traceback.format_stack())

		# Big hack here
		# PyMysql stores exact DB query in cursor._executed
		# Assumes that function refers to frappe.db.sql
		# __self__ will refer to frappe.db
		# Rest is trivial
		data = {
			"function": function.__name__,
			"args": args,
			"kwargs": kwargs,
			"result": result,
			"stack": stack
		}

		# Record all calls, Will be later stored in cache
		wrapper.calls.append(data)
		return result

	wrapper.calls = list()
	wrapper.path = frappe.request.path
	return wrapper

def dumps(stuff):
	return json.dumps(stuff, default=lambda x: str(x))

def persist(function):
	"""Stores recorded requests and calls in redis cache with following hierarchy

	recorder-paths -> ["Path1", "Path2", ... ,"Path3"]

	recorder-paths is a sorted set, Paths have non decreasing score,
	Highest score means recently visited

	recorder-requests-[path] -> ["UUID3", "UUID2", ...]
	recorder-requests-[path] is a list of UUIDs of requests made on that path
	in reverse chronological order

	recorder-requests-[uuid] -> ["Call1", "Call2"]
	recorder-requests-[uuid] is a list of calls made during that request
	in chronological order
	"""
	path = function.path
	calls = function.calls

	# RecorderMiddleware creates a uuid for every request and
	# stores it in request environ
	uuid = frappe.request.environ["uuid"]

	# Redis Sorted Set -> Ordered set (Ordereed by `score`)
	# Elements are ordered from low to high score

	# Get the highest score from our set
	highest_score = frappe.cache().zrange("recorder-paths", -1, -1, withscores=True)

	# In the begning we might not even have a highest score
	# We have to start somewhere, 0 seems like a safe bet
	highest_score = highest_score[0][1] if highest_score else 0

	# Now insert `path` with score highest + 1
	# Effectively giving `path` the highest score
	# Note: Iff these two operations are done consequtively
	# Note: score can grow exponentially, Will probably need a fix
	frappe.cache().zincrby("recorder-paths", path, amount=float(highest_score)+1)

	# Also record number of times each URL was hit
	frappe.cache().hincrby("recorder-paths-counts", path, 1)

	# LPUSH -> Reverse chronological order for requests
	frappe.cache().lpush("recorder-requests-{}".format(path), uuid)

	# LPUSH -> Chronological order for calls
	# Since every request uuid is unique, no need for any heirarchy

	# Datetime objects cannot be used with json.dumps
	# str() seems to work with them
	calls = map(dumps, calls)
	frappe.cache().rpush("recorder-calls-{}".format(uuid), *calls)

@Request.application
def application(request):
	response = None

	try:
		rollback = True

		init_request(request)

		# Need to record all calls to frappe.db.sql
		# Should be done after frappe.db refers to an instance of Database
		# Now is a good time
		frappe.db.sql = recorder(frappe.db.sql)

		if frappe.local.form_dict.cmd:
			response = frappe.handler.handle()

		elif frappe.request.path.startswith("/api/"):
			if frappe.local.form_dict.data is None:
					frappe.local.form_dict.data = request.get_data()
			response = frappe.api.handle()

		elif frappe.request.path.startswith('/backups'):
			response = frappe.utils.response.download_backup(request.path)

		elif frappe.request.path.startswith('/private/files/'):
			response = frappe.utils.response.download_private_file(request.path)

		elif frappe.local.request.method in ('GET', 'HEAD', 'POST'):
			response = frappe.website.render.render()

		else:
			raise NotFound

	except HTTPException as e:
		return e

	except frappe.SessionStopped as e:
		response = frappe.utils.response.handle_session_stopped()

	except Exception as e:
		response = handle_exception(e)

	else:
		rollback = after_request(rollback)

	finally:
		if frappe.local.request.method in ("POST", "PUT") and frappe.db and rollback:
			frappe.db.rollback()

		# set cookies
		if response and hasattr(frappe.local, 'cookie_manager'):
			frappe.local.cookie_manager.flush_cookies(response=response)

		# Recorded calls need to be stored in cache
		# This looks like a terribe syntax, Because it actually is
		persist(frappe.db.sql)
		frappe.destroy()

	return response

def init_request(request):
	frappe.local.request = request
	frappe.local.is_ajax = frappe.get_request_header("X-Requested-With")=="XMLHttpRequest"

	site = _site or request.headers.get('X-Frappe-Site-Name') or get_site_name(request.host)
	frappe.init(site=site, sites_path=_sites_path)

	if not (frappe.local.conf and frappe.local.conf.db_name):
		# site does not exist
		raise NotFound

	if frappe.local.conf.get('maintenance_mode'):
		raise frappe.SessionStopped

	make_form_dict(request)

	frappe.local.http_request = frappe.auth.HTTPRequest()

def make_form_dict(request):
	import json

	if 'application/json' in (request.content_type or '') and request.data:
		args = json.loads(request.data)
	else:
		args = request.form or request.args

	try:
		frappe.local.form_dict = frappe._dict({ k:v[0] if isinstance(v, (list, tuple)) else v \
			for k, v in iteritems(args) })
	except IndexError:
		frappe.local.form_dict = frappe._dict(args)

	if "_" in frappe.local.form_dict:
		# _ is passed by $.ajax so that the request is not cached by the browser. So, remove _ from form_dict
		frappe.local.form_dict.pop("_")

def handle_exception(e):
	response = None
	http_status_code = getattr(e, "http_status_code", 500)
	return_as_message = False

	if frappe.get_request_header('Accept') and (frappe.local.is_ajax or 'application/json' in frappe.get_request_header('Accept')):
		# handle ajax responses first
		# if the request is ajax, send back the trace or error message
		response = frappe.utils.response.report_error(http_status_code)

	elif (http_status_code==500
		and isinstance(e, pymysql.InternalError)
		and e.args[0] in (ER.LOCK_WAIT_TIMEOUT, ER.LOCK_DEADLOCK)):
			http_status_code = 508

	elif http_status_code==401:
		frappe.respond_as_web_page(_("Session Expired"),
			_("Your session has expired, please login again to continue."),
			http_status_code=http_status_code,  indicator_color='red')
		return_as_message = True

	elif http_status_code==403:
		frappe.respond_as_web_page(_("Not Permitted"),
			_("You do not have enough permissions to complete the action"),
			http_status_code=http_status_code,  indicator_color='red')
		return_as_message = True

	elif http_status_code==404:
		frappe.respond_as_web_page(_("Not Found"),
			_("The resource you are looking for is not available"),
			http_status_code=http_status_code,  indicator_color='red')
		return_as_message = True

	else:
		traceback = "<pre>"+frappe.get_traceback()+"</pre>"
		if frappe.local.flags.disable_traceback:
			traceback = ""

		frappe.respond_as_web_page("Server Error",
			traceback, http_status_code=http_status_code,
			indicator_color='red', width=640)
		return_as_message = True

	if e.__class__ == frappe.AuthenticationError:
		if hasattr(frappe.local, "login_manager"):
			frappe.local.login_manager.clear_cookies()

	if http_status_code >= 500:
		frappe.logger().error('Request Error', exc_info=True)
		make_error_snapshot(e)

	if return_as_message:
		response = frappe.website.render.render("message",
			http_status_code=http_status_code)

	return response

def after_request(rollback):
	if (frappe.local.request.method in ("POST", "PUT") or frappe.local.flags.commit) and frappe.db:
		if frappe.db.transaction_writes:
			frappe.db.commit()
			rollback = False

	# update session
	if getattr(frappe.local, "session_obj", None):
		updated_in_db = frappe.local.session_obj.update()
		if updated_in_db:
			frappe.db.commit()
			rollback = False

	update_comments_in_parent_after_request()

	return rollback

application = local_manager.make_middleware(application)

def serve(port=8000, profile=False, record=False, no_reload=False, no_threading=False, site=None, sites_path='.'):
	global application, _site, _sites_path
	_site = site
	_sites_path = sites_path

	from werkzeug.serving import run_simple

	if profile:
		application = ProfilerMiddleware(application, sort_by=('cumtime', 'calls'))

	if record:
		application = RecorderMiddleware(application)

	if not os.environ.get('NO_STATICS'):
		application = SharedDataMiddleware(application, {
			'/assets': os.path.join(sites_path, 'assets'),
		})

		application = StaticDataMiddleware(application, {
			'/files': os.path.abspath(sites_path)
		})

	application.debug = True
	application.config = {
		'SERVER_NAME': 'localhost:8000'
	}

	in_test_env = os.environ.get('CI')
	if in_test_env:
		log = logging.getLogger('werkzeug')
		log.setLevel(logging.ERROR)

	run_simple('0.0.0.0', int(port), application,
		use_reloader=False if in_test_env else not no_reload,
		use_debugger=not in_test_env,
		use_evalex=not in_test_env,
		threaded=not no_threading)
