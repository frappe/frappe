import os
import sys
from datetime import datetime

import rq
from sentry_sdk import capture_message as sentry_capture_message
from sentry_sdk.hub import Hub
from sentry_sdk.integrations import Integration
from sentry_sdk.integrations.wsgi import _make_wsgi_event_processor
from sentry_sdk.tracing import SOURCE_FOR_STYLE
from sentry_sdk.tracing_utils import record_sql_queries
from sentry_sdk.utils import capture_internal_exceptions, event_from_exception

import frappe
import frappe.monitor
from frappe.database.database import Database, EmptyQueryValues


class FrappeIntegration(Integration):
	identifier = "frappe"

	@staticmethod
	def setup_once():
		real_connect = Database.connect
		real_sql = Database.sql

		def sql(self, query, values=None, *args, **kwargs):
			hub = Hub.current

			if not self._conn:
				self.connect()

			with record_sql_queries(
				hub, self._cursor, query, values, paramstyle="pyformat", executemany=False
			):
				return real_sql(self, query, values or EmptyQueryValues, *args, **kwargs)

		def connect(self):
			hub = Hub.current
			with capture_internal_exceptions():
				hub.add_breadcrumb(message="connect", category="query")

			with hub.start_span(op="db", description="connect"):
				return real_connect(self)

		Database.connect = connect
		Database.sql = sql


def set_scope(scope):
	if job := rq.get_current_job():
		kwargs = job._kwargs
		transaction_name = str(kwargs["method"])
		context = frappe._dict({"scheduled": False, "wait": 0})
		if "run_scheduled_job" in transaction_name:
			transaction_name = kwargs.get("kwargs", {}).get("job_type", "")
			context.scheduled = True

		waitdiff = datetime.utcnow() - job.enqueued_at
		context.uuid = job.id
		context.wait = waitdiff.total_seconds()
		context.kwargs = kwargs

		scope.set_extra("job", context)
		scope.set_transaction_name(transaction_name)
	else:
		if frappe.form_dict.cmd:
			path = f"/api/method/{frappe.form_dict.cmd}"
		else:
			path = frappe.request.path

		scope.set_transaction_name(
			path,
			source=SOURCE_FOR_STYLE["endpoint"],
		)

	scope.set_user({"id": frappe.local.site})
	user = getattr(frappe.session, "user", "Unidentified")
	scope.set_tag("frappe_user", user)
	# Extract `X-Frappe-Request-ID` to store as a separate field if its present
	if trace_id := frappe.monitor.get_trace_id():
		scope.set_tag("frappe_trace_id", trace_id)


def set_sentry_context():
	if not frappe.get_system_settings("enable_telemetry"):
		return

	hub = Hub.current
	with hub.configure_scope() as scope:
		set_scope(scope)


def before_send(event, hint):
	if event.get("logger", "") == "CSSUTILS":
		return None
	return event


def capture_exception(message: str | None = None) -> None:
	"""
	Function to upload exception data to entry

	:param message: A message to be sent if we can't find an exception
	"""
	# Don't report anything if the user hasn't opted-in to telemetry
	if not frappe.get_system_settings("enable_telemetry"):
		return
	try:
		hub = Hub.current
		with hub.configure_scope() as scope:
			if (
				os.getenv("ENABLE_SENTRY_DB_MONITORING") is None
				or os.getenv("SENTRY_TRACING_SAMPLE_RATE") is None
				or os.getenv("SENTRY_PROFILING_SAMPLE_RATE") is None
			):
				set_scope(scope)
			if frappe.request:
				evt_processor = _make_wsgi_event_processor(frappe.request.environ, False)
				scope.add_event_processor(evt_processor)
				if frappe.request.is_json:
					scope.set_context("JSON Body", frappe.request.json)
				elif frappe.request.form:
					scope.set_context("Form Data", frappe.request.form)

		if client := hub.client:
			exc_info = sys.exc_info()
			if any(exc_info):
				# Don't report errors which we can't "fix" in code
				if isinstance(exc_info[1], frappe.ValidationError | frappe.PermissionError):
					return

				event, hint = event_from_exception(
					exc_info,
					client_options=client.options,
					mechanism={"type": "wsgi", "handled": False},
				)
				hub.capture_event(event, hint=hint)
			elif message:
				sentry_capture_message(message, level="error")

	except Exception:
		frappe.logger().error("Failed to capture exception", exc_info=True)
