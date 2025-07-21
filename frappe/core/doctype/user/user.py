# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from collections.abc import Iterable
from datetime import timedelta

import frappe
import frappe.defaults
import frappe.permissions
import frappe.share
from frappe import STANDARD_USERS, _, msgprint, throw
from frappe.apps import get_default_path
from frappe.auth import MAX_PASSWORD_SIZE
from frappe.core.doctype.user_type.user_type import user_linked_with_permission_on_doctype
from frappe.desk.doctype.notification_settings.notification_settings import (
	create_notification_settings,
	toggle_notifications,
)
from frappe.desk.notifications import clear_notifications
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.rate_limiter import rate_limit
from frappe.sessions import clear_sessions
from frappe.utils import (
	cint,
	escape_html,
	flt,
	format_datetime,
	get_formatted_email,
	get_system_timezone,
	has_gravatar,
	now_datetime,
	today,
)
from frappe.utils.data import sha256_hash
from frappe.utils.html_utils import sanitize_html
from frappe.utils.password import check_password, get_password_reset_limit
from frappe.utils.password import update_password as _update_password
from frappe.utils.user import get_system_managers
from frappe.website.utils import get_home_page, is_signup_disabled

desk_properties = (
	"search_bar",
	"notifications",
	"list_sidebar",
	"bulk_actions",
	"view_switcher",
	"form_sidebar",
	"timeline",
	"dashboard",
)


class User(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.block_module.block_module import BlockModule
		from frappe.core.doctype.defaultvalue.defaultvalue import DefaultValue
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.core.doctype.user_email.user_email import UserEmail
		from frappe.core.doctype.user_role_profile.user_role_profile import UserRoleProfile
		from frappe.core.doctype.user_social_login.user_social_login import UserSocialLogin
		from frappe.types import DF

		allowed_in_mentions: DF.Check
		api_key: DF.Data | None
		api_secret: DF.Password | None
		banner_image: DF.AttachImage | None
		bio: DF.SmallText | None
		birth_date: DF.Date | None
		block_modules: DF.Table[BlockModule]
		bulk_actions: DF.Check
		bypass_restrict_ip_check_if_2fa_enabled: DF.Check
		code_editor_type: DF.Literal["vscode", "vim", "emacs"]
		dashboard: DF.Check
		default_app: DF.Literal[None]
		default_workspace: DF.Link | None
		defaults: DF.Table[DefaultValue]
		desk_theme: DF.Literal["Light", "Dark", "Automatic"]
		document_follow_frequency: DF.Literal["Hourly", "Daily", "Weekly"]
		document_follow_notify: DF.Check
		email: DF.Data
		email_signature: DF.TextEditor | None
		enabled: DF.Check
		first_name: DF.Data
		follow_assigned_documents: DF.Check
		follow_commented_documents: DF.Check
		follow_created_documents: DF.Check
		follow_liked_documents: DF.Check
		follow_shared_documents: DF.Check
		form_sidebar: DF.Check
		full_name: DF.Data | None
		gender: DF.Link | None
		home_settings: DF.Code | None
		interest: DF.SmallText | None
		language: DF.Link | None
		last_active: DF.Datetime | None
		last_ip: DF.ReadOnly | None
		last_known_versions: DF.Text | None
		last_login: DF.ReadOnly | None
		last_name: DF.Data | None
		last_password_reset_date: DF.Date | None
		last_reset_password_key_generated_on: DF.Datetime | None
		list_sidebar: DF.Check
		location: DF.Data | None
		login_after: DF.Int
		login_before: DF.Int
		logout_all_sessions: DF.Check
		middle_name: DF.Data | None
		mobile_no: DF.Data | None
		module_profile: DF.Link | None
		mute_sounds: DF.Check
		new_password: DF.Password | None
		notifications: DF.Check
		onboarding_status: DF.SmallText | None
		phone: DF.Data | None
		redirect_url: DF.SmallText | None
		reset_password_key: DF.Data | None
		restrict_ip: DF.SmallText | None
		role_profile_name: DF.Link | None
		role_profiles: DF.TableMultiSelect[UserRoleProfile]
		roles: DF.Table[HasRole]
		search_bar: DF.Check
		send_me_a_copy: DF.Check
		send_welcome_email: DF.Check
		show_absolute_datetime_in_timeline: DF.Check
		simultaneous_sessions: DF.Int
		social_logins: DF.Table[UserSocialLogin]
		thread_notify: DF.Check
		time_zone: DF.Autocomplete | None
		timeline: DF.Check
		unsubscribed: DF.Check
		user_emails: DF.Table[UserEmail]
		user_image: DF.AttachImage | None
		user_type: DF.Link | None
		username: DF.Data | None
		view_switcher: DF.Check
	# end: auto-generated types

	__new_password = None

	def __setup__(self):
		# because it is handled separately
		self.flags.ignore_save_passwords = ["new_password"]

	def autoname(self):
		"""set name as Email Address"""
		if self.get("is_admin") or self.get("is_guest"):
			self.name = self.first_name
		else:
			self.email = self.email.strip().lower()
			self.name = self.email

	def onload(self):
		from frappe.utils.modules import get_modules_from_all_apps

		self.set_onload("all_modules", sorted(m.get("module_name") for m in get_modules_from_all_apps()))

	def before_insert(self):
		self.flags.in_insert = True
		throttle_user_creation()

	def after_insert(self):
		create_notification_settings(self.name)
		frappe.cache.delete_key("users_for_mentions")
		frappe.cache.delete_key("enabled_users")

	def validate(self):
		# clear new password
		self.__new_password = self.new_password
		self.new_password = ""

		if not frappe.in_test:
			self.password_strength_test()

		if self.name not in STANDARD_USERS:
			self.email = self.name
			self.validate_email_type(self.name)

		self.move_role_profile_name_to_role_profiles()
		self.populate_role_profile_roles()
		self.check_roles_added()
		self.set_system_user()
		self.clean_name()
		self.set_full_name()
		self.check_enable_disable()
		self.ensure_unique_roles()
		self.ensure_unique_role_profiles()
		self.remove_all_roles_for_guest()
		self.validate_username()
		self.remove_disabled_roles()
		self.validate_user_email_inbox()
		if self.user_emails:
			ask_pass_update()
		self.validate_allowed_modules()
		self.validate_user_image()
		self.set_time_zone()
		if self.restrict_ip:
			self.validate_ip_addr()

		if self.language == "Loading...":
			self.language = None

		if (self.name not in ["Administrator", "Guest"]) and (not self.get_social_login_userid("frappe")):
			self.set_social_login_userid("frappe", frappe.generate_hash(length=39))

	def disable_email_fields_if_user_disabled(self):
		if not self.enabled:
			self.thread_notify = 0
			self.send_me_a_copy = 0
			self.allowed_in_mentions = 0

	@frappe.whitelist()
	def populate_role_profile_roles(self):
		if not self.role_profiles:
			return

		if self.name in STANDARD_USERS:
			self.role_profiles = []
			return

		new_roles = set()
		for role_profile in self.role_profiles:
			role_profile = frappe.get_cached_doc("Role Profile", role_profile.role_profile)
			new_roles.update(role.role for role in role_profile.roles)

		# Remove invalid roles and add new ones
		self.roles = [r for r in self.roles if r.role in new_roles]
		self.append_roles(*new_roles)

	def move_role_profile_name_to_role_profiles(self):
		"""This handles old role_profile_name field if programatically set.

		This behaviour will be remoed in future versions."""
		if not self.role_profile_name:
			return

		current_role_profiles = [r.role_profile for r in self.role_profiles]
		if self.role_profile_name in current_role_profiles:
			self.role_profile_name = None
			return

		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown",
			"v16",
			"The field `role_profile_name` is deprecated and will be removed in v16, use `role_profiles` child table instead.",
		)
		self.append("role_profiles", {"role_profile": self.role_profile_name})
		self.role_profile_name = None

	def validate_allowed_modules(self):
		if self.module_profile:
			module_profile = frappe.get_doc("Module Profile", self.module_profile)
			self.set("block_modules", [])
			for d in module_profile.get("block_modules"):
				self.append("block_modules", {"module": d.module})

	def validate_user_image(self):
		if self.user_image and len(self.user_image) > 2000:
			frappe.throw(_("Not a valid User Image."))

	def on_update(self):
		# clear new password
		self.share_with_self()
		clear_notifications(user=self.name)
		frappe.clear_cache(user=self.name)
		now = frappe.in_test or frappe.flags.in_install
		self.send_password_notification(self.__new_password)
		frappe.enqueue(
			"frappe.core.doctype.user.user.create_contact",
			user=self,
			ignore_mandatory=True,
			now=now,
			enqueue_after_commit=True,
		)

		if self.name not in STANDARD_USERS and not self.user_image:
			frappe.enqueue(
				"frappe.core.doctype.user.user.update_gravatar",
				name=self.name,
				now=now,
				enqueue_after_commit=True,
			)

		# Set user selected timezone
		if self.time_zone:
			frappe.defaults.set_default("time_zone", self.time_zone, self.name)

		if self.has_value_changed("language"):
			locale_keys = ("date_format", "time_format", "number_format", "first_day_of_the_week")
			if self.language:
				language = frappe.get_doc("Language", self.language)
				for key in locale_keys:
					value = language.get(key)
					if value:
						frappe.defaults.set_default(key, value, self.name)
			else:
				for key in locale_keys:
					frappe.defaults.clear_default(key, parent=self.name)

		if self.has_value_changed("enabled"):
			frappe.cache.delete_key("users_for_mentions")
			frappe.cache.delete_key("enabled_users")
		elif self.has_value_changed("allow_in_mentions") or self.has_value_changed("user_type"):
			frappe.cache.delete_key("users_for_mentions")

	def has_website_permission(self, ptype, user, verbose=False):
		"""Return True if current user is the session user."""
		return self.name == frappe.session.user

	def clean_name(self):
		for field in ("first_name", "middle_name", "last_name"):
			if field_value := self.get(field):
				self.set(field, sanitize_html(field_value, always_sanitize=True))

	def set_full_name(self):
		self.full_name = " ".join(filter(None, [self.first_name, self.last_name]))

	def check_enable_disable(self):
		# do not allow disabling administrator/guest
		if not cint(self.enabled) and self.name in STANDARD_USERS:
			frappe.throw(_("User {0} cannot be disabled").format(self.name))

		# clear sessions if disabled
		if not cint(self.enabled) and getattr(frappe.local, "login_manager", None):
			frappe.local.login_manager.logout(user=self.name)

		# toggle notifications based on the user's status
		toggle_notifications(self.name, enable=cint(self.enabled), ignore_permissions=True)
		self.disable_email_fields_if_user_disabled()

	def email_new_password(self, new_password=None):
		if new_password and not self.flags.in_insert:
			_update_password(user=self.name, pwd=new_password, logout_all_sessions=self.logout_all_sessions)

	def set_system_user(self):
		"""For the standard users like admin and guest, the user type is fixed."""
		user_type_mapper = {"Administrator": "System User", "Guest": "Website User"}

		if self.user_type and not frappe.get_cached_value("User Type", self.user_type, "is_standard"):
			if user_type_mapper.get(self.name):
				self.user_type = user_type_mapper.get(self.name)
			else:
				self.set_roles_and_modules_based_on_user_type()
		else:
			"""Set as System User if any of the given roles has desk_access"""
			self.user_type = "System User" if self.has_desk_access() else "Website User"

	def set_roles_and_modules_based_on_user_type(self):
		user_type_doc = frappe.get_cached_doc("User Type", self.user_type)
		if user_type_doc.role:
			self.roles = []

			# Check whether User has linked with the 'Apply User Permission On' doctype or not
			if user_linked_with_permission_on_doctype(user_type_doc, self.name):
				self.append("roles", {"role": user_type_doc.role})

				frappe.msgprint(
					_("Role has been set as per the user type {0}").format(self.user_type), alert=True
				)

		user_type_doc.update_modules_in_user(self)

	def has_desk_access(self):
		"""Return true if any of the set roles has desk access"""
		if not self.roles:
			return False

		role_table = DocType("Role")
		return frappe.db.count(
			role_table,
			((role_table.desk_access == 1) & (role_table.name.isin([d.role for d in self.roles]))),
		)

	def share_with_self(self):
		if self.name in STANDARD_USERS:
			return

		frappe.share.add_docshare(
			self.doctype, self.name, self.name, write=1, share=1, flags={"ignore_share_permission": True}
		)

	def validate_share(self, docshare):
		pass
		# if docshare.user == self.name:
		# 	if self.user_type=="System User":
		# 		if docshare.share != 1:
		# 			frappe.throw(_("Sorry! User should have complete access to their own record."))
		# 	else:
		# 		frappe.throw(_("Sorry! Sharing with Website User is prohibited."))

	def send_password_notification(self, new_password):
		try:
			if self.flags.in_insert:
				if self.name not in STANDARD_USERS:
					if new_password:
						# new password given, no email required
						_update_password(
							user=self.name, pwd=new_password, logout_all_sessions=self.logout_all_sessions
						)

					if (
						not self.flags.no_welcome_mail
						and cint(self.send_welcome_email)
						and not self.flags.email_sent
					):
						self.send_welcome_mail_to_user()
						self.flags.email_sent = 1
						if frappe.session.user != "Guest":
							msgprint(_("Welcome email sent"))
						return
			else:
				self.email_new_password(new_password)

		except frappe.OutgoingEmailError:
			frappe.clear_last_message()
			frappe.msgprint(
				_("Please setup default outgoing Email Account from Settings > Email Account"), alert=True
			)
			# email server not set, don't send email
			self.log_error("Unable to send new password notification")

	@Document.hook
	def validate_reset_password(self):
		pass

	def reset_password(self, send_email=False, password_expired=False):
		from frappe.utils import get_url

		key = frappe.generate_hash()
		hashed_key = sha256_hash(key)
		self.db_set("reset_password_key", hashed_key)
		self.db_set("last_reset_password_key_generated_on", now_datetime())

		url = "/update-password?key=" + key
		if password_expired:
			url = "/update-password?key=" + key + "&password_expired=true"

		link = get_url(url, allow_header_override=False)
		if send_email:
			self.password_reset_mail(link)

		return link

	def get_fullname(self):
		"""get first_name space last_name"""
		return (self.first_name or "") + ((self.first_name and " ") or "") + (self.last_name or "")

	def password_reset_mail(self, link):
		reset_password_template = frappe.db.get_system_setting("reset_password_template")

		self.send_login_mail(
			_("Password Reset"),
			"password_reset",
			{"link": link},
			now=True,
			custom_template=reset_password_template,
		)

	def send_welcome_mail_to_user(self):
		from frappe.utils import get_url

		link = self.reset_password()
		subject = None
		method = frappe.get_hooks("welcome_email")
		if method:
			subject = frappe.get_attr(method[-1])()
		if not subject:
			site_name = frappe.db.get_default("site_name") or frappe.get_conf().get("site_name")
			if site_name:
				subject = _("Welcome to {0}").format(site_name)
			else:
				subject = _("Complete Registration")

		welcome_email_template = frappe.db.get_system_setting("welcome_email_template")

		self.send_login_mail(
			subject,
			"new_user",
			dict(
				link=link,
				site_url=get_url(),
			),
			custom_template=welcome_email_template,
		)

	def send_login_mail(self, subject, template, add_args, now=None, custom_template=None):
		"""send mail with login details"""
		from frappe.utils import get_url
		from frappe.utils.user import get_user_fullname

		created_by = get_user_fullname(frappe.session["user"])
		if created_by == "Guest":
			created_by = "Administrator"

		args = {
			"first_name": self.first_name or self.last_name or "user",
			"user": self.name,
			"title": subject,
			"login_url": get_url(),
			"created_by": created_by,
		}

		args.update(add_args)

		sender = (
			frappe.session.user not in STANDARD_USERS and get_formatted_email(frappe.session.user)
		) or None

		if custom_template:
			from frappe.email.doctype.email_template.email_template import get_email_template

			email_template = get_email_template(custom_template, args)
			subject = email_template.get("subject")
			content = email_template.get("message")

		frappe.sendmail(
			recipients=self.email,
			sender=sender,
			subject=subject,
			template=template if not custom_template else None,
			content=content if custom_template else None,
			args=args,
			header=[subject, "green"],
			delayed=(not now) if now is not None else self.flags.delay_emails,
			retry=3,
		)

	def on_trash(self):
		frappe.clear_cache(user=self.name)
		if self.name in STANDARD_USERS:
			throw(_("User {0} cannot be deleted").format(self.name))

		# disable the user and log him/her out
		self.enabled = 0
		if getattr(frappe.local, "login_manager", None):
			frappe.local.login_manager.logout(user=self.name)

		# delete todos
		frappe.db.delete("ToDo", {"allocated_to": self.name})
		todo_table = DocType("ToDo")
		(
			frappe.qb.update(todo_table)
			.set(todo_table.assigned_by, None)
			.where(todo_table.assigned_by == self.name)
		).run()

		# delete events
		frappe.db.delete("Event", {"owner": self.name, "event_type": "Private"})

		# delete shares
		frappe.db.delete("DocShare", {"user": self.name})
		# unlink contact
		table = DocType("Contact")
		frappe.qb.update(table).where(table.user == self.name).set(table.user, None).run()

		# delete notification settings
		frappe.delete_doc("Notification Settings", self.name, ignore_permissions=True)

		if self.get("allow_in_mentions"):
			frappe.cache.delete_key("users_for_mentions")

		frappe.cache.delete_key("enabled_users")

		# delete user permissions
		frappe.db.delete("User Permission", {"user": self.name})

		# Delete OAuth data
		frappe.db.delete("OAuth Authorization Code", {"user": self.name})
		frappe.db.delete("Token Cache", {"user": self.name})

		# Remove user link from Workflow Action
		frappe.db.set_value("Workflow Action", {"user": self.name}, "user", None)

		# Delete user's List Filters
		frappe.db.delete("List Filter", {"for_user": self.name})

		# Remove user from Note's Seen By table
		seen_notes = frappe.get_all("Note", filters=[["Note Seen By", "user", "=", self.name]], pluck="name")
		for note_id in seen_notes:
			note = frappe.get_doc("Note", note_id)
			for row in note.seen_by:
				if row.user == self.name:
					note.remove(row)
			note.save(ignore_permissions=True)

	def before_rename(self, old_name, new_name, merge=False):
		# if merging, delete the old user notification settings
		if merge:
			frappe.delete_doc("Notification Settings", old_name, ignore_permissions=True)

		frappe.clear_cache(user=old_name)
		self.validate_rename(old_name, new_name)

	def validate_rename(self, old_name, new_name):
		# do not allow renaming administrator and guest
		if old_name in STANDARD_USERS:
			throw(_("User {0} cannot be renamed").format(self.name))

		self.validate_email_type(new_name)

	def validate_email_type(self, email):
		from frappe.utils import validate_email_address

		validate_email_address(email.strip(), True)

	def after_rename(self, old_name, new_name, merge=False):
		tables = frappe.db.get_tables()
		for tab in tables:
			desc = frappe.db.get_table_columns_description(tab)
			has_fields = [d.get("name") for d in desc if d.get("name") in ["owner", "modified_by"]]
			for field in has_fields:
				frappe.db.sql(
					"""UPDATE `{}`
					SET `{}` = {}
					WHERE `{}` = {}""".format(tab, field, "%s", field, "%s"),
					(new_name, old_name),
				)

		if frappe.db.exists("Notification Settings", old_name):
			frappe.rename_doc("Notification Settings", old_name, new_name, force=True, show_alert=False)

		# set email
		frappe.db.set_value("User", new_name, "email", new_name)

		clear_sessions(user=old_name, force=True)
		clear_sessions(user=new_name, force=True)

	def append_roles(self, *roles):
		"""Add roles to user"""
		current_roles = {d.role for d in self.get("roles")}
		for role in roles:
			if role in current_roles:
				continue
			self.append("roles", {"role": role})

	def add_roles(self, *roles):
		"""Add roles to user and save"""
		self.append_roles(*roles)
		# test_user_permission.create_user depends on this
		self.save()

	def remove_roles(self, *roles):
		existing_roles = {d.role: d for d in self.get("roles")}
		for role in roles:
			if role in existing_roles:
				self.get("roles").remove(existing_roles[role])

		self.save()

	def remove_all_roles_for_guest(self):
		if self.name == "Guest":
			self.set("roles", list({d for d in self.get("roles") if d.role == "Guest"}))

	def remove_disabled_roles(self):
		disabled_roles = [d.name for d in frappe.get_all("Role", filters={"disabled": 1})]
		for role in list(self.get("roles")):
			if role.role in disabled_roles:
				self.get("roles").remove(role)

	def ensure_unique_roles(self):
		exists = set()
		for d in list(self.roles):
			if (not d.role) or (d.role in exists):
				self.roles.remove(d)
			exists.add(d.role)

	def ensure_unique_role_profiles(self):
		seen = set()
		for rp in list(self.role_profiles):
			if rp.role_profile in seen:
				self.role_profiles.remove(rp)
			seen.add(rp.role_profile)

	def validate_username(self):
		if not self.username and self.is_new() and self.first_name:
			self.username = frappe.scrub(self.first_name)

		if not self.username:
			return

		# strip space and @
		self.username = self.username.strip(" @")

		if self.username_exists():
			if self.user_type == "System User":
				frappe.msgprint(_("Username {0} already exists").format(self.username))
				self.suggest_username()

			self.username = ""

	def password_strength_test(self):
		"""test password strength"""
		if self.flags.ignore_password_policy:
			return

		if self.__new_password:
			user_data = (self.first_name, self.middle_name, self.last_name, self.email, self.birth_date)
			result = test_password_strength(self.__new_password, user_data=user_data)
			feedback = result.get("feedback", None)

			if feedback and not feedback.get("password_policy_validation_passed", False):
				handle_password_test_fail(feedback)

	def suggest_username(self):
		def _check_suggestion(suggestion):
			if self.username != suggestion and not self.username_exists(suggestion):
				return suggestion

			return None

		# @firstname
		username = _check_suggestion(frappe.scrub(self.first_name))

		if not username:
			# @firstname_last_name
			username = _check_suggestion(frappe.scrub("{} {}".format(self.first_name, self.last_name or "")))

		if username:
			frappe.msgprint(_("Suggested Username: {0}").format(username))

		return username

	def username_exists(self, username=None):
		return frappe.db.get_value("User", {"username": username or self.username, "name": ("!=", self.name)})

	def get_blocked_modules(self):
		"""Return list of modules blocked for that user."""
		return [d.module for d in self.block_modules] if self.block_modules else []

	def validate_user_email_inbox(self):
		"""check if same email account added in User Emails twice"""

		email_accounts = [user_email.email_account for user_email in self.user_emails]
		if len(email_accounts) != len(set(email_accounts)):
			frappe.throw(_("Email Account added multiple times"))

	def get_social_login_userid(self, provider: str):
		try:
			for p in self.social_logins:
				if p.provider == provider:
					return p.userid
		except Exception:
			return None

	def set_social_login_userid(self, provider, userid, username=None):
		social_logins = {"provider": provider, "userid": userid}

		if username:
			social_logins["username"] = username

		self.append("social_logins", social_logins)

	def get_restricted_ip_list(self):
		return get_restricted_ip_list(self)

	@classmethod
	def find_by_credentials(cls, user_name: str, password: str, validate_password: bool = True):
		"""Find the user by credentials.

		This is a login utility that needs to check login related system settings while finding the user.
		1. Find user by email ID by default
		2. If allow_login_using_mobile_number is set, you can use mobile number while finding the user.
		3. If allow_login_using_user_name is set, you can use username while finding the user.
		"""

		login_with_mobile = cint(frappe.get_system_settings("allow_login_using_mobile_number"))
		login_with_username = cint(frappe.get_system_settings("allow_login_using_user_name"))

		or_filters = [{"name": user_name}]
		if login_with_mobile:
			or_filters.append({"mobile_no": user_name})
		if login_with_username:
			or_filters.append({"username": user_name})

		users = frappe.get_all("User", fields=["name", "enabled"], or_filters=or_filters, limit=1)
		if not users:
			return

		user = users[0]
		user["is_authenticated"] = True
		if validate_password:
			try:
				check_password(user["name"], password, delete_tracker_cache=False)
			except frappe.AuthenticationError:
				user["is_authenticated"] = False

		return user

	def set_time_zone(self):
		if not self.time_zone:
			self.time_zone = get_system_timezone()

	def get_permission_log_options(self, event=None):
		return {"fields": ("role_profile_name", "roles", "module_profile", "block_modules")}

	def check_roles_added(self):
		if self.user_type != "System User" or self.roles or not self.is_new():
			return

		frappe.msgprint(
			_("Newly created user {0} has no roles enabled.").format(frappe.bold(self.name)),
			title=_("No Roles Specified"),
			indicator="orange",
			primary_action={
				"label": _("Add Roles"),
				"client_action": "frappe.set_route",
				"args": ["Form", self.doctype, self.name],
			},
		)

	def validate_ip_addr(self):
		self.restrict_ip = ",".join(self.get_restricted_ip_list())


@frappe.whitelist()
def get_timezones():
	import zoneinfo

	return {"timezones": zoneinfo.available_timezones()}


@frappe.whitelist()
def get_all_roles():
	"""return all roles"""
	active_domains = frappe.get_active_domains()

	roles = frappe.get_all(
		"Role",
		filters={
			"name": ("not in", frappe.permissions.AUTOMATIC_ROLES),
			"disabled": 0,
		},
		or_filters={"ifnull(restrict_to_domain, '')": "", "restrict_to_domain": ("in", active_domains)},
		order_by="name",
	)

	return sorted([role.get("name") for role in roles])


@frappe.whitelist()
def get_roles(arg=None):
	"""get roles for a user"""
	return frappe.get_roles(frappe.form_dict.get("uid", frappe.session.user))


@frappe.whitelist()
def get_perm_info(role):
	"""get permission info"""
	from frappe.permissions import get_all_perms

	return get_all_perms(role)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_password(
	new_password: str, logout_all_sessions: int = 0, key: str | None = None, old_password: str | None = None
):
	"""Update password for the current user.

	Args:
	    new_password (str): New password.
	    logout_all_sessions (int, optional): If set to 1, all other sessions will be logged out. Defaults to 0.
	    key (str, optional): Password reset key. Defaults to None.
	    old_password (str, optional): Old password. Defaults to None.
	"""

	if len(new_password) > MAX_PASSWORD_SIZE:
		frappe.throw(_("Password size exceeded the maximum allowed size."))

	result = test_password_strength(new_password)
	feedback = result.get("feedback", None)

	if feedback and not feedback.get("password_policy_validation_passed", False):
		handle_password_test_fail(feedback)

	res = _get_user_for_update_password(key, old_password)
	if res.get("message"):
		frappe.local.response.http_status_code = 410
		return res["message"]
	else:
		user = res["user"]

	logout_all_sessions = cint(logout_all_sessions) or frappe.get_system_settings("logout_on_password_reset")
	_update_password(user, new_password, logout_all_sessions=cint(logout_all_sessions))

	user_doc, redirect_url = reset_user_data(user)

	user_doc.validate_reset_password()

	# get redirect url from cache
	redirect_to = frappe.cache.hget("redirect_after_login", user)
	if redirect_to:
		redirect_url = redirect_to
		frappe.cache.hdel("redirect_after_login", user)

	frappe.local.login_manager.login_as(user)

	frappe.db.set_value("User", user, "last_password_reset_date", today())
	frappe.db.set_value("User", user, "reset_password_key", "")

	if user_doc.user_type == "System User":
		return get_default_path() or "/app"
	else:
		return redirect_url or get_default_path() or get_home_page()


@frappe.whitelist(allow_guest=True)
def test_password_strength(new_password: str, key=None, old_password=None, user_data: tuple | None = None):
	from frappe.utils.password_strength import test_password_strength as _test_password_strength

	if key is not None or old_password is not None:
		from frappe.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown",
			"v17",
			"Arguments `key` and `old_password` are deprecated in function `test_password_strength`.",
		)

	enable_password_policy = frappe.get_system_settings("enable_password_policy")

	if not enable_password_policy:
		return {}

	if not user_data:
		user_data = frappe.db.get_value(
			"User", frappe.session.user, ["first_name", "middle_name", "last_name", "email", "birth_date"]
		)

	if new_password:
		result = _test_password_strength(new_password, user_inputs=user_data)
		password_policy_validation_passed = False
		minimum_password_score = cint(frappe.get_system_settings("minimum_password_score"))

		# score should be greater than 0 and minimum_password_score
		if result.get("score") and result.get("score") >= minimum_password_score:
			password_policy_validation_passed = True

		result["feedback"]["password_policy_validation_passed"] = password_policy_validation_passed
		result.pop("password", None)
		return result


@frappe.whitelist()
def has_email_account(email: str):
	return frappe.get_list("Email Account", filters={"email_id": email})


@frappe.whitelist(allow_guest=False)
def get_email_awaiting(user):
	return frappe.get_all(
		"User Email",
		fields=["email_account", "email_id"],
		filters={"awaiting_password": 1, "parent": user, "used_oauth": 0},
	)


def ask_pass_update():
	# update the sys defaults as to awaiting users
	from frappe.utils import set_default

	password_list = frappe.get_all(
		"User Email", filters={"awaiting_password": 1, "used_oauth": 0}, pluck="parent", distinct=True
	)
	set_default("email_user_password", ",".join(password_list))


def _get_user_for_update_password(key, old_password):
	# verify old password
	result = frappe._dict()
	if key:
		hashed_key = sha256_hash(key)
		user = frappe.db.get_value(
			"User", {"reset_password_key": hashed_key}, ["name", "last_reset_password_key_generated_on"]
		)
		result.user, last_reset_password_key_generated_on = user or (None, None)
		if result.user:
			reset_password_link_expiry = cint(
				frappe.get_system_settings("reset_password_link_expiry_duration")
			)
			if (
				reset_password_link_expiry
				and now_datetime()
				> last_reset_password_key_generated_on + timedelta(seconds=reset_password_link_expiry)
			):
				result.message = _("The reset password link has been expired")
		else:
			result.message = _("The reset password link has either been used before or is invalid")
	elif old_password:
		# verify old password
		frappe.local.login_manager.check_password(frappe.session.user, old_password)
		user = frappe.session.user
		result.user = user
	return result


def reset_user_data(user):
	user_doc = frappe.get_doc("User", user)
	redirect_url = user_doc.redirect_url
	user_doc.reset_password_key = ""
	user_doc.redirect_url = ""
	user_doc.save(ignore_permissions=True)

	return user_doc, redirect_url


@frappe.whitelist(methods=["POST"])
def verify_password(password):
	frappe.local.login_manager.check_password(frappe.session.user, password)


@frappe.whitelist(allow_guest=True)
def sign_up(email: str, full_name: str, redirect_to: str) -> tuple[int, str]:
	if is_signup_disabled():
		frappe.throw(_("Sign Up is disabled"), title=_("Not Allowed"))

	user = frappe.db.get("User", {"email": email})
	if user:
		if user.enabled:
			return 0, _("Already Registered")
		else:
			return 0, _("Registered but disabled")
	else:
		if frappe.db.get_creation_count("User", 60) > 300:
			frappe.respond_as_web_page(
				_("Temporarily Disabled"),
				_(
					"Too many users signed up recently, so the registration is disabled. Please try back in an hour"
				),
				http_status_code=429,
			)

		from frappe.utils import random_string

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": escape_html(full_name),
				"enabled": 1,
				"new_password": random_string(10),
				"user_type": "Website User",
			}
		)
		user.flags.ignore_permissions = True
		user.flags.ignore_password_policy = True
		user.insert()

		# set default signup role as per Portal Settings
		default_role = frappe.get_single_value("Portal Settings", "default_role")
		if default_role:
			user.add_roles(default_role)

		if redirect_to:
			frappe.cache.hset("redirect_after_login", user.name, redirect_to)

		if user.flags.email_sent:
			return 1, _("Please check your email for verification")
		else:
			return 2, _("Please ask your administrator to verify your sign-up")


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=get_password_reset_limit, seconds=60 * 60)
def reset_password(user: str) -> str:
	try:
		user: User = frappe.get_doc("User", user)
		if user.name == "Administrator":
			return "not allowed"
		if not user.enabled:
			return "disabled"

		user.validate_reset_password()
		user.reset_password(send_email=True)

		return frappe.msgprint(
			msg=_("Password reset instructions have been sent to {}'s email").format(user.full_name),
			title=_("Password Email Sent"),
		)
	except frappe.DoesNotExistError:
		frappe.local.response["http_status_code"] = 404
		frappe.clear_messages()
		return "not found"


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def user_query(doctype, txt, searchfield, start, page_len, filters):
	doctype = "User"

	list_filters = {
		"enabled": 1,
		"docstatus": ["<", 2],
	}

	# Check if we have a search term, and decide the filters depending on the search term
	or_filters = [[searchfield, "like", f"%{txt}%"]]
	if "name" in searchfield:
		or_filters += [[field, "like", f"%{txt}%"] for field in ("first_name", "middle_name", "last_name")]

	if filters:
		if not (filters.get("ignore_user_type") and frappe.session.data.user_type == "System User"):
			list_filters["user_type"] = ["!=", "Website User"]

		filters.pop("ignore_user_type", None)
		list_filters.update(filters)

	return frappe.get_list(
		doctype,
		filters=list_filters,
		fields=["name", "full_name"],
		limit_start=start,
		limit_page_length=page_len,
		order_by="name asc",
		or_filters=or_filters,
		as_list=True,
	)


def get_total_users():
	"""Return total number of system users."""
	return flt(
		frappe.db.sql(
			"""SELECT SUM(`simultaneous_sessions`)
		FROM `tabUser`
		WHERE `enabled` = 1
		AND `user_type` = 'System User'
		AND `name` NOT IN ({})""".format(", ".join(["%s"] * len(STANDARD_USERS))),
			STANDARD_USERS,
		)[0][0]
	)


def get_system_users(exclude_users: Iterable[str] | str | None = None, limit: int | None = None):
	_excluded_users = list(STANDARD_USERS)
	if isinstance(exclude_users, str):
		_excluded_users.append(exclude_users)
	elif isinstance(exclude_users, Iterable):
		_excluded_users.extend(exclude_users)

	return frappe.get_all(
		"User",
		filters={
			"enabled": 1,
			"user_type": ("!=", "Website User"),
			"name": ("not in", _excluded_users),
		},
		pluck="name",
		limit=limit,
	)


def get_active_users():
	"""Return number of system users who logged in, in the last 3 days."""
	return frappe.db.sql(
		"""select count(*) from `tabUser`
		where enabled = 1 and user_type != 'Website User'
		and name not in ({})
		and hour(timediff(now(), last_active)) < 72""".format(", ".join(["%s"] * len(STANDARD_USERS))),
		STANDARD_USERS,
	)[0][0]


def get_website_users():
	"""Return total number of website users."""
	return frappe.db.count("User", filters={"enabled": True, "user_type": "Website User"})


def get_active_website_users():
	"""Return number of website users who logged in, in the last 3 days."""
	return frappe.db.sql(
		"""select count(*) from `tabUser`
        where enabled = 1 and user_type = 'Website User'
        and hour(timediff(now(), last_active)) < 72"""
	)[0][0]


def get_permission_query_conditions(user):
	if user == "Administrator":
		return ""
	else:
		return """(`tabUser`.name not in ({standard_users}))""".format(
			standard_users=", ".join(frappe.db.escape(user) for user in STANDARD_USERS)
		)


def has_permission(doc, user):
	if (user != "Administrator") and (doc.name in STANDARD_USERS):
		# dont allow non Administrator user to view / edit Administrator user
		return False
	return True


def notify_admin_access_to_system_manager(login_manager=None):
	if (
		login_manager
		and login_manager.user == "Administrator"
		and frappe.local.conf.notify_admin_access_to_system_manager
	):
		site = '<a href="{0}" target="_blank">{0}</a>'.format(frappe.local.request.host_url)
		date_and_time = "<b>{}</b>".format(format_datetime(now_datetime(), format_string="medium"))
		ip_address = frappe.local.request_ip

		access_message = _("Administrator accessed {0} on {1} via IP Address {2}.").format(
			site, date_and_time, ip_address
		)

		frappe.sendmail(
			recipients=get_system_managers(),
			subject=_("Administrator Logged In"),
			template="administrator_logged_in",
			args={"access_message": access_message},
			header=["Access Notification", "orange"],
		)


def handle_password_test_fail(feedback: dict):
	# Backward compatibility
	if "feedback" in feedback:
		feedback = feedback["feedback"]

	suggestions = feedback.get("suggestions", [])
	warning = feedback.get("warning", "")

	frappe.throw(msg=" ".join([warning, *suggestions]), title=_("Invalid Password"))


def update_gravatar(name):
	gravatar = has_gravatar(name)
	if gravatar:
		frappe.db.set_value("User", name, "user_image", gravatar)


def throttle_user_creation():
	if frappe.flags.in_import:
		return

	if frappe.db.get_creation_count("User", 60) > frappe.local.conf.get("throttle_user_limit", 60):
		frappe.throw(_("Throttled"))


@frappe.whitelist()
def get_module_profile(module_profile: str):
	module_profile = frappe.get_doc("Module Profile", {"module_profile_name": module_profile})
	return module_profile.get("block_modules")


def create_contact(user, ignore_links=False, ignore_mandatory=False):
	from frappe.contacts.doctype.contact.contact import get_contact_name

	if user.name in ["Administrator", "Guest"]:
		return

	contact_name = get_contact_name(user.email)
	if not contact_name:
		try:
			contact = frappe.get_doc(
				{
					"doctype": "Contact",
					"first_name": user.first_name,
					"last_name": user.last_name,
					"user": user.name,
					"gender": user.gender,
				}
			)

			if user.email:
				contact.add_email(user.email, is_primary=True)

			if user.phone:
				contact.add_phone(user.phone, is_primary_phone=True)

			if user.mobile_no:
				contact.add_phone(user.mobile_no, is_primary_mobile_no=True)

			contact.insert(
				ignore_permissions=True, ignore_links=ignore_links, ignore_mandatory=ignore_mandatory
			)
		except frappe.DuplicateEntryError:
			pass
	else:
		try:
			contact = frappe.get_doc("Contact", contact_name)
			contact.first_name = user.first_name
			contact.last_name = user.last_name
			contact.gender = user.gender

			# Add mobile number if phone does not exists in contact
			if user.phone and not any(new_contact.phone == user.phone for new_contact in contact.phone_nos):
				# Set primary phone if there is no primary phone number
				contact.add_phone(
					user.phone,
					is_primary_phone=not any(
						new_contact.is_primary_phone == 1 for new_contact in contact.phone_nos
					),
				)

			# Add mobile number if mobile does not exists in contact
			if user.mobile_no and not any(
				new_contact.phone == user.mobile_no for new_contact in contact.phone_nos
			):
				# Set primary mobile if there is no primary mobile number
				contact.add_phone(
					user.mobile_no,
					is_primary_mobile_no=not any(
						new_contact.is_primary_mobile_no == 1 for new_contact in contact.phone_nos
					),
				)

			contact.save(ignore_permissions=True)
		except frappe.TimestampMismatchError:
			raise frappe.RetryBackgroundJobError


def get_restricted_ip_list(user):
	if not user.restrict_ip:
		return

	return [i.strip() for i in user.restrict_ip.strip().split(",")]


@frappe.whitelist(methods=["POST"])
def generate_keys(user: str):
	"""
	generate api key and api secret

	:param user: str
	"""
	frappe.only_for("System Manager")
	user_details: User = frappe.get_doc("User", user)
	api_secret = frappe.generate_hash(length=15)
	# if api key is not set generate api key
	if not user_details.api_key:
		api_key = frappe.generate_hash(length=15)
		user_details.api_key = api_key
	user_details.api_secret = api_secret
	user_details.save()

	return {"api_secret": api_secret}


@frappe.whitelist()
def switch_theme(theme):
	if theme in ["Dark", "Light", "Automatic"]:
		frappe.db.set_value("User", frappe.session.user, "desk_theme", theme)


def get_enabled_users():
	def _get_enabled_users():
		enabled_users = frappe.get_all("User", filters={"enabled": "1"}, pluck="name")
		return enabled_users

	return frappe.cache.get_value("enabled_users", _get_enabled_users)


@frappe.whitelist(methods=["POST"])
def impersonate(user: str, reason: str):
	# Note: For now we only allow admins, we MIGHT allow system manager in future.
	# All the impersonation code doesn't assume anything about user.
	frappe.only_for("Administrator")

	impersonator = frappe.session.user
	frappe.get_doc(
		{
			"doctype": "Activity Log",
			"user": user,
			"status": "Success",
			"subject": _("User {0} impersonated as {1}").format(impersonator, user),
			"operation": "Impersonate",
		}
	).insert(ignore_permissions=True, ignore_links=True)

	notification = frappe.new_doc(
		"Notification Log",
		for_user=user,
		from_user=frappe.session.user,
		subject=_("{0} just impersonated as you. They gave this reason: {1}").format(impersonator, reason),
	)
	notification.set("type", "Alert")
	notification.insert(ignore_permissions=True)
	frappe.local.login_manager.impersonate(user)
