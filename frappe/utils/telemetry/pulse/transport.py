import frappe
from frappe.utils import get_request_session

from .utils import pulse_host


class PulseHTTP:
	"""Low-level HTTP transport to the pulse ingest service.

	Owns the connection identity — host, API key, URL building — and nothing
	about event semantics. The client layer composes this with the event queue
	and decides which endpoint each verb posts to.
	"""

	def __init__(self):
		self.api_key = frappe.conf.get("pulse_api_key")
		self.host = pulse_host()

	def _session(self):
		session = get_request_session()
		session.headers.update(
			{
				"Content-Type": "application/json",
				"X-Pulse-API-Key": self.api_key,
			}
		)
		return session

	def _url(self, endpoint: str) -> str:
		return f"{self.host}/{endpoint.lstrip('/')}"

	def post(self, endpoint: str, payload: dict, label: str | None = None, raise_on_error: bool = False):
		"""POST a JSON payload to an endpoint on the pulse host.

		Non-2xx and connection errors are logged. With ``raise_on_error`` (used by
		the queue drain so it can retry) the error propagates; otherwise it's
		swallowed (used by identify/alias, which never raise to the caller).
		"""
		label = label or endpoint
		try:
			resp = self._session().post(self._url(endpoint), data=frappe.as_json(payload), timeout=15)
		except Exception as e:
			frappe.logger("pulse").error(f"pulse-client - {label} failed: {e!s}")
			if raise_on_error:
				raise
			return

		if not (200 <= resp.status_code < 300):
			msg = f"pulse-client - {label} failed: {resp.status_code} {resp.text}"
			frappe.logger("pulse").error(msg)
			if raise_on_error:
				raise Exception(msg)

		return resp
