from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import pytz

import frappe
from frappe import _
from frappe.frappeclient import FrappeClient, FrappeOAuth2Client
from frappe.utils import convert_utc_to_system_timezone, get_datetime, get_system_timezone


class FrappeMail:
	"""Class to interact with the Frappe Mail API."""

	def __init__(
		self,
		site: str,
		mailbox: str,
		api_key: str | None = None,
		api_secret: str | None = None,
		access_token: str | None = None,
	) -> None:
		self.site = site
		self.mailbox = mailbox
		self.api_key = api_key
		self.api_secret = api_secret
		self.access_token = access_token
		self.client = self.get_client(
			self.site, self.mailbox, self.api_key, self.api_secret, self.access_token
		)

	@staticmethod
	def get_client(
		site: str,
		mailbox: str,
		api_key: str | None = None,
		api_secret: str | None = None,
		access_token: str | None = None,
	) -> FrappeClient | FrappeOAuth2Client:
		"""Returns a FrappeClient or FrappeOAuth2Client instance."""

		if hasattr(frappe.local, "frappe_mail_clients"):
			if client := frappe.local.frappe_mail_clients.get(mailbox):
				return client
		else:
			frappe.local.frappe_mail_clients = {}

		client = (
			FrappeOAuth2Client(url=site, access_token=access_token)
			if access_token
			else FrappeClient(url=site, api_key=api_key, api_secret=api_secret)
		)
		frappe.local.frappe_mail_clients[mailbox] = client

		return client

	def request(
		self,
		method: str,
		endpoint: str,
		params: dict | None = None,
		data: dict | None = None,
		json: dict | None = None,
		files: dict | None = None,
		headers: dict[str, str] | None = None,
		timeout: int | tuple[int, int] = (60, 120),
	) -> Any | None:
		"""Makes a request to the Frappe Mail API."""

		url = urljoin(self.client.url, endpoint)

		headers = headers or {}
		headers.update(self.client.headers)

		if files:
			headers.pop("content-type", None)

		response = self.client.session.request(
			method=method,
			url=url,
			params=params,
			data=data,
			json=json,
			files=files,
			headers=headers,
			timeout=timeout,
		)

		return self.client.post_process(response)

	def validate(self, for_outbound: bool = False, for_inbound: bool = False) -> None:
		"""Validates the mailbox for inbound and outbound emails."""

		endpoint = "/api/method/mail_client.api.auth.validate"
		data = {"mailbox": self.mailbox, "for_outbound": for_outbound, "for_inbound": for_inbound}
		self.request("POST", endpoint=endpoint, data=data)

	def send_raw(
		self, sender: str, recipients: str | list, message: str | bytes, is_newsletter: bool = False
	) -> None:
		"""Sends an email using the Frappe Mail API."""

		endpoint = "/api/method/mail_client.api.outbound.send_raw"
		data = {"from_": sender, "to": recipients, "is_newsletter": is_newsletter}
		self.request("POST", endpoint=endpoint, data=data, files={"raw_message": message})

	def pull_raw(self, limit: int = 50, last_synced_at: str | None = None) -> dict[str, str | list[str]]:
		"""Pulls emails from the mailbox using the Frappe Mail API."""

		endpoint = "/api/method/mail_client.api.inbound.pull_raw"
		if last_synced_at:
			last_synced_at = add_or_update_tzinfo(last_synced_at)

		data = {"mailbox": self.mailbox, "limit": limit, "last_synced_at": last_synced_at}
		headers = {"X-Site": frappe.utils.get_url()}
		response = self.request("GET", endpoint=endpoint, data=data, headers=headers)
		last_synced_at = convert_utc_to_system_timezone(get_datetime(response["last_synced_at"]))

		return {"latest_messages": response["mails"], "last_synced_at": last_synced_at}


def add_or_update_tzinfo(date_time: datetime | str, timezone: str | None = None) -> str:
	"""Adds or updates timezone to the datetime."""

	date_time = get_datetime(date_time)
	target_tz = pytz.timezone(timezone or get_system_timezone())

	if date_time.tzinfo is None:
		date_time = target_tz.localize(date_time)
	else:
		date_time = date_time.astimezone(target_tz)

	return str(date_time)
