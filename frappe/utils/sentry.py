import os
import sys

from sentry_sdk import capture_message as sentry_capture_message
from sentry_sdk.hub import Hub
from sentry_sdk.integrations.wsgi import _make_wsgi_event_processor
from sentry_sdk.tracing import SOURCE_FOR_STYLE
from sentry_sdk.utils import event_from_exception

import frappe
import frappe.monitor


def before_send(event, hint):
	# Not doing anything here for now - we can add some checks to clean up the data, strip PII, etc.
	return event


def capture_exception(
	exception: ValueError | BaseException | None = None, message: str | None = None
) -> None:
	"""
	Function to upload exception data to entry

	:param exception: Exception object - if missing, try to get with sys.exc_info()
	:param message: A message to be sent if we can't find an exception
	"""
	# Don't report anything if the user hasn't opted-in to telemetry
	if not frappe.get_system_settings("enable_telemetry"):
		return
	try:
		hub = Hub.current

		if frappe.request:
			with hub.configure_scope() as scope:
				scope.set_transaction_name(
					frappe.request.path,
					source=SOURCE_FOR_STYLE["endpoint"],
				)

				evt_processor = _make_wsgi_event_processor(frappe.request.environ, False)
				scope.add_event_processor(evt_processor)
				scope.set_tag("site", frappe.local.site)
				scope.set_tag("user", getattr(frappe.session, "user", "Unidentified"))

				# Extract `X-Frappe-Request-ID` to store as a separate field if its present
				if trace_id := frappe.monitor.get_trace_id():
					scope.set_tag("frappe_trace_id", trace_id)

		if client := hub.client:
			if exception is None and ((exception := sys.exc_info()[1]) is None):
				if message:
					sentry_capture_message(message, level="error")
				return

			event, hint = event_from_exception(
				exception,
				client_options=client.options,
				mechanism={"type": "wsgi", "handled": False},
			)
			hub.capture_event(event, hint=hint)

	except Exception:
		frappe.logger().error("Failed to capture exception", exc_info=True)
		pass


def add_bootinfo(bootinfo):
	"""Called from hook, sends DSN so client side can setup error monitoring."""
	if not frappe.get_system_settings("enable_telemetry"):
		return

	if sentry_dsn := os.getenv("FRAPPE_SENTRY_DSN"):
		bootinfo.sentry_dsn = sentry_dsn
