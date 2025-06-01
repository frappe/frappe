# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import functools
import gc
import logging
import os
import re

from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.middleware.profiler import ProfilerMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import ClosingIterator

import nts
import nts.api
import nts.handler
import nts.monitor
import nts.rate_limiter
import nts.recorder
import nts.utils.response
from nts import _
from nts.auth import SAFE_HTTP_METHODS, UNSAFE_HTTP_METHODS, HTTPRequest, validate_auth
from nts.middlewares import StaticDataMiddleware
from nts.permissions import handle_does_not_exist_error
from nts.utils import CallbackManager, cint, get_site_name
from nts.utils.data import escape_html
from nts.utils.deprecations import deprecation_warning
from nts.utils.error import log_error_snapshot
from nts.website.serve import get_response

_site = None
_sites_path = os.environ.get("SITES_PATH", ".")


# If gc.freeze is done then importing modules before forking allows us to share the memory
if nts._tune_gc:
	import gettext

	import babel
	import babel.messages
	import bleach
	import num2words
	import pydantic

	import nts.boot
	import nts.client
	import nts.core.doctype.file.file
	import nts.core.doctype.user.user
	import nts.database.mariadb.database  # Load database related utils
	import nts.database.query
	import nts.desk.desktop  # workspace
	import nts.desk.form.save
	import nts.model.db_query
	import nts.query_builder
	import nts.utils.background_jobs  # Enqueue is very common
	import nts.utils.data  # common utils
	import nts.utils.jinja  # web page rendering
	import nts.utils.jinja_globals
	import nts.utils.redis_wrapper  # Exact redis_wrapper
	import nts.utils.safe_exec
	import nts.utils.typing_validations  # any whitelisted method uses this
	import nts.website.path_resolver  # all the page types and resolver
	import nts.website.router  # Website router
	import nts.website.website_generator  # web page doctypes

# end: module pre-loading


def after_response_wrapper(app):
	"""Wrap a WSGI application to call after_response hooks after we have responded.

	This is done to reduce response time by deferring expensive tasks."""

	@functools.wraps(app)
	def application(environ, start_response):
		return ClosingIterator(
			app(environ, start_response),
			(
				nts.rate_limiter.update,
				nts.recorder.dump,
				nts.request.after_response.run,
				nts.destroy,
			),
		)

	return application


@after_response_wrapper
@Request.application
def application(request: Request):
	response = None

	try:
		rollback = True

		init_request(request)

		validate_auth()

		if request.method == "OPTIONS":
			response = Response()

		elif nts.form_dict.cmd:
			deprecation_warning(
				f"{nts.form_dict.cmd}: Sending `cmd` for RPC calls is deprecated, call REST API instead `/api/method/cmd`"
			)
			nts.handler.handle()
			response = nts.utils.response.build_response("json")

		elif request.path.startswith("/api/"):
			response = nts.api.handle(request)

		elif request.path.startswith("/backups"):
			response = nts.utils.response.download_backup(request.path)

		elif request.path.startswith("/private/files/"):
			response = nts.utils.response.download_private_file(request.path)

		elif request.method in ("GET", "HEAD", "POST"):
			response = get_response()

		else:
			raise NotFound

	except HTTPException as e:
		return e

	except Exception as e:
		response = handle_exception(e)

	else:
		rollback = sync_database(rollback)

	finally:
		# Important note:
		# this function *must* always return a response, hence any exception thrown outside of
		# try..catch block like this finally block needs to be handled appropriately.

		if rollback and request.method in UNSAFE_HTTP_METHODS and nts.db:
			nts.db.rollback()

		try:
			run_after_request_hooks(request, response)
		except Exception:
			# We can not handle exceptions safely here.
			nts.logger().error("Failed to run after request hook", exc_info=True)

		log_request(request, response)
		process_response(response)

	return response


def run_after_request_hooks(request, response):
	if not getattr(nts.local, "initialised", False):
		return

	for after_request_task in nts.get_hooks("after_request"):
		nts.call(after_request_task, response=response, request=request)


def init_request(request):
	nts.local.request = request
	nts.local.request.after_response = CallbackManager()

	nts.local.is_ajax = nts.get_request_header("X-Requested-With") == "XMLHttpRequest"

	site = _site or request.headers.get("X-nts-Site-Name") or get_site_name(request.host)
	nts.init(site=site, sites_path=_sites_path, force=True)

	if not (nts.local.conf and nts.local.conf.db_name):
		# site does not exist
		raise NotFound

	if nts.local.conf.maintenance_mode:
		nts.connect()
		if nts.local.conf.allow_reads_during_maintenance:
			setup_read_only_mode()
		else:
			raise nts.SessionStopped("Session Stopped")
	else:
		nts.connect(set_admin_as_user=False)
	if request.path.startswith("/api/method/upload_file"):
		from nts.core.api.file import get_max_file_size

		request.max_content_length = get_max_file_size()
	else:
		request.max_content_length = cint(nts.local.conf.get("max_file_size")) or 25 * 1024 * 1024
	make_form_dict(request)

	if request.method != "OPTIONS":
		nts.local.http_request = HTTPRequest()

	for before_request_task in nts.get_hooks("before_request"):
		nts.call(before_request_task)


def setup_read_only_mode():
	"""During maintenance_mode reads to DB can still be performed to reduce downtime. This
	function sets up read only mode

	- Setting global flag so other pages, desk and database can know that we are in read only mode.
	- Setup read only database access either by:
	    - Connecting to read replica if one exists
	    - Or setting up read only SQL transactions.
	"""
	nts.flags.read_only = True

	# If replica is available then just connect replica, else setup read only transaction.
	if nts.conf.read_from_replica:
		nts.connect_replica()
	else:
		nts.db.begin(read_only=True)


def log_request(request, response):
	if hasattr(nts.local, "conf") and nts.local.conf.enable_nts_logger:
		nts.logger("nts.web", allow_site=nts.local.site).info(
			{
				"site": get_site_name(request.host),
				"remote_addr": getattr(request, "remote_addr", "NOTFOUND"),
				"pid": os.getpid(),
				"user": getattr(nts.local.session, "user", "NOTFOUND"),
				"base_url": getattr(request, "base_url", "NOTFOUND"),
				"full_path": getattr(request, "full_path", "NOTFOUND"),
				"method": getattr(request, "method", "NOTFOUND"),
				"scheme": getattr(request, "scheme", "NOTFOUND"),
				"http_status_code": getattr(response, "status_code", "NOTFOUND"),
			}
		)


def process_response(response):
	if not response:
		return

	# set cookies
	if hasattr(nts.local, "cookie_manager"):
		nts.local.cookie_manager.flush_cookies(response=response)

	# rate limiter headers
	if hasattr(nts.local, "rate_limiter"):
		response.headers.extend(nts.local.rate_limiter.headers())

	if trace_id := nts.monitor.get_trace_id():
		response.headers.extend({"X-nts-Request-Id": trace_id})

	# CORS headers
	if hasattr(nts.local, "conf"):
		set_cors_headers(response)


def set_cors_headers(response):
	if not (
		(allowed_origins := nts.conf.allow_cors)
		and (request := nts.local.request)
		and (origin := request.headers.get("Origin"))
	):
		return

	if allowed_origins != "*":
		if not isinstance(allowed_origins, list):
			allowed_origins = [allowed_origins]

		if origin not in allowed_origins:
			return

	cors_headers = {
		"Access-Control-Allow-Credentials": "true",
		"Access-Control-Allow-Origin": origin,
		"Vary": "Origin",
	}

	# only required for preflight requests
	if request.method == "OPTIONS":
		cors_headers["Access-Control-Allow-Methods"] = request.headers.get("Access-Control-Request-Method")

		if allowed_headers := request.headers.get("Access-Control-Request-Headers"):
			cors_headers["Access-Control-Allow-Headers"] = allowed_headers

		# allow browsers to cache preflight requests for upto a day
		if not nts.conf.developer_mode:
			cors_headers["Access-Control-Max-Age"] = "86400"

	response.headers.extend(cors_headers)


def make_form_dict(request: Request):
	import json

	request_data = request.get_data(as_text=True)
	if request_data and request.is_json:
		args = json.loads(request_data)
	else:
		args = {}
		args.update(request.args or {})
		args.update(request.form or {})

	if isinstance(args, dict):
		nts.local.form_dict = nts._dict(args)
		# _ is passed by $.ajax so that the request is not cached by the browser. So, remove _ from form_dict
		nts.local.form_dict.pop("_", None)
	elif isinstance(args, list):
		nts.local.form_dict["data"] = args
	else:
		nts.throw(_("Invalid request arguments"))


@handle_does_not_exist_error
def handle_exception(e):
	response = None
	http_status_code = getattr(e, "http_status_code", 500)
	return_as_message = False
	accept_header = nts.get_request_header("Accept") or ""
	respond_as_json = (
		nts.get_request_header("Accept")
		and (nts.local.is_ajax or "application/json" in accept_header)
		or (nts.local.request.path.startswith("/api/") and not accept_header.startswith("text"))
	)

	allow_traceback = nts.get_system_settings("allow_error_traceback") if nts.db else False

	if not nts.session.user:
		# If session creation fails then user won't be unset. This causes a lot of code that
		# assumes presence of this to fail. Session creation fails => guest or expired login
		# usually.
		nts.session.user = "Guest"

	if respond_as_json:
		# handle ajax responses first
		# if the request is ajax, send back the trace or error message
		response = nts.utils.response.report_error(http_status_code)

	elif isinstance(e, nts.SessionStopped):
		response = nts.utils.response.handle_session_stopped()

	elif (
		http_status_code == 500
		and (nts.db and isinstance(e, nts.db.InternalError))
		and (nts.db and (nts.db.is_deadlocked(e) or nts.db.is_timedout(e)))
	):
		http_status_code = 508

	elif http_status_code == 401:
		nts.respond_as_web_page(
			_("Session Expired"),
			_("Your session has expired, please login again to continue."),
			http_status_code=http_status_code,
			indicator_color="red",
		)
		return_as_message = True

	elif http_status_code == 403:
		nts.respond_as_web_page(
			_("Not Permitted"),
			_("You do not have enough permissions to complete the action"),
			http_status_code=http_status_code,
			indicator_color="red",
		)
		return_as_message = True

	elif http_status_code == 404:
		nts.respond_as_web_page(
			_("Not Found"),
			_("The resource you are looking for is not available"),
			http_status_code=http_status_code,
			indicator_color="red",
		)
		return_as_message = True

	elif http_status_code == 429:
		response = nts.rate_limiter.respond()

	else:
		traceback = "<pre>" + escape_html(nts.get_traceback()) + "</pre>"
		# disable traceback in production if flag is set
		if nts.local.flags.disable_traceback or not allow_traceback and not nts.local.dev_server:
			traceback = ""

		nts.respond_as_web_page(
			"Server Error", traceback, http_status_code=http_status_code, indicator_color="red", width=640
		)
		return_as_message = True

	if e.__class__ == nts.AuthenticationError:
		if hasattr(nts.local, "login_manager"):
			nts.local.login_manager.clear_cookies()

	if http_status_code >= 500:
		log_error_snapshot(e)

	if return_as_message:
		response = get_response("message", http_status_code=http_status_code)

	if nts.conf.get("developer_mode") and not respond_as_json:
		# don't fail silently for non-json response errors
		print(nts.get_traceback())

	return response


def sync_database(rollback: bool) -> bool:
	# if HTTP method would change server state, commit if necessary
	if nts.db and (nts.local.flags.commit or nts.local.request.method in UNSAFE_HTTP_METHODS):
		nts.db.commit()
		rollback = False
	elif nts.db:
		nts.db.rollback()
		rollback = False

	# update session
	if session := getattr(nts.local, "session_obj", None):
		if session.update():
			rollback = False

	return rollback


# Always initialize sentry SDK if the DSN is sent
if sentry_dsn := os.getenv("nts_SENTRY_DSN"):
	import sentry_sdk
	from sentry_sdk.integrations.argv import ArgvIntegration
	from sentry_sdk.integrations.atexit import AtexitIntegration
	from sentry_sdk.integrations.dedupe import DedupeIntegration
	from sentry_sdk.integrations.excepthook import ExcepthookIntegration
	from sentry_sdk.integrations.modules import ModulesIntegration
	from sentry_sdk.integrations.wsgi import SentryWsgiMiddleware

	from nts.utils.sentry import ntsIntegration, before_send

	integrations = [
		AtexitIntegration(),
		ExcepthookIntegration(),
		DedupeIntegration(),
		ModulesIntegration(),
		ArgvIntegration(),
	]

	experiments = {}
	kwargs = {}

	if os.getenv("ENABLE_SENTRY_DB_MONITORING"):
		integrations.append(ntsIntegration())
		experiments["record_sql_params"] = True

	if tracing_sample_rate := os.getenv("SENTRY_TRACING_SAMPLE_RATE"):
		kwargs["traces_sample_rate"] = float(tracing_sample_rate)
		application = SentryWsgiMiddleware(application)

	if profiling_sample_rate := os.getenv("SENTRY_PROFILING_SAMPLE_RATE"):
		kwargs["profiles_sample_rate"] = float(profiling_sample_rate)

	sentry_sdk.init(
		dsn=sentry_dsn,
		before_send=before_send,
		attach_stacktrace=True,
		release=nts.__version__,
		auto_enabling_integrations=False,
		default_integrations=False,
		integrations=integrations,
		_experiments=experiments,
		**kwargs,
	)


def serve(
	port=8000,
	profile=False,
	no_reload=False,
	no_threading=False,
	site=None,
	sites_path=".",
	proxy=False,
):
	global application, _site, _sites_path
	_site = site
	_sites_path = sites_path

	from werkzeug.serving import run_simple

	if profile or os.environ.get("USE_PROFILER"):
		application = ProfilerMiddleware(application, sort_by=("cumtime", "calls"))

	if not os.environ.get("NO_STATICS"):
		application = application_with_statics()

	if proxy or os.environ.get("USE_PROXY"):
		application = ProxyFix(application, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

	application.debug = True
	application.config = {"SERVER_NAME": "127.0.0.1:8000"}

	log = logging.getLogger("werkzeug")
	log.propagate = False

	in_test_env = os.environ.get("CI")
	if in_test_env:
		log.setLevel(logging.ERROR)

	run_simple(
		"0.0.0.0",
		int(port),
		application,
		exclude_patterns=["test_*"],
		use_reloader=False if in_test_env else not no_reload,
		use_debugger=not in_test_env,
		use_evalex=not in_test_env,
		threaded=not no_threading,
	)


def application_with_statics():
	global application, _sites_path

	application = SharedDataMiddleware(application, {"/assets": str(os.path.join(_sites_path, "assets"))})

	application = StaticDataMiddleware(application, {"/files": str(os.path.abspath(_sites_path))})

	return application


# Remove references to pattern that are pre-compiled and loaded to global scopes.
re.purge()

# Both Gunicorn and RQ use forking to spawn workers. In an ideal world, the fork should be sharing
# most of the memory if there are no writes made to data because of Copy on Write, however,
# python's GC is not CoW friendly and writes to data even if user-code doesn't. Specifically, the
# generational GC which stores and mutates every python object: `PyGC_Head`
#
# Calling gc.freeze() moves all the objects imported so far into permanant generation and hence
# doesn't mutate `PyGC_Head`
#
# Refer to issue for more info: https://github.com/nts/nts/issues/18927
if nts._tune_gc:
	gc.collect()  # clean up any garbage created so far before freeze
	gc.freeze()
