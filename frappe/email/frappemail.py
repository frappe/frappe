from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import pytz

import frappe
from frappe.frappeclient import FrappeClient
from frappe.utils import convert_utc_to_system_timezone, get_datetime, get_datetime_str, get_system_timezone

if TYPE_CHECKING:
	from requests import Response


class FrappeMailException(Exception):
	"""Exception raised for errors in the Frappe Mail API."""

	def __init__(self, message: str, status_code: int) -> None:
		self.message = message
		self.status_code = status_code
		super().__init__(message)


class FrappeMail:
	"""Class to interact with the Frappe Mail API."""

	def __init__(self, site: str, mailbox: str, api_key: str, api_secret: str) -> None:
		self.site = site
		self.mailbox = mailbox
		self.client = self.get_client(site, mailbox, api_key, api_secret)

	@staticmethod
	def get_client(site: str, mailbox: str, api_key: str, api_secret: str) -> "FrappeClient":
		"""Returns a FrappeClient instance."""

		if hasattr(frappe.local, "frappe_mail_clients"):
			if client := frappe.local.frappe_mail_clients.get(mailbox):
				return client
		else:
			frappe.local.frappe_mail_clients = {}

		client = FrappeClient(url=site, api_key=api_key, api_secret=api_secret)
		frappe.local.frappe_mail_clients[mailbox] = client

		return client

	def request(
		self,
		method: str,
		endpoint: str,
		params: dict | None = None,
		data: dict | None = None,
		json: dict | None = None,
		headers: dict[str, str] | None = None,
		timeout: int | tuple[int, int] = (60, 120),
		raise_exception: bool = True,
	) -> "Response":
		"""Makes a HTTP request to the Frappe Mail API."""

		url = urljoin(self.site, endpoint)
		headers = headers or {}
		headers.update(self.client.headers)
		response = self.client.session.request(
			method=method, url=url, params=params, data=data, json=json, headers=headers, timeout=timeout
		)

		if not response.ok and raise_exception:
			raise FrappeMailException(response.text, response.status_code)

		return response

	def validate(self, for_outbound: bool = False, for_inbound: bool = False) -> None:
		"""Validates the mailbox for inbound and outbound emails."""

		endpoint = "auth/validate"
		data = {"mailbox": self.mailbox, "for_outbound": for_outbound, "for_inbound": for_inbound}
		response = self.request("POST", endpoint=endpoint, data=data, raise_exception=False)

		if not response.ok:
			if exception := response.json().get("exception"):
				if exception == "frappe.exceptions.AuthenticationError":
					exception += ": Invalid API Key or Secret"

				frappe.throw(title="Frappe Mail", msg=exception)

	def send(self, sender: str, recipients: str, message: str) -> None:
		"""Sends an email using the Frappe Mail API."""

		endpoint = "outbound/send-raw"
		json_data = {"from": sender, "to": recipients, "raw_message": message}
		self.request("POST", endpoint=endpoint, json=json_data)

	def pull(self, limit: int = 50, last_synced_at: str | None = None) -> dict[str, list[str] | str]:
		"""Pulls emails from the mailbox using the Frappe Mail API."""

		endpoint = "inbound/pull-raw"
		if last_synced_at:
			last_synced_at = convert_to_utc(last_synced_at)

		data = {"mailbox": self.mailbox, "limit": limit, "last_synced_at": last_synced_at}
		headers = {"X-Site": frappe.utils.get_url()}
		response = self.request("GET", endpoint=endpoint, data=data, headers=headers).json()["message"]
		last_synced_at = convert_utc_to_system_timezone(get_datetime(response["last_synced_at"]))

		return {"latest_messages": response["mails"], "last_synced_at": last_synced_at}


def convert_to_utc(date_time: datetime | str, from_timezone: str | None = None) -> str:
	"""Converts datetime to UTC timezone."""

	dt = (
		pytz.timezone(from_timezone or get_system_timezone())
		.localize(get_datetime(date_time))
		.astimezone(pytz.utc)
	)

	return get_datetime_str(dt)
