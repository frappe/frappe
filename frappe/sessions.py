# Copyright (c) 2021, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
Boot session from cache or build

Session bootstraps info needed by common client side activities including
permission, homepage, default variables, system defaults etc
"""
import json
from datetime import datetime, timezone
from urllib.parse import unquote

import redis

import nts
import nts.defaults
import nts.model.meta
import nts.translate
import nts.utils
from nts import _
from nts.apps import get_apps, get_default_path, is_desk_apps
from nts.cache_manager import clear_user_cache
from nts.query_builder import Order
from nts.utils import cint, cstr, get_assets_json
from nts.utils.change_log import has_app_update_notifications
from nts.utils.data import add_to_date


@nts.whitelist()
def clear():
	nts.local.session_obj.update(force=True)
	nts.local.db.commit()
	clear_user_cache(nts.session.user)
	nts.response["message"] = _("Cache Cleared")


def clear_sessions(user=None, keep_current=False, force=False):
	"""Clear other sessions of the current user. Called at login / logout

	:param user: user name (default: current user)
	:param keep_current: keep current session (default: false)
	:param force: triggered by the user (default false)
	"""

	reason = "Logged In From Another Session"
	if force:
		reason = "Force Logged out by the user"

	for sid in get_sessions_to_clear(user, keep_current, force):
		delete_session(sid, reason=reason)


def get_sessions_to_clear(user=None, keep_current=False, force=False):
	"""Returns sessions of the current user. Called at login / logout

	:param user: user name (default: current user)
	:param keep_current: keep current session (default: false)
	:param force: ignore simultaneous sessions count, log the user out of all except current (default: false)
	"""
	if not user:
		user = nts.session.user

	offset = 0
	if not force and user == nts.session.user:
		simultaneous_sessions = nts.db.get_value("User", user, "simultaneous_sessions") or 1
		offset = simultaneous_sessions

	session = nts.qb.DocType("Sessions")
	session_id = nts.qb.from_(session).where(session.user == user)
	if keep_current:
		if not force:
			offset = max(0, offset - 1)
		session_id = session_id.where(session.sid != nts.session.sid)

	query = (
		session_id.select(session.sid).offset(offset).limit(100).orderby(session.lastupdate, order=Order.desc)
	)

	return query.run(pluck=True)


def delete_session(sid=None, user=None, reason="Session Expired"):
	from nts.core.doctype.activity_log.feed import logout_feed

	if nts.flags.read_only:
		# This isn't manually initiated logout, most likely user's cookies were expired in such case
		# we should just ignore it till database is back up again.
		return

	if sid and not user:
		table = nts.qb.DocType("Sessions")
		user_details = nts.qb.from_(table).where(table.sid == sid).select(table.user).run(as_dict=True)
		if user_details:
			user = user_details[0].get("user")

	logout_feed(user, reason)
	nts.db.delete("Sessions", {"sid": sid})
	nts.db.commit()

	nts.cache.hdel("session", sid)
	nts.cache.hdel("last_db_session_update", sid)


def clear_all_sessions(reason=None):
	"""This effectively logs out all users"""
	nts.only_for("Administrator")
	if not reason:
		reason = "Deleted All Active Session"
	for sid in nts.qb.from_("Sessions").select("sid").run(pluck=True):
		delete_session(sid, reason=reason)


def get_expired_sessions():
	"""Returns list of expired sessions"""

	sessions = nts.qb.DocType("Sessions")
	return (
		nts.qb.from_(sessions).select(sessions.sid).where(sessions.lastupdate < get_expired_threshold())
	).run(pluck=True)


def clear_expired_sessions():
	"""This function is meant to be called from scheduler"""
	for sid in get_expired_sessions():
		delete_session(sid, reason="Session Expired")


def get():
	"""get session boot info"""
	from nts.boot import get_bootinfo, get_unseen_notes
	from nts.utils.change_log import get_change_log

	bootinfo = None
	if not getattr(nts.conf, "disable_session_cache", None):
		# check if cache exists
		bootinfo = nts.cache.hget("bootinfo", nts.session.user)
		if bootinfo:
			bootinfo["from_cache"] = 1
			bootinfo["user"]["recent"] = json.dumps(nts.cache.hget("user_recent", nts.session.user))

	if not bootinfo:
		# if not create it
		bootinfo = get_bootinfo()
		nts.cache.hset("bootinfo", nts.session.user, bootinfo)
		try:
			nts.cache.ping()
		except redis.exceptions.ConnectionError:
			message = _("Redis cache server not running. Please contact Administrator / Tech support")
			if "messages" in bootinfo:
				bootinfo["messages"].append(message)
			else:
				bootinfo["messages"] = [message]

		# check only when clear cache is done, and don't cache this
		if nts.local.request:
			bootinfo["change_log"] = get_change_log()

	bootinfo["metadata_version"] = nts.cache.get_value("metadata_version")
	if not bootinfo["metadata_version"]:
		bootinfo["metadata_version"] = nts.reset_metadata_version()

	bootinfo.notes = get_unseen_notes()
	bootinfo.assets_json = get_assets_json()
	bootinfo.read_only = bool(nts.flags.read_only)

	for hook in nts.get_hooks("extend_bootinfo"):
		nts.get_attr(hook)(bootinfo=bootinfo)

	bootinfo["lang"] = nts.translate.get_user_lang()
	bootinfo["disable_async"] = nts.conf.disable_async

	bootinfo["setup_complete"] = cint(nts.get_system_settings("setup_complete"))
	apps = get_apps() or []
	bootinfo["apps_data"] = {
		"apps": apps,
		"is_desk_apps": 1 if bool(is_desk_apps(apps)) else 0,
		"default_path": get_default_path(apps) or "",
	}

	bootinfo["desk_theme"] = nts.db.get_value("User", nts.session.user, "desk_theme") or "Light"
	bootinfo["user"]["impersonated_by"] = nts.session.data.get("impersonated_by")
	bootinfo["navbar_settings"] = nts.get_cached_doc("Navbar Settings")
	bootinfo.has_app_updates = has_app_update_notifications()

	return bootinfo


@nts.whitelist()
def get_boot_assets_json():
	return get_assets_json()


def get_csrf_token():
	if not nts.local.session.data.csrf_token:
		generate_csrf_token()

	return nts.local.session.data.csrf_token


def generate_csrf_token():
	nts.local.session.data.csrf_token = nts.generate_hash()
	if not nts.flags.in_test:
		nts.local.session_obj.update(force=True)


class Session:
	__slots__ = ("user", "user_type", "full_name", "data", "time_diff", "sid", "_update_in_cache")

	def __init__(
		self,
		user: str,
		resume: bool = False,
		full_name: str | None = None,
		user_type: str | None = None,
		session_end: str | None = None,
		audit_user: str | None = None,
	):
		self.sid = cstr(nts.form_dict.get("sid") or unquote(nts.request.cookies.get("sid", "Guest")))
		self.user = user
		self.user_type = user_type
		self.full_name = full_name
		self.data = nts._dict({"data": nts._dict({})})
		self.time_diff = None
		self._update_in_cache = False

		# set local session
		nts.local.session = self.data

		if resume:
			self.resume()

		else:
			if self.user:
				self.validate_user()
				self.start(session_end, audit_user)

	def validate_user(self):
		if not nts.get_cached_value("User", self.user, "enabled"):
			nts.throw(
				_("User {0} is disabled. Please contact your System Manager.").format(self.user),
				nts.ValidationError,
			)

	def start(self, session_end: str | None = None, audit_user: str | None = None):
		"""start a new session"""
		# generate sid
		if self.user == "Guest":
			sid = "Guest"
		else:
			sid = nts.generate_hash()

		self.data.user = self.user
		self.sid = self.data.sid = sid
		self.data.data.user = self.user
		self.data.data.session_ip = nts.local.request_ip

		if session_end:
			self.data.data.session_end = session_end

		if audit_user:
			self.data.data.audit_user = audit_user

		if self.user != "Guest":
			self.data.data.update(
				{
					"last_updated": nts.utils.now(),
					"session_expiry": get_expiry_period(),
					"full_name": self.full_name,
					"user_type": self.user_type,
				}
			)

		# insert session
		if self.user != "Guest":
			self.insert_session_record()

			# update user
			user = nts.get_doc("User", self.data["user"])
			user_doctype = nts.qb.DocType("User")
			(
				nts.qb.update(user_doctype)
				.set(user_doctype.last_login, nts.utils.now())
				.set(user_doctype.last_ip, nts.local.request_ip)
				.set(user_doctype.last_active, nts.utils.now())
				.where(user_doctype.name == self.data["user"])
			).run()

			user.run_notifications("before_change")
			user.run_notifications("on_update")
			nts.db.commit()

	def insert_session_record(self):
		Sessions = nts.qb.DocType("Sessions")
		now = nts.utils.now()

		(
			nts.qb.into(Sessions)
			.columns(Sessions.sessiondata, Sessions.user, Sessions.lastupdate, Sessions.sid, Sessions.status)
			.insert((str(self.data["data"]), self.data["user"], now, self.data["sid"], "Active"))
		).run()
		nts.cache.hset("session", self.data.sid, self.data)

	def resume(self):
		"""non-login request: load a session"""
		import nts
		from nts.auth import validate_ip_address

		data = self.get_session_record()

		if data:
			self.data.update({"data": data, "user": data.user, "sid": self.sid})
			self.user = data.user
			self.validate_user()
			validate_ip_address(self.user)
		else:
			self.start_as_guest()

		if self.sid != "Guest":
			nts.local.user_lang = nts.translate.get_user_lang(self.data.user)
			nts.local.lang = nts.local.user_lang

	def get_session_record(self):
		"""get session record, or return the standard Guest Record"""
		from nts.auth import clear_cookies

		r = self.get_session_data()

		if not r:
			nts.response["session_expired"] = 1
			clear_cookies()
			self.sid = "Guest"
			r = self.get_session_data()

		return r

	def get_session_data(self):
		if self.sid == "Guest":
			return nts._dict({"user": "Guest"})

		data = self.get_session_data_from_cache()
		if not data:
			self._update_in_cache = True
			data = self.get_session_data_from_db()
		return data

	def get_session_data_from_cache(self):
		data = nts.cache.hget("session", self.sid)
		if data:
			data = nts._dict(data)
			session_data = data.get("data", {})

			# set user for correct timezone
			self.time_diff = nts.utils.time_diff_in_seconds(
				nts.utils.now(), session_data.get("last_updated")
			)
			expiry = get_expiry_in_seconds(session_data.get("session_expiry"))

			if self.time_diff > expiry or (
				(session_end := session_data.get("session_end"))
				and datetime.now(tz=timezone.utc) > datetime.fromisoformat(session_end)
			):
				self._delete_session()
				data = None

		return data and data.data

	def get_session_data_from_db(self):
		sessions = nts.qb.DocType("Sessions")

		record = (
			nts.qb.from_(sessions)
			.select(sessions.user, sessions.sessiondata)
			.where(sessions.sid == self.sid)
			.where(sessions.lastupdate > get_expired_threshold())
		).run()

		if record:
			data = nts._dict(nts.safe_eval(record and record[0][1] or "{}"))
			data.user = record[0][0]
		else:
			self._delete_session()
			data = None

		return data

	def _delete_session(self):
		delete_session(self.sid, reason="Session Expired")

	def start_as_guest(self):
		"""all guests share the same 'Guest' session"""
		self.user = "Guest"
		self.start()

	def update(self, force=False):
		"""extend session expiry"""

		if nts.session.user == "Guest":
			return

		now = nts.utils.now()

		Sessions = nts.qb.DocType("Sessions")

		# update session in db
		last_updated = nts.cache.hget("last_db_session_update", self.sid)
		time_diff = nts.utils.time_diff_in_seconds(now, last_updated) if last_updated else None

		# database persistence is secondary, don't update it too often
		updated_in_db = False
		if (force or (time_diff is None) or (time_diff > 600)) and not nts.flags.read_only:
			self.data.data.last_updated = now
			self.data.data.lang = str(nts.lang)
			# update sessions table
			(
				nts.qb.update(Sessions)
				.where(Sessions.sid == self.data["sid"])
				.set(Sessions.sessiondata, str(self.data["data"]))
				.set(Sessions.lastupdate, now)
			).run()

			nts.db.set_value("User", nts.session.user, "last_active", now, update_modified=False)

			nts.db.commit()
			updated_in_db = True

			nts.cache.hset("last_db_session_update", self.sid, now)
			nts.cache.hset("session", self.sid, self.data)

		return updated_in_db

	def set_impersonated(self, original_user):
		self.data.data.impersonated_by = original_user
		# Forcefully flush session
		self.update(force=True)


def get_expiry_period_for_query():
	if nts.db.db_type == "postgres":
		return get_expiry_period()
	else:
		return get_expiry_in_seconds()


def get_expiry_in_seconds(expiry=None):
	if not expiry:
		expiry = get_expiry_period()

	parts = expiry.split(":")
	return (cint(parts[0]) * 3600) + (cint(parts[1]) * 60) + cint(parts[2])


def get_expired_threshold():
	"""Get cutoff time before which all sessions are considered expired."""

	now = nts.utils.now()
	expiry_in_seconds = get_expiry_in_seconds()

	return add_to_date(now, seconds=-expiry_in_seconds, as_string=True)


def get_expiry_period():
	exp_sec = nts.defaults.get_global_default("session_expiry") or "240:00:00"

	# incase seconds is missing
	if len(exp_sec.split(":")) == 2:
		exp_sec = exp_sec + ":00"

	return exp_sec


def get_geo_from_ip(ip_addr):
	try:
		from geolite2 import geolite2

		with geolite2 as f:
			reader = f.reader()
			data = reader.get(ip_addr)

			return nts._dict(data)
	except ImportError:
		return
	except ValueError:
		return
	except TypeError:
		return


def get_geo_ip_country(ip_addr):
	match = get_geo_from_ip(ip_addr)
	if match:
		return match.country
