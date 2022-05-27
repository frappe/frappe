# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
import base64
import imaplib
import poplib
import smtplib
from typing import Union

from frappe import _, db, log_error, throw
from frappe.integrations.google_oauth import GoogleAuthenticationError, GoogleOAuth
from frappe.utils import cint


def get_port(doc):
	if not doc.incoming_port:
		if doc.use_imap:
			doc.incoming_port = imaplib.IMAP4_SSL_PORT if doc.use_ssl else imaplib.IMAP4_PORT

		else:
			doc.incoming_port = poplib.POP3_SSL_PORT if doc.use_ssl else poplib.POP3_PORT

	return cint(doc.incoming_port)


def connect_google_oauth(
	connection_obj: Union[imaplib.IMAP4, poplib.POP3, smtplib.SMTP],
	email_account: str,
	email: str,
	google_access_token: str,
	google_refresh_token: str,
	retry: int = 0,
) -> None:
	auth_string = "user=%s\1auth=Bearer %s\1\1" % (email, google_access_token)
	mechanism = "XOAUTH2"
	_func = lambda x: auth_string  # noqa: E731

	try:
		if isinstance(connection_obj, poplib.POP3):
			# poplib doesn't have AUTH command implementation
			res = connection_obj._shortcmd(
				"AUTH {0} {1}".format(mechanism, base64.b64encode(bytes(auth_string, "utf-8")).decode("utf-8"))
			)

			if not res.startswith(b"+OK"):
				raise

		elif isinstance(connection_obj, imaplib.IMAP4):
			connection_obj.authenticate(mechanism, _func)

		else:
			# SMTP
			connection_obj.auth(mechanism, _func, initial_response_ok=False)

	except Exception:
		# maybe the access token expired - refreshing
		access_token = refresh_google_access_token(email_account, google_refresh_token)

		if not access_token or retry > 0:
			throw(
				_("Google Authentication Failed. Please Check and Update the credentials."),
				GoogleAuthenticationError,
				_("Google Authentication Error"),
			)

		connect_google_oauth(
			connection_obj, email_account, email, access_token, google_refresh_token, retry + 1
		)


def refresh_google_access_token(email_account: str, google_refresh_token: str) -> str:
	oauth_obj = GoogleOAuth("mail")
	res = oauth_obj.refresh_access_token(google_refresh_token)
	db.set_value("Email Account", email_account, "google_access_token", res.get("access_token"))

	return res.get("access_token")
