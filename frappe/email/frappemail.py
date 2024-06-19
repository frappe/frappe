from typing import TYPE_CHECKING

import frappe
from frappe.frappeclient import FrappeClient

if TYPE_CHECKING:
	from requests import Response


class FrappeMail:
	"""Class to interact with the Frappe Mail API."""

	def __init__(self, site: str, mailbox: str, api_key: str, api_secret: str) -> None:
		self.site = site
		self.client = self.get_client(site, mailbox, api_key, api_secret)

	@staticmethod
	def get_client(site: str, mailbox: str, api_key: str, api_secret: str) -> FrappeClient:
		"""Returns FrappeClient object for the given email account."""

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
	) -> "Response":
		"""Makes a HTTP request to the Frappe Mail API."""

		url = f"{self.site}/{endpoint}"
		headers = headers or {}
		headers.update(self.client.headers)
		response = self.client.session.request(
			method=method, url=url, params=params, data=data, json=json, headers=headers, timeout=timeout
		)
		return response

	def send(self, sender: str, recipients: str, message: str) -> None:
		"""Sends an email using the Frappe Mail API."""

		endpoint = "outbound/send-raw"
		json_data = {"from": sender, "to": recipients, "raw_message": message}
		self.request("POST", endpoint=endpoint, json=json_data)

	def pull(
		self, mailbox: str, limit: int = 50, last_synced_at: str | None = None
	) -> dict[str, list[str] | str]:
		"""Returns the emails for the given mailbox."""

		endpoint = "inbound/pull"
		data = {"mailbox": mailbox, "limit": limit, "last_synced_at": last_synced_at}
		headers = {"X-Site": frappe.utils.get_url()}
		response = self.request("GET", endpoint=endpoint, data=data, headers=headers).json()["message"]

		return {"latest_messages": response["mails"], "last_synced_at": response["last_synced_at"]}
