import base64
from imaplib import IMAP4
from poplib import POP3
from smtplib import SMTP

import frappe


class Oauth:
	def __init__(
		self,
		conn: IMAP4 | POP3 | SMTP,
		email_account: str,
		email: str,
		access_token: str,
		mechanism: str = "XOAUTH2",
	) -> None:

		self.email_account = email_account
		self.email = email
		self._mechanism = mechanism
		self._conn = conn
		self._access_token = access_token

		self._validate()

	def _validate(self) -> None:
		if not self._access_token:
			frappe.throw(
				frappe._("Please Authorize OAuth for Email Account {}").format(self.email_account),
				title=frappe._("OAuth Error"),
			)

	@property
	def _auth_string(self) -> str:
		return f"user={self.email}\1auth=Bearer {self._access_token}\1\1"

	def connect(self) -> None:
		try:
			if isinstance(self._conn, POP3):
				self._connect_pop()

			elif isinstance(self._conn, IMAP4):
				self._connect_imap()

			else:
				# SMTP
				self._connect_smtp()

		except Exception:
			frappe.log_error(
				"Email Connection Error - Authentication Failed",
				reference_doctype="Email Account",
				reference_name=self.email_account,
			)
			# raising a bare exception here as we have a lot of exception handling present
			# where the connect method is called from - hence just logging and raising.
			raise

	def _connect_pop(self) -> None:
		# NOTE: poplib doesn't have AUTH command implementation
		res = self._conn._shortcmd(
			"AUTH {} {}".format(
				self._mechanism, base64.b64encode(bytes(self._auth_string, "utf-8")).decode("utf-8")
			)
		)

		if not res.startswith(b"+OK"):
			raise

	def _connect_imap(self) -> None:
		self._conn.authenticate(self._mechanism, lambda x: self._auth_string)

	def _connect_smtp(self) -> None:
		self._conn.auth(self._mechanism, lambda x: self._auth_string, initial_response_ok=False)
