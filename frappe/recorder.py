# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import cProfile
import functools
import inspect
import io
import json
import pstats
import re
import time
import typing
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

import sqlparse

import frappe
from frappe import _
from frappe.database.utils import is_query_type
from frappe.utils import now_datetime

RECORDER_INTERCEPT_FLAG = "recorder-intercept"
RECORDER_CONFIG_FLAG = "recorder-config"
RECORDER_REQUEST_SPARSE_HASH = "recorder-requests-sparse"
RECORDER_REQUEST_HASH = "recorder-requests"
TRACEBACK_PATH_PATTERN = re.compile(".*/apps/")
RECORDER_AUTO_DISABLE = 10 * 60


if typing.TYPE_CHECKING:
	from frappe.database.database import Database


@dataclass
class RecorderConfig:
	record_requests: bool = True  # Record web request
	record_jobs: bool = True  # record background jobs
	record_sql: bool = True  # Record SQL queries
	capture_stack: bool = True  # Recod call stack of SQL queries
	capture_doc_events: bool = True  # Record document lifecycle / doc_events timeline
	profile: bool = False  # Run cProfile
	explain: bool = True  # Provide explain output of SQL queries
	request_filter: str = "/"  # Filter request paths
	jobs_filter: str = ""  # Filter background jobs

	def __post_init__(self):
		if not (self.record_jobs or self.record_requests):
			frappe.throw("You must record one of jobs or requests")

	def store(self):
		frappe.cache.set_value(RECORDER_CONFIG_FLAG, self, expires_in_sec=RECORDER_AUTO_DISABLE)

	@classmethod
	def retrieve(cls):
		return frappe.cache.get_value(RECORDER_CONFIG_FLAG) or cls()

	@staticmethod
	def delete():
		frappe.cache.delete_value(RECORDER_CONFIG_FLAG)


def record_sql(*args, **kwargs):
	start_time = time.monotonic()
	result = frappe.db._sql(*args, **kwargs)
	end_time = time.monotonic()

	query = getattr(frappe.db, "last_query", None)
	if not query or isinstance(result, str):
		# run=0, doesn't actually run the query so last_query won't be present
		return result

	stack = []
	if frappe.local._recorder.config.capture_stack:
		stack = list(get_current_stack_frames())

	data = {
		"query": str(query),
		"stack": stack,
		"explain_result": [],
		"time": start_time,
		"duration": float(f"{(end_time - start_time) * 1000:.3f}"),
	}

	frappe.local._recorder.register(data)
	return result


def get_current_stack_frames():
	from frappe.utils.safe_exec import SERVER_SCRIPT_FILE_PREFIX

	try:
		current = inspect.currentframe()
		frames = inspect.getouterframes(current, context=10)
		for frame, filename, lineno, function, context, index in list(reversed(frames))[:-2]:  # noqa: B007
			if "/apps/" in filename or SERVER_SCRIPT_FILE_PREFIX in filename:
				yield {
					"filename": TRACEBACK_PATH_PATTERN.sub("", filename),
					"lineno": lineno,
					"function": function,
				}
	except Exception:
		pass


def _doc_event_contributors(doctype: str, method: str, doc=None) -> tuple[list[str], list[str]]:
	"""Everything Document.run_method runs for (doctype, method): app `doc_events` hooks,
	DocType Event server scripts, and webhooks. Returns (apps, handler_labels), where `apps`
	tags the source (app name, "server_script", or "webhook"). All lookups are cached, and
	any failure is swallowed so tracing can never break the actual request."""
	handlers: list[str] = []
	apps: set[str] = set()

	try:
		doc_hooks = frappe.get_doc_hooks()
		for handler in doc_hooks.get(doctype, {}).get(method, []):
			handlers.append(handler)
			apps.add(handler.split(".")[0])
		# "*" hooks fire on every doctype, so flag them — otherwise it's unclear why an
		# unrelated app's handler ran on this document.
		for handler in doc_hooks.get("*", {}).get(method, []):
			handlers.append(f"{handler}  (all doctypes)")
			apps.add(handler.split(".")[0])
	except Exception:
		pass

	flags = frappe.flags

	# server scripts are skipped by run_server_script_for_doc_event during install/migrate
	try:
		from frappe.core.doctype.server_script.server_script_utils import EVENT_MAP, get_server_script_map

		if not (flags.in_install or flags.in_migrate) and (event := EVENT_MAP.get(method)):
			for name in get_server_script_map().get(doctype, {}).get(event, None) or []:
				handlers.append(f"Server Script: {name}")
				apps.add("server_script")
	except Exception:
		pass

	# Mirror every gate run_webhooks applies so we don't attribute a webhook that wouldn't
	# run: the event must be webhook-supported; skipped during import/patch/install/migrate;
	# on_change doesn't fire on insert; and each webhook's condition is evaluated per-document.
	try:
		from frappe.integrations.doctype.webhook import get_all_webhooks, supported_events
		from frappe.integrations.doctype.webhook.webhook import get_context

		if method in supported_events and not (
			flags.in_import or flags.in_patch or flags.in_install or flags.in_migrate
		):
			skip_on_insert = (
				doc is not None and getattr(doc.flags, "in_insert", False) and method == "on_change"
			)
			webhooks = frappe.client_cache.get_value("webhooks", generator=get_all_webhooks)
			for webhook in webhooks.get(doctype, None) or []:
				if webhook.get("webhook_docevent") != method or skip_on_insert:
					continue
				condition = webhook.get("condition")
				if condition and doc is not None:
					if not frappe.safe_eval(condition, eval_locals=get_context(doc)):
						continue
				handlers.append(f"Webhook: {webhook.get('name')}")
				apps.add("webhook")
	except Exception:
		pass

	return sorted(apps), handlers


_run_method_traced = False


def _install_run_method_tracer():
	"""Wrap Document.run_method once per process so every lifecycle phase / doc_events
	handler is recorded as a timed, nested span on the active recorder — attributed to
	the app(s) that hook it. The wrapper is a cheap no-op unless recording is active with
	`capture_doc_events`, so it is safe to leave installed."""
	global _run_method_traced
	if _run_method_traced:
		return

	from frappe.model.document import Document

	original_run_method = Document.run_method

	@functools.wraps(original_run_method)
	def run_method(doc, method, *args, **kwargs):
		recorder = getattr(frappe.local, "_recorder", None)
		if (
			recorder is None
			or not getattr(recorder, "_recording", False)
			or not recorder.config.capture_doc_events
			or method.startswith("__")
		):
			return original_run_method(doc, method, *args, **kwargs)

		seq = recorder._seq
		depth = recorder._depth
		recorder._seq += 1
		recorder._depth += 1
		queries_before = len(recorder.calls)
		start_time = time.monotonic()
		try:
			return original_run_method(doc, method, *args, **kwargs)
		finally:
			recorder._depth -= 1
			duration = float(f"{(time.monotonic() - start_time) * 1000:.3f}")
			queries = len(recorder.calls) - queries_before
			# compute contributors after the method ran: run_webhooks evaluates each
			# webhook's condition against the post-execution doc, so we must too.
			apps, handlers = _doc_event_contributors(doc.doctype, method, doc=doc)
			recorder.register_event(
				{
					"seq": seq,
					"depth": depth,
					"method": method,
					"ref_doctype": doc.doctype,
					"ref_name": doc.name or "",
					"duration": duration,
					"queries": queries,
					"apps": apps,
					"handlers": handlers,
				}
			)

	Document.run_method = run_method
	_run_method_traced = True


def post_process():
	"""post process all recorded values.

	Any processing that can be done later should be done here to avoid overhead while
	profiling. As of now following values are post-processed:
	        - `EXPLAIN` output of queries.
	        - SQLParse reformatting of queries
	        - Mark duplicates
	"""
	frappe.db.rollback()
	frappe.db.begin(read_only=True)  # Explicitly start read only transaction

	config = RecorderConfig.retrieve()
	result = list(frappe.cache.hgetall(RECORDER_REQUEST_HASH).values())

	for request in result:
		for call in request["calls"]:
			formatted_query = sqlparse.format(
				call["query"].strip(), keyword_case="upper", reindent=True, strip_comments=True
			)
			call["query"] = formatted_query

			# Collect EXPLAIN for executed query
			if config.explain and is_query_type(formatted_query, ("select", "update", "delete")):
				# Only SELECT/UPDATE/DELETE queries can be "EXPLAIN"ed
				try:
					call["explain_result"] = frappe.db.sql(f"EXPLAIN {formatted_query}", as_dict=True)
				except Exception:
					pass
		mark_duplicates(request)
		frappe.cache.hset(RECORDER_REQUEST_HASH, request["uuid"], request)

	config.delete()


def mark_duplicates(request):
	exact_duplicates = Counter([call["query"] for call in request["calls"]])

	for sql_call in request["calls"]:
		sql_call["normalized_query"] = normalize_query(sql_call["query"])

	normalized_duplicates = Counter([call["normalized_query"] for call in request["calls"]])

	for index, call in enumerate(request["calls"]):
		call["index"] = index
		call["exact_copies"] = exact_duplicates[call["query"]]
		call["normalized_copies"] = normalized_duplicates[call["normalized_query"]]


def normalize_query(query: str) -> str:
	"""Attempt to normalize query by removing variables.
	This gives a different view of similar duplicate queries.

	Example:
	        These two are distinct queries:
	                `select * from user where name = 'x'`
	                `select * from user where name = 'z'`

	        But their "normalized" form would be same:
	                `select * from user where name = ?`
	"""

	try:
		q = sqlparse.parse(query)[0]
		for token in q.flatten():
			if "Token.Literal" in str(token.ttype):
				token.value = "?"

		# Transform IN parts like this: IN (?, ?, ?) -> IN (?)
		q = re.sub(r"( IN )\(\?[\s\n\?\,]*\)", r"\1(?)", str(q), flags=re.IGNORECASE)
		return q
	except Exception as e:
		print("Failed to normalize query ", e)

	return query


def record(force=False):
	flag_value = frappe.client_cache.get_value(RECORDER_INTERCEPT_FLAG)
	if flag_value or force:
		frappe.local._recorder = Recorder(force=force)
		return frappe.local._recorder
	elif flag_value is None:
		# Explicitly set it once so next requests can use client-side cache
		frappe.client_cache.set_value(RECORDER_INTERCEPT_FLAG, False)


def dump():
	if hasattr(frappe.local, "_recorder"):
		frappe.local._recorder.dump()


class Recorder:
	def __init__(self, force=False):
		self.config = RecorderConfig.retrieve()
		self.calls = []
		self.profiler = None
		self._recording = True
		self.force = force
		self.cmd = None
		self.method = None
		self.headers = None
		self.form_dict = None
		self.patched_databases = []
		self.events = []
		self._depth = 0
		self._seq = 0

		if (
			self.config.record_requests
			and frappe.request
			and self.config.request_filter in frappe.request.path
		):
			self.path = frappe.request.path
			self.cmd = frappe.local.form_dict.cmd or ""
			self.method = frappe.request.method
			self.headers = dict(frappe.local.request.headers)
			self.form_dict = frappe.local.form_dict
			self.event_type = "HTTP Request"
		elif self.config.record_jobs and frappe.job and self.config.jobs_filter in frappe.job.method:
			self.event_type = "Background Job"
			self.path = frappe.job.method
			self.cmd = None
			self.method = None
			self.headers = None
			self.form_dict = None
		elif not self.force:
			self._recording = False
			return
		else:
			self.event_type = "Function Call"

		self.uuid = None
		self.time = now_datetime()

		self._patch_sql(frappe.db)
		if self.config.capture_doc_events:
			_install_run_method_tracer()

		if self.config.profile:
			self.profiler = cProfile.Profile()
			self.profiler.enable()

	def register(self, data):
		self.calls.append(data)

	def register_event(self, data):
		self.events.append(data)

	def cleanup(self):
		if self.profiler:
			self.profiler.disable()
		self._unpatch_sql()

	def process_profiler(self):
		if self.config.profile or self.profiler:
			self.profiler.disable()
			profiler_output = io.StringIO()
			pstats.Stats(self.profiler, stream=profiler_output).sort_stats("cumulative").print_stats(200)
			profile = profiler_output.getvalue()
			profiler_output.close()
			return profile

	def dump(self):
		if not self._recording:
			return

		import frappe.monitor

		self.uuid = frappe.monitor.get_trace_id() or frappe.generate_hash(length=10)

		profiler_output = self.process_profiler()

		request_data = {
			"uuid": self.uuid,
			"path": self.path,
			"cmd": self.cmd,
			"time": self.time,
			"queries": len(self.calls),
			"time_queries": float("{:0.3f}".format(sum(call["duration"] for call in self.calls))),
			"duration": float(f"{(now_datetime() - self.time).total_seconds() * 1000:0.3f}"),
			"method": self.method,
			"event_type": self.event_type,
			"number_of_events": len(self.events),
			"apps_involved": ", ".join(sorted({app for event in self.events for app in event["apps"]})),
		}
		frappe.cache.hset(RECORDER_REQUEST_SPARSE_HASH, self.uuid, request_data)

		request_data["calls"] = self.calls
		request_data["events"] = sorted(self.events, key=lambda event: event["seq"])
		request_data["headers"] = self.headers
		request_data["form_dict"] = self.form_dict
		request_data["profile"] = profiler_output
		frappe.cache.hset(RECORDER_REQUEST_HASH, self.uuid, request_data)

		self._unpatch_sql()

	def _patch_sql(self, db: "Database"):
		if not self.config.record_sql:
			return

		frappe.db._sql = frappe.db.sql
		frappe.db.sql = record_sql
		self.patched_databases.append(db)

	def _unpatch_sql(self):
		for db in self.patched_databases:
			db.sql = db._sql


def do_not_record(function):
	@functools.wraps(function)
	def wrapper(*args, **kwargs):
		if hasattr(frappe.local, "_recorder"):
			frappe.local._recorder.cleanup()
			del frappe.local._recorder
		return function(*args, **kwargs)

	return wrapper


def administrator_only(function):
	@functools.wraps(function)
	def wrapper(*args, **kwargs):
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator is allowed to use Recorder"))
		return function(*args, **kwargs)

	return wrapper


@frappe.whitelist()
@do_not_record
@administrator_only
def status(*args, **kwargs):
	return bool(frappe.cache.get_value(RECORDER_INTERCEPT_FLAG))


@frappe.whitelist()
@do_not_record
@administrator_only
def start(
	record_jobs: bool = True,
	record_requests: bool = True,
	record_sql: bool = True,
	profile: bool = False,
	capture_stack: bool = True,
	capture_doc_events: bool = True,
	explain: bool = True,
	request_filter: str = "/",
	jobs_filter: str = "",
	*args,
	**kwargs,
):
	RecorderConfig(
		record_requests=int(record_requests),
		record_jobs=int(record_jobs),
		record_sql=int(record_sql),
		profile=int(profile),
		capture_stack=int(capture_stack),
		capture_doc_events=int(capture_doc_events),
		explain=int(explain),
		request_filter=request_filter,
		jobs_filter=jobs_filter,
	).store()
	frappe.client_cache.set_value(RECORDER_INTERCEPT_FLAG, True)
	frappe.cache.expire_key(RECORDER_INTERCEPT_FLAG, RECORDER_AUTO_DISABLE)


@frappe.whitelist()
@do_not_record
@administrator_only
def stop(*args, **kwargs):
	frappe.client_cache.set_value(RECORDER_INTERCEPT_FLAG, False)
	frappe.enqueue(post_process, now=frappe.in_test)


@frappe.whitelist()
@do_not_record
@administrator_only
def get(uuid: str | None = None, *args, **kwargs):
	if uuid:
		result = frappe.cache.hget(RECORDER_REQUEST_HASH, uuid)
	else:
		result = list(frappe.cache.hgetall(RECORDER_REQUEST_SPARSE_HASH).values())
	return result


@frappe.whitelist()
@do_not_record
@administrator_only
def export_data(*args, **kwargs):
	return list(frappe.cache.hgetall(RECORDER_REQUEST_HASH).values())


@frappe.whitelist()
@do_not_record
@administrator_only
def delete(*args, **kwargs):
	frappe.cache.delete_value(RECORDER_REQUEST_SPARSE_HASH)
	frappe.cache.delete_value(RECORDER_REQUEST_HASH)


def record_queries(func: Callable):
	"""Decorator to profile a specific function using recorder."""

	@functools.wraps(func)
	def wrapped(*args, **kwargs):
		recorder = record(force=True)
		recorder.path = f"Function call: {func.__module__}.{func.__qualname__}"
		ret = func(*args, **kwargs)
		dump()
		recorder._unpatch_sql()
		post_process()
		print("Recorded queries, open recorder to view them.")
		return ret

	return wrapped


@frappe.whitelist()
@do_not_record
@administrator_only
def import_data(file: str) -> None:
	file_doc = frappe.get_doc("File", {"file_url": file})
	file_content = json.loads(file_doc.get_content())
	for request in file_content:
		frappe.cache.hset(RECORDER_REQUEST_SPARSE_HASH, request["uuid"], request)
		frappe.cache.hset(RECORDER_REQUEST_HASH, request["uuid"], request)
	file_doc.delete(delete_permanently=True)
