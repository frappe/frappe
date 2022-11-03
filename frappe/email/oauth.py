import base64
from imaplib import IMAP4
from poplib import POP3
from smtplib import SMTP
from urllib.parse import quote

import frappe
from frappe.integrations.google_oauth import GoogleOAuth
from frappe.utils.password import encrypt


class OAuthenticationError(Exception):
	pass


class Oauth:
	def __init__(
		self,
		conn: IMAP4 | POP3 | SMTP,
		email_account: str,
		email: str,
		access_token: str,
		refresh_token: str,
		service: str,
		mechanism: str = "XOAUTH2",
	) -> None:

		self.email_account = email_account
		self.email = email
		self.service = service
		self._mechanism = mechanism
		self._conn = conn
		self._access_token = access_token
		self._refresh_token = refresh_token

		self._validate()

	def _validate(self) -> None:
		if self.service != "GMail":
			raise NotImplementedError(
				f"Service {self.service} currently doesn't have oauth implementation."
			)

		if not self._refresh_token:
			frappe.throw(
				frappe._("Please Authorize OAuth."),
				OAuthenticationError,
				frappe._("OAuth Error"),
			)

	@property
	def _auth_string(self) -> str:
		return f"user={self.email}\1auth=Bearer {self._access_token}\1\1"

	def connect(self, _retry: int = 0) -> None:
		"""Connection method with retry on exception for connection errors"""
		try:
			if isinstance(self._conn, POP3):
				res = self._connect_pop()

				if not res.startswith(b"+OK"):
					raise

			elif isinstance(self._conn, IMAP4):
				self._connect_imap()

			else:
				# SMTP
				self._connect_smtp()

		except Exception as e:
			if _retry > 0:
				frappe.log_error(
					"SMTP Connection Error - Authentication Failed", str(e), "Email Account", self.email_account
				)
				# raising a bare exception here as we have a lot of exception handling present
				# where the connect method is called from - hence just logging and raising.
				raise

			self.connect(_retry + 1)

	def _connect_pop(self) -> bytes:
		# poplib doesn't have AUTH command implementation
		res = self._conn._shortcmd(
			"AUTH {} {}".format(
				self._mechanism, base64.b64encode(bytes(self._auth_string, "utf-8")).decode("utf-8")
			)
		)

		return res

	def _connect_imap(self) -> None:
		self._conn.authenticate(self._mechanism, lambda x: self._auth_string)

	def _connect_smtp(self) -> None:
		self._conn.auth(self._mechanism, lambda x: self._auth_string, initial_response_ok=False)
