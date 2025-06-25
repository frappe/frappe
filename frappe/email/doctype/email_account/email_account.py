# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import email.utils
import functools
import imaplib
import time
from datetime import datetime, timedelta
from poplib import error_proto

import frappe
from frappe import _, are_emails_muted, safe_encode
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.desk.form import assign_to
from frappe.email.doctype.email_domain.email_domain import EMAIL_DOMAIN_FIELDS
from frappe.email.frappemail import FrappeMail
from frappe.email.receive import EmailServer, InboundMail, SentEmailInInboxError
from frappe.email.smtp import SMTPServer
from frappe.email.utils import get_port
from frappe.model.document import Document
from frappe.utils import cint, comma_or, cstr, parse_addr, validate_email_address
from frappe.utils.background_jobs import enqueue, get_jobs
from frappe.utils.jinja import render_template
from frappe.utils.user import get_system_managers


class SentEmailInInbox(Exception):
	pass


def cache_email_account(cache_name):
	def decorator_cache_email_account(func):
		@functools.wraps(func)
		def wrapper_cache_email_account(*args, **kwargs):
			if not hasattr(frappe.local, cache_name):
				setattr(frappe.local, cache_name, {})

			cached_accounts = getattr(frappe.local, cache_name)
			match_by = [*list(kwargs.values()), "default"]
			matched_accounts = list(filter(None, [cached_accounts.get(key) for key in match_by]))
			if matched_accounts:
				return matched_accounts[0]

			matched_accounts = func(*args, **kwargs)
			cached_accounts.update(matched_accounts or {})
			return matched_accounts and next(iter(matched_accounts.values()))

		return wrapper_cache_email_account

	return decorator_cache_email_account


class EmailAccount(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.email.doctype.imap_folder.imap_folder import IMAPFolder
		from frappe.types import DF

		add_signature: DF.Check
		always_bcc: DF.Data | None
		always_use_account_email_id_as_sender: DF.Check
		always_use_account_name_as_sender_name: DF.Check
		api_key: DF.Data | None
		api_secret: DF.Password | None
		append_emails_to_sent_folder: DF.Check
		append_to: DF.Link | None
		ascii_encode_password: DF.Check
		attachment_limit: DF.Int
		auth_method: DF.Literal["Basic", "OAuth"]
		auto_reply_message: DF.TextEditor | None
		awaiting_password: DF.Check
		backend_app_flow: DF.Check
		brand_logo: DF.AttachImage | None
		connected_app: DF.Link | None
		connected_user: DF.Link | None
		create_contact: DF.Check
		default_incoming: DF.Check
		default_outgoing: DF.Check
		domain: DF.Link | None
		email_account_name: DF.Data | None
		email_id: DF.Data
		email_server: DF.Data | None
		email_sync_option: DF.Literal["ALL", "UNSEEN"]
		enable_auto_reply: DF.Check
		enable_automatic_linking: DF.Check
		enable_incoming: DF.Check
		enable_outgoing: DF.Check
		footer: DF.TextEditor | None
		frappe_mail_site: DF.Data | None
		imap_folder: DF.Table[IMAPFolder]
		incoming_port: DF.Data | None
		initial_sync_count: DF.Literal["100", "250", "500"]
		last_synced_at: DF.Datetime | None
		login_id: DF.Data | None
		login_id_is_different: DF.Check
		no_failed: DF.Int
		no_smtp_authentication: DF.Check
		notify_if_unreplied: DF.Check
		password: DF.Password | None
		send_notification_to: DF.SmallText | None
		send_unsubscribe_message: DF.Check
		sent_folder_name: DF.Data | None
		service: DF.Literal[
			"", "Frappe Mail", "GMail", "Sendgrid", "SparkPost", "Yahoo Mail", "Outlook.com", "Yandex.Mail"
		]
		signature: DF.TextEditor | None
		smtp_port: DF.Data | None
		smtp_server: DF.Data | None
		track_email_status: DF.Check
		uidnext: DF.Int
		uidvalidity: DF.Data | None
		unreplied_for_mins: DF.Int
		use_imap: DF.Check
		use_ssl: DF.Check
		use_ssl_for_outgoing: DF.Check
		use_starttls: DF.Check
		use_tls: DF.Check
		validate_ssl_certificate: DF.Check
	# end: auto-generated types

	DOCTYPE = "Email Account"

	def autoname(self):
		"""Set name as `email_account_name` or make title from Email Address."""
		if not self.email_account_name:
			self.email_account_name = (
				self.email_id.split("@", 1)[0].replace("_", " ").replace(".", " ").replace("-", " ").title()
			)

		self.name = self.email_account_name

	def validate(self):
		"""Validate Email Address and check POP3/IMAP and SMTP connections is enabled."""

		if self.email_id:
			validate_email_address(self.email_id, True)

		if self.login_id_is_different:
			if not self.login_id:
				frappe.throw(_("Login Id is required"))
		else:
			self.login_id = None

		if self.service == "Sendgrid":
			self.login_id = "apikey"

		if self.service == "Frappe Mail":
			self.use_imap = 0
			self.always_use_account_email_id_as_sender = 1

			if self.auth_method == "Basic" or self.get_oauth_token():
				self.validate_frappe_mail_settings()

		# validate the imap settings
		if self.enable_incoming and self.use_imap and len(self.imap_folder) <= 0:
			frappe.throw(_("You need to set one IMAP folder for {0}").format(frappe.bold(self.email_id)))

		if frappe.local.flags.in_patch or frappe.in_test:
			return

		use_oauth = self.auth_method == "OAuth"
		validate_oauth = use_oauth and not (self.is_new() and not self.get_oauth_token())
		self.use_starttls = cint(self.use_imap and self.use_starttls and not self.use_ssl)

		if use_oauth:
			# no need for awaiting password for oauth
			self.awaiting_password = 0
			self.password = None

		if (
			not frappe.local.flags.in_install
			and not self.awaiting_password
			and not self.service == "Frappe Mail"
		):
			if validate_oauth or self.password or self.smtp_server in ("127.0.0.1", "localhost"):
				if self.enable_incoming:
					self.get_incoming_server()
					self.no_failed = 0

				if self.enable_outgoing:
					self.validate_smtp_conn()
			else:
				if self.enable_incoming or (self.enable_outgoing and not self.no_smtp_authentication):
					if not use_oauth:
						frappe.throw(_("Password is required or select Awaiting Password"))

		if self.notify_if_unreplied:
			if not self.send_notification_to:
				frappe.throw(_("{0} is mandatory").format(self.meta.get_label("send_notification_to")))
			for e in self.get_unreplied_notification_emails():
				validate_email_address(e, True)

		if self.enable_incoming:
			for folder in self.imap_folder:
				if folder.append_to:
					valid_doctypes = [d[0] for d in get_append_to()]
					if folder.append_to not in valid_doctypes:
						frappe.throw(_("Append To can be one of {0}").format(comma_or(valid_doctypes)))

	@frappe.whitelist()
	def validate_frappe_mail_settings(self):
		if self.service == "Frappe Mail":
			frappe_mail_client = self.get_frappe_mail_client()
			frappe_mail_client.validate()

	def validate_smtp_conn(self):
		if not self.smtp_server:
			frappe.throw(_("SMTP Server is required"))

		server = self.get_smtp_server()
		return server.session

	def before_save(self):
		messages = []
		as_list = 1
		if not self.enable_incoming and self.default_incoming:
			self.default_incoming = False
			messages.append(
				_("{} has been disabled. It can only be enabled if {} is checked.").format(
					frappe.bold(_("Default Incoming")),
					frappe.bold(_("Enable Incoming")),
				)
			)
		if not self.enable_outgoing and self.default_outgoing:
			self.default_outgoing = False
			messages.append(
				_("{} has been disabled. It can only be enabled if {} is checked.").format(
					frappe.bold(_("Default Outgoing")),
					frappe.bold(_("Enable Outgoing")),
				)
			)
		if messages:
			if len(messages) == 1:
				(as_list, messages) = (0, messages[0])
			frappe.msgprint(
				messages,
				as_list=as_list,
				indicator="orange",
				title=_("Defaults Updated"),
			)

	def on_update(self):
		"""Check there is only one default of each type."""
		self.check_automatic_linking_email_account()
		self.there_must_be_only_one_default()
		setup_user_email_inbox(
			email_account=self.name,
			awaiting_password=self.awaiting_password,
			email_id=self.email_id,
			enable_outgoing=self.enable_outgoing,
			used_oauth=self.auth_method == "OAuth",
		)

	def clear_cache(self):
		super().clear_cache()
		frappe.client_cache.delete_value("automatic_linking_email")

	def there_must_be_only_one_default(self):
		"""If current Email Account is default, un-default all other accounts."""
		for field in ("default_incoming", "default_outgoing"):
			if not self.get(field):
				continue

			for email_account in frappe.get_all("Email Account", filters={field: 1}):
				if email_account.name == self.name:
					continue

				email_account = frappe.get_doc("Email Account", email_account.name)
				email_account.set(field, 0)
				email_account.save()

	@frappe.whitelist()
	def get_domain_values(self, domain: str):
		return frappe.db.get_value("Email Domain", domain, EMAIL_DOMAIN_FIELDS, as_dict=True)

	def get_incoming_server(self, in_receive=False, email_sync_rule="UNSEEN"):
		"""Return logged in POP3/IMAP connection object."""
		oauth_token = self.get_oauth_token()
		args = frappe._dict(
			{
				"email_account_name": self.email_account_name,
				"email_account": self.name,
				"host": self.email_server,
				"use_ssl": self.use_ssl,
				"use_starttls": self.use_starttls,
				"username": getattr(self, "login_id", None) or self.email_id,
				"use_imap": self.use_imap,
				"email_sync_rule": email_sync_rule,
				"incoming_port": get_port(self),
				"initial_sync_count": self.initial_sync_count or 100,
				"use_oauth": self.auth_method == "OAuth",
				"access_token": oauth_token.get_password("access_token") if oauth_token else None,
			}
		)

		if self.password:
			args.password = self.get_password()

		if not args.get("host"):
			frappe.throw(_("{0} is required").format("Email Server"))

		email_server = EmailServer(frappe._dict(args))
		self.check_email_server_connection(email_server, in_receive)

		if not in_receive and self.use_imap:
			email_server.imap.logout()

		return email_server

	def check_email_server_connection(self, email_server, in_receive):
		# tries to connect to email server and handles failure
		try:
			email_server.connect()

			# reset failed attempts count - do it after succesful connection
			self.set_failed_attempts_count(0)
		except (error_proto, imaplib.IMAP4.error) as e:
			message = cstr(e).lower().replace(" ", "")
			auth_error_codes = [
				"authenticationfailed",
				"loginfailed",
			]

			other_error_codes = [
				"err[auth]",
				"errtemporaryerror",
				"loginviayourwebbrowser",
			]

			all_error_codes = auth_error_codes + other_error_codes

			if in_receive and any(map(lambda t: t in message, all_error_codes)):
				# if called via self.receive and it leads to authentication error,
				# disable incoming and send email to System Manager
				error_message = _(
					"Authentication failed while receiving emails from Email Account: {0}."
				).format(self.name)

				error_message = _("Email Account Disabled.") + " " + error_message
				error_message += "<br>" + _("Message from server: {0}").format(cstr(e))
				self.handle_incoming_connect_error(description=error_message)
				return None

			elif not in_receive and any(map(lambda t: t in message, auth_error_codes)):
				SMTPServer.throw_invalid_credentials_exception()
			else:
				frappe.throw(cstr(e))

		except OSError:
			if in_receive:
				# timeout while connecting, see receive.py connect method
				description = frappe.message_log.pop() if frappe.message_log else "Socket Error"
				self.db_set("no_failed", self.no_failed + 1)
				if self.no_failed > 2:
					self.handle_incoming_connect_error(description=description)
				return

			raise

	@property
	def _password(self):
		raise_exception = not (self.auth_method == "OAuth" or self.no_smtp_authentication or frappe.in_test)
		return self.get_password(raise_exception=raise_exception)

	@property
	def default_sender(self):
		return email.utils.formataddr((self.name, self.get("email_id")))

	def is_exists_in_db(self):
		"""Some of the Email Accounts we create from configs and those doesn't exists in DB.
		This is is to check the specific email account exists in DB or not.
		"""
		return self.find_one_by_filters(name=self.name)

	@classmethod
	def from_record(cls, record):
		email_account = frappe.new_doc(cls.DOCTYPE)
		email_account.update(record)
		return email_account

	@classmethod
	def find(cls, name):
		return frappe.get_doc(cls.DOCTYPE, name)

	@classmethod
	def find_one_by_filters(cls, **kwargs) -> "EmailAccount":
		name = frappe.db.get_value(cls.DOCTYPE, kwargs)
		return cls.find(name) if name else None

	@classmethod
	def find_from_config(cls):
		config = cls.get_account_details_from_site_config()
		if config:
			account = cls.from_record(config)
			account._from_site_config = True
			return account

	@classmethod
	def create_dummy(cls):
		return cls.from_record({"sender": "notifications@example.com"})

	@classmethod
	@cache_email_account("outgoing_email_account")
	def find_outgoing(cls, match_by_email=None, match_by_doctype=None, _raise_error=False):
		"""Find the outgoing Email account to use.

		:param match_by_email: Find account using emailID
		:param match_by_doctype: Find account by matching `Append To` doctype
		:param _raise_error: This is used by raise_error_on_no_output decorator to raise error.
		"""
		if match_by_email:
			match_by_email = parse_addr(match_by_email)[1]
			doc = cls.find_one_by_filters(enable_outgoing=1, email_id=match_by_email)
			if doc:
				return {match_by_email: doc}

		if match_by_doctype:
			doc = cls.find_one_by_filters(enable_outgoing=1, enable_incoming=1, append_to=match_by_doctype)
			if doc:
				return {match_by_doctype: doc}

		doc = cls.find_default_outgoing()
		if doc:
			return {"default": doc}

		if _raise_error:
			frappe.throw(
				_("Please setup default outgoing Email Account from Tools > Email Account"),
				frappe.OutgoingEmailError,
			)

	@classmethod
	def find_default_outgoing(cls):
		"""Find default outgoing account."""
		doc = cls.find_one_by_filters(enable_outgoing=1, default_outgoing=1)
		doc = doc or cls.find_from_config()
		return doc or (are_emails_muted() and cls.create_dummy())

	@classmethod
	def find_incoming(cls, match_by_email=None, match_by_doctype=None):
		"""Find the incoming Email account to use.
		:param match_by_email: Find account using emailID
		:param match_by_doctype: Find account by matching `Append To` doctype
		"""
		doc = cls.find_one_by_filters(enable_incoming=1, email_id=match_by_email)
		if doc:
			return doc

		doc = cls.find_one_by_filters(enable_incoming=1, append_to=match_by_doctype)
		if doc:
			return doc

		doc = cls.find_default_incoming()
		return doc

	@classmethod
	def find_default_incoming(cls):
		return cls.find_one_by_filters(enable_incoming=1, default_incoming=1)

	@classmethod
	def get_account_details_from_site_config(cls):
		if not frappe.conf.get("mail_server"):
			return {}

		field_to_conf_name_map = {
			"smtp_server": {"conf_names": ("mail_server",)},
			"smtp_port": {"conf_names": ("mail_port",)},
			"use_tls": {"conf_names": ("use_tls", "mail_login")},
			"login_id": {"conf_names": ("mail_login",)},
			"email_id": {
				"conf_names": ("auto_email_id", "mail_login"),
				"default": "notifications@example.com",
			},
			"password": {"conf_names": ("mail_password",)},
			"always_use_account_email_id_as_sender": {
				"conf_names": ("always_use_account_email_id_as_sender",),
				"default": 0,
			},
			"always_use_account_name_as_sender_name": {
				"conf_names": ("always_use_account_name_as_sender_name",),
				"default": 0,
			},
			"name": {"conf_names": ("email_sender_name",), "default": "Frappe"},
			"auth_method": {"conf_names": ("auth_method"), "default": "Basic"},
			"from_site_config": {"default": True},
			"no_smtp_authentication": {
				"conf_names": ("disable_mail_smtp_authentication",),
				"default": 0,
			},
		}

		account_details = {}
		for doc_field_name, d in field_to_conf_name_map.items():
			conf_names, default = d.get("conf_names") or [], d.get("default")
			value = [frappe.conf.get(k) for k in conf_names if frappe.conf.get(k)]
			account_details[doc_field_name] = (value and value[0]) or default

		return account_details

	def get_access_token(self) -> str | None:
		oauth_token = self.get_oauth_token()
		return oauth_token.get_password("access_token") if oauth_token else None

	def sendmail_config(self):
		return {
			"email_account": self.name,
			"server": self.smtp_server,
			"port": cint(self.smtp_port),
			"login": getattr(self, "login_id", None) or self.email_id,
			"password": self._password,
			"use_ssl": cint(self.use_ssl_for_outgoing),
			"use_tls": cint(self.use_tls),
			"use_oauth": self.auth_method == "OAuth",
			"access_token": self.get_access_token(),
		}

	def get_smtp_server(self):
		"""Get SMTPServer (wrapper around actual smtplib object) for this account.

		Implementation Detail: Since SMTPServer is same for each email connection, the same *instance*
		is returned every time this function is called from same EmailAccount object.
		This enables reusabilty of connection for better performance."""
		return self._smtp_server_instance

	@functools.cached_property
	def _smtp_server_instance(self):
		config = self.sendmail_config()
		return SMTPServer(**config)

	def get_frappe_mail_client(self):
		return self._frappe_mail_client

	@functools.cached_property
	def _frappe_mail_client(self):
		if self.auth_method == "OAuth":
			if access_token := self.get_access_token():
				return FrappeMail(self.frappe_mail_site, self.email_id, access_token=access_token)

			frappe.throw(
				_("Please Authorize OAuth for Email Account {0}").format(
					frappe.bold(self.email_account_name)
				),
				title=_("Frappe Mail OAuth Error"),
			)
		else:
			return FrappeMail(
				self.frappe_mail_site, self.email_id, self.api_key, self.get_password("api_secret")
			)

	def remove_unpicklable_values(self, state):
		super().remove_unpicklable_values(state)
		state.pop("_smtp_server_instance", None)

	def handle_incoming_connect_error(self, description):
		if self.get_failed_attempts_count() > 5:
			# This is done in background to avoid committing here.
			frappe.enqueue(self._disable_broken_incoming_account, description=description)
		else:
			self.set_failed_attempts_count(self.get_failed_attempts_count() + 1)

	def _disable_broken_incoming_account(self, description):
		if frappe.in_test:
			return
		self.db_set("enable_incoming", 0)

		users = get_system_managers(only_name=True)
		notification = {
			"document_type": self.doctype,
			"document_name": self.name,
			"subject": description,
			"from_user": "Administrator",
			"email_header": _("Email Account {0} Disabled").format(self.email_id or self.name),
		}
		enqueue_create_notification(users, notification)

	def set_failed_attempts_count(self, value):
		frappe.cache.set_value(
			f"{self.name}:email-account-failed-attempts", value, expires_in_sec=2 * 60 * 60
		)

	def get_failed_attempts_count(self):
		return cint(frappe.cache.get_value(f"{self.name}:email-account-failed-attempts"))

	def receive(self):
		"""Called by scheduler to receive emails from this EMail account using POP3/IMAP."""
		exceptions = []
		inbound_mails = self.get_inbound_mails()
		for mail in inbound_mails:
			try:
				communication = mail.process()
				frappe.db.commit()
				# If email already exists in the system
				# then do not send notifications for the same email.
				if communication and mail.flags.is_new_communication:
					# notify all participants of this thread
					if self.enable_auto_reply:
						self.send_auto_reply(communication, mail)

					communication.send_email(is_inbound_mail_communcation=True)
			except SentEmailInInboxError:
				frappe.db.rollback()
			except Exception:
				frappe.db.rollback()
				try:
					self.log_error(title="EmailAccount.receive")
					if self.use_imap:
						self.handle_bad_emails(mail.uid, mail.raw_message, frappe.get_traceback())
					exceptions.append(frappe.get_traceback())
				except Exception:
					frappe.db.rollback()
				else:
					frappe.db.commit()
			else:
				frappe.db.commit()

		if exceptions:
			raise Exception(frappe.as_json(exceptions))

	def get_inbound_mails(self) -> list[InboundMail]:
		"""retrive and return inbound mails."""
		mails = []

		def process_mail(messages, append_to=None):
			for index, message in enumerate(messages.get("latest_messages", [])):
				uid = messages["uid_list"][index] if messages.get("uid_list") else None
				seen_status = messages.get("seen_status", {}).get(uid)
				if self.email_sync_option != "UNSEEN" or seen_status != "SEEN":
					# only append the emails with status != 'SEEN' if sync option is set to 'UNSEEN'
					mails.append(
						InboundMail(
							message,
							self,
							frappe.safe_decode(uid),
							seen_status,
							append_to,
						)
					)

		if not self.enable_incoming:
			return []

		try:
			if self.service == "Frappe Mail":
				frappe_mail_client = self.get_frappe_mail_client()
				messages = frappe_mail_client.pull_raw(last_synced_at=self.last_synced_at)
				process_mail(messages)
				self.db_set("last_synced_at", messages["last_synced_at"], update_modified=False)
			else:
				email_sync_rule = self.build_email_sync_rule()
				email_server = self.get_incoming_server(in_receive=True, email_sync_rule=email_sync_rule)
				if self.use_imap:
					# process all given imap folder
					for folder in self.imap_folder:
						if email_server.select_imap_folder(folder.folder_name):
							email_server.settings["uid_validity"] = folder.uidvalidity
							messages = email_server.get_messages(folder=f'"{folder.folder_name}"') or {}
							process_mail(messages, folder.append_to)
				else:
					# process the pop3 account
					messages = email_server.get_messages() or {}
					process_mail(messages)

				# close connection to mailserver
				email_server.logout()
		except Exception:
			self.log_error(title=_("Error while connecting to email account {0}").format(self.name))
			return []

		return mails

	def handle_bad_emails(self, uid, raw, reason):
		"""Save the email in Unhandled Email doctype.

		The excessive encoding and decoding is done to handle the case where the
		email contains invalid characters. This should fail when parsing, not
		when storing the email in the database.
		"""
		if cint(self.use_imap):
			import email

			try:
				if isinstance(raw, bytes):
					raw_str = raw.decode("ASCII", "replace")
					mail = email.message_from_string(raw_str)
				else:
					raw_str = raw.encode(errors="replace").decode()
					mail = email.message_from_string(raw_str)

				message_id = mail.get("Message-ID")
			except Exception:
				raw_str = "can't be parsed"
				message_id = "can't be parsed"

			unhandled_email = frappe.get_doc(
				{
					"raw": raw_str,
					"uid": uid,
					"reason": reason,
					"message_id": message_id,
					"doctype": "Unhandled Email",
					"email_account": self.name,
				}
			)
			unhandled_email.insert(ignore_permissions=True)
			frappe.db.commit()

	def send_auto_reply(self, communication, email):
		"""Send auto reply if set."""
		from frappe.core.doctype.communication.email import (
			set_incoming_outgoing_accounts,
		)

		if self.enable_auto_reply:
			set_incoming_outgoing_accounts(communication)

			unsubscribe_message = (self.send_unsubscribe_message and _("Leave this conversation")) or ""

			frappe.sendmail(
				recipients=[email.from_email],
				sender=self.email_id,
				reply_to=communication.incoming_email_account,
				subject=" ".join([_("Re:"), communication.subject]),
				content=render_template(self.auto_reply_message or "", communication.as_dict())
				or frappe.get_template("templates/emails/auto_reply.html").render(communication.as_dict()),
				reference_doctype=communication.reference_doctype,
				reference_name=communication.reference_name,
				in_reply_to=email.mail.get("Message-Id"),  # send back the Message-Id as In-Reply-To
				unsubscribe_message=unsubscribe_message,
			)

	def get_unreplied_notification_emails(self):
		"""Return list of emails listed"""
		self.send_notification_to = self.send_notification_to.replace(",", "\n")
		return [e.strip() for e in self.send_notification_to.split("\n") if e.strip()]

	def on_trash(self):
		"""Clear communications where email account is linked"""
		Communication = frappe.qb.DocType("Communication")
		frappe.qb.update(Communication).set(Communication.email_account, "").where(
			Communication.email_account == self.name
		).run()

		remove_user_email_inbox(email_account=self.name)

	def after_rename(self, old, new, merge=False):
		frappe.db.set_value("Email Account", new, "email_account_name", new)

	def build_email_sync_rule(self):
		if not self.use_imap:
			return "UNSEEN"

		if self.email_sync_option == "ALL":
			max_uid = get_max_email_uid(self.name)
			last_uid = max_uid + int(self.initial_sync_count or 100) if max_uid == 1 else "*"
			return f"UID {max_uid}:{last_uid}"
		else:
			return self.email_sync_option or "UNSEEN"

	def check_automatic_linking_email_account(self):
		if self.enable_automatic_linking:
			if not self.enable_incoming:
				frappe.throw(_("Automatic Linking can be activated only if Incoming is enabled."))

			if frappe.db.exists(
				"Email Account",
				{"enable_automatic_linking": 1, "name": ("!=", self.name)},
			):
				frappe.throw(_("Automatic Linking can be activated only for one Email Account."))

	def append_email_to_sent_folder(self, message):
		if not (self.enable_incoming and self.use_imap):
			# don't try appending if enable incoming and imap is not set
			return

		try:
			email_server = self.get_incoming_server(in_receive=True)
			message = safe_encode(message)
			sent_folder_name = self.sent_folder_name or "Sent"
			email_server.imap.append(
				sent_folder_name, "\\Seen", imaplib.Time2Internaldate(time.time()), message
			)
		except Exception:
			self.log_error("Unable to add to Sent folder")

	def get_oauth_token(self):
		if self.auth_method == "OAuth":
			connected_app = frappe.get_doc("Connected App", self.connected_app)
			if self.backend_app_flow:
				token = connected_app.get_backend_app_token()
			else:
				token = connected_app.get_active_token(self.connected_user)

			return token


@frappe.whitelist()
def get_append_to(doctype=None, txt=None, searchfield=None, start=None, page_len=None, filters=None):
	txt = txt if txt else ""

	filters = {"istable": 0, "issingle": 0, "email_append_to": 1}
	# Set Email Append To DocTypes via DocType
	email_append_to_list = [
		dt.name for dt in frappe.get_all("DocType", filters=filters, fields=["name", "email_append_to"])
	]
	# Set Email Append To DocTypes set via Customize Form
	email_append_to_list.extend(
		dt.doc_type
		for dt in frappe.get_list(
			"Property Setter",
			filters={"property": "email_append_to", "value": 1},
			fields=["doc_type"],
		)
	)
	return [[d] for d in set(email_append_to_list) if txt in d]


def notify_unreplied():
	"""Sends email notifications if there are unreplied Communications
	and `notify_if_unreplied` is set as true."""
	for email_account in frappe.get_all(
		"Email Account",
		"name",
		filters={"enable_incoming": 1, "notify_if_unreplied": 1},
	):
		email_account = frappe.get_doc("Email Account", email_account.name)

		if email_account.use_imap:
			append_to = [folder.get("append_to") for folder in email_account.imap_folder]
		else:
			append_to = email_account.append_to

		if append_to:
			# get open communications younger than x mins, for given doctype
			for comm in frappe.get_all(
				"Communication",
				"name",
				filters=[
					{"sent_or_received": "Received"},
					{"reference_doctype": ("in", append_to)},
					{"unread_notification_sent": 0},
					{"email_account": email_account.name},
					{
						"creation": (
							"<",
							datetime.now() - timedelta(seconds=(email_account.unreplied_for_mins or 30) * 60),
						)
					},
					{
						"creation": (
							">",
							datetime.now()
							- timedelta(seconds=(email_account.unreplied_for_mins or 30) * 60 * 3),
						)
					},
				],
			):
				comm = frappe.get_doc("Communication", comm.name)

				if frappe.db.get_value(comm.reference_doctype, comm.reference_name, "status") == "Open":
					# if status is still open
					frappe.sendmail(
						recipients=email_account.get_unreplied_notification_emails(),
						content=comm.content,
						subject=comm.subject,
						doctype=comm.reference_doctype,
						name=comm.reference_name,
					)

				# update flag
				comm.db_set("unread_notification_sent", 1)


def pull(now=False):
	"""Will be called via scheduler, pull emails from all enabled Email accounts."""
	from frappe.integrations.doctype.connected_app.connected_app import has_token

	doctype = frappe.qb.DocType("Email Account")
	email_accounts = (
		frappe.qb.from_(doctype)
		.select(
			doctype.name,
			doctype.auth_method,
			doctype.backend_app_flow,
			doctype.connected_app,
			doctype.connected_user,
		)
		.where(doctype.enable_incoming == 1)
		.where(doctype.awaiting_password == 0)
		.run(as_dict=1)
	)

	for email_account in email_accounts:
		if (
			email_account.auth_method == "OAuth"
			and not email_account.backend_app_flow
			and not has_token(email_account.connected_app, email_account.connected_user)
		):
			# don't try to pull from accounts which dont have access token (for Oauth)
			continue

		if now:
			pull_from_email_account(email_account.name)

		else:
			# job_name is used to prevent duplicates in queue
			job_name = f"pull_from_email_account|{email_account.name}"

			queued_jobs = get_jobs(site=frappe.local.site, key="job_name")[frappe.local.site]
			if job_name not in queued_jobs:
				enqueue(
					pull_from_email_account,
					"short",
					event="all",
					job_name=job_name,
					email_account=email_account.name,
				)


@frappe.whitelist()
def pull_emails(email_account: str) -> None:
	"""Pull emails from given email account."""
	frappe.has_permission("Email Account", "read", throw=True)

	job_name = f"pull_from_email_account|{email_account}"
	queued_jobs = get_jobs(site=frappe.local.site, key="job_name")[frappe.local.site]

	if job_name not in queued_jobs:
		pull_from_email_account(email_account)
	else:
		frappe.msgprint(_("Emails are already being pulled from this account."))


def pull_from_email_account(email_account):
	"""Runs within a worker process"""
	email_account = frappe.get_doc("Email Account", email_account)
	email_account.receive()


def get_max_email_uid(email_account):
	"""get maximum uid of emails"""

	if result := frappe.get_all(
		"Communication",
		filters={
			"communication_medium": "Email",
			"sent_or_received": "Received",
			"email_account": email_account,
		},
		fields=["max(uid) as uid"],
	):
		return cint(result[0].get("uid", 0)) + 1
	return 1


def setup_user_email_inbox(email_account, awaiting_password, email_id, enable_outgoing, used_oauth):
	"""setup email inbox for user"""
	from frappe.core.doctype.user.user import ask_pass_update

	def add_user_email(user):
		user = frappe.get_doc("User", user)
		row = user.append("user_emails", {})

		row.email_id = email_id
		row.email_account = email_account
		row.awaiting_password = awaiting_password or 0
		row.used_oauth = used_oauth or 0
		row.enable_outgoing = enable_outgoing or 0

		user.save(ignore_permissions=True)

	update_user_email_settings = False
	if not all([email_account, email_id]):
		return

	user_names = frappe.db.get_values("User", {"email": email_id}, as_dict=True)
	if not user_names:
		return

	for user in user_names:
		user_name = user.get("name")

		# check if inbox is alreay configured
		user_inbox = (
			frappe.db.get_value(
				"User Email",
				{"email_account": email_account, "parent": user_name},
				["name"],
			)
			or None
		)

		if not user_inbox:
			add_user_email(user_name)
		else:
			# update awaiting password for email account
			update_user_email_settings = True

	if update_user_email_settings:
		UserEmail = frappe.qb.DocType("User Email")
		frappe.qb.update(UserEmail).set(UserEmail.awaiting_password, (awaiting_password or 0)).set(
			UserEmail.enable_outgoing, (enable_outgoing or 0)
		).set(UserEmail.used_oauth, (used_oauth or 0)).where(UserEmail.email_account == email_account).run()

	else:
		users = " and ".join([frappe.bold(user.get("name")) for user in user_names])
		frappe.msgprint(_("Enabled email inbox for user {0}").format(users))
	ask_pass_update()


def remove_user_email_inbox(email_account):
	"""remove user email inbox settings if email account is deleted"""
	if not email_account:
		return

	users = frappe.get_all(
		"User Email",
		filters={"email_account": email_account},
		fields=["parent as name"],
	)

	for user in users:
		doc = frappe.get_doc("User", user.get("name"))
		to_remove = [row for row in doc.user_emails if row.email_account == email_account]
		[doc.remove(row) for row in to_remove]

		doc.save(ignore_permissions=True)


@frappe.whitelist()
def set_email_password(email_account, password):
	account = frappe.get_doc("Email Account", email_account)
	if account.awaiting_password and account.auth_method != "OAuth":
		account.awaiting_password = 0
		account.password = password
		try:
			account.save(ignore_permissions=True)
		except Exception:
			frappe.db.rollback()
			return False

	return True


def get_automatic_email_link():
	def check_db():
		return frappe.db.get_value(
			"Email Account", {"enable_incoming": 1, "enable_automatic_linking": 1}, "email_id"
		)

	return frappe.client_cache.get_value("automatic_linking_email", generator=check_db)


def on_doctype_update() -> None:
	frappe.db.add_unique(
		"Email Account",
		["email_id", "enable_incoming", "enable_outgoing"],
		constraint_name="unique_email_account_type",
	)
