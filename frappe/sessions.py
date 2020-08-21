# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
Boot session from cache or build

Session bootstraps info needed by common client side activities including
permission, homepage, default variables, system defaults etc
"""
import frappe, json
from frappe import _
import frappe.utils
from frappe.utils import cint, cstr
import frappe.model.meta
import frappe.defaults
import frappe.translate
from frappe.utils.change_log import get_change_log
import redis
from six.moves.urllib.parse import unquote
from six import text_type
from frappe.cache_manager import clear_user_cache

@frappe.whitelist()
def clear(user=None):
	frappe.local.session_obj.update(force=True)
	frappe.local.db.commit()
	clear_user_cache(frappe.session.user)
	frappe.response['message'] = _("Cache Cleared")

def clear_sessions(user=None, keep_current=False, device=None, force=False):
	'''Clear other sessions of the current user. Called at login / logout

	:param user: user name (default: current user)
	:param keep_current: keep current session (default: false)
	:param device: delete sessions of this device (default: desktop, mobile)
	:param force: triggered by the user (default false)
	'''

	reason = "Logged In From Another Session"
	if force:
		reason = "Force Logged out by the user"

	for sid in get_sessions_to_clear(user, keep_current, device):
		delete_session(sid, reason=reason)

def get_sessions_to_clear(user=None, keep_current=False, device=None):
	'''Returns sessions of the current user. Called at login / logout

	:param user: user name (default: current user)
	:param keep_current: keep current session (default: false)
	:param device: delete sessions of this device (default: desktop, mobile)
	'''
	if not user:
		user = frappe.session.user

	if not device:
		device = ("desktop", "mobile")

	if not isinstance(device, (tuple, list)):
		device = (device,)

	offset = 0
	if user == frappe.session.user:
		simultaneous_sessions = frappe.db.get_value('User', user, 'simultaneous_sessions') or 1
		offset = simultaneous_sessions - 1

	condition = ''
	if keep_current:
		condition = ' AND sid != {0}'.format(frappe.db.escape(frappe.session.sid))

	return frappe.db.sql_list("""
		SELECT `sid` FROM `tabSessions`
		WHERE user=%(user)s
		AND device in %(device)s
		{condition}
		ORDER BY `lastupdate` DESC
		LIMIT 100 OFFSET {offset}""".format(condition=condition, offset=offset),
		{"user": user, "device": device})

def delete_session(sid=None, user=None, reason="Session Expired"):
	from frappe.core.doctype.activity_log.feed import logout_feed

	frappe.cache().hdel("session", sid)
	frappe.cache().hdel("last_db_session_update", sid)
	if sid and not user:
		user_details = frappe.db.sql("""select user from tabSessions where sid=%s""", sid, as_dict=True)
		if user_details: user = user_details[0].get("user")

	logout_feed(user, reason)
	frappe.db.sql("""delete from tabSessions where sid=%s""", sid)
	frappe.db.commit()

def clear_all_sessions(reason=None):
	"""This effectively logs out all users"""
	frappe.only_for("Administrator")
	if not reason: reason = "Deleted All Active Session"
	for sid in frappe.db.sql_list("select sid from `tabSessions`"):
		delete_session(sid, reason=reason)

def get_expired_sessions():
	'''Returns list of expired sessions'''
	expired = []
	for device in ("desktop", "mobile"):
		expired += frappe.db.sql_list("""SELECT `sid`
				FROM `tabSessions`
				WHERE (NOW() - `lastupdate`) > %s
				AND device = %s""", (get_expiry_period_for_query(device), device))

	return expired

def clear_expired_sessions():
	"""This function is meant to be called from scheduler"""
	for sid in get_expired_sessions():
		delete_session(sid, reason="Session Expired")

def get():

	"""get session boot info"""
	from frappe.boot import get_bootinfo, get_unseen_notes

	bootinfo = None
	if not getattr(frappe.conf,'disable_session_cache', None):
		# check if cache exists
		bootinfo = frappe.cache().hget("bootinfo", frappe.session.user)
		if bootinfo:
			bootinfo['from_cache'] = 1
			bootinfo["user"]["recent"] = json.dumps(\
				frappe.cache().hget("user_recent", frappe.session.user))

	if not bootinfo:
		# if not create it
		bootinfo = get_bootinfo()
		frappe.cache().hset("bootinfo", frappe.session.user, bootinfo)
		try:
			frappe.cache().ping()
		except redis.exceptions.ConnectionError:
			message = _("Redis cache server not running. Please contact Administrator / Tech support")
			if 'messages' in bootinfo:
				bootinfo['messages'].append(message)
			else:
				bootinfo['messages'] = [message]

		# check only when clear cache is done, and don't cache this
		if frappe.local.request:
			bootinfo["change_log"] = get_change_log()

	bootinfo["metadata_version"] = frappe.cache().get_value("metadata_version")
	if not bootinfo["metadata_version"]:
		bootinfo["metadata_version"] = frappe.reset_metadata_version()

	bootinfo.notes = get_unseen_notes()

	for hook in frappe.get_hooks("extend_bootinfo"):
		frappe.get_attr(hook)(bootinfo=bootinfo)

	bootinfo["lang"] = frappe.translate.get_user_lang()
	bootinfo["disable_async"] = frappe.conf.disable_async

	bootinfo["setup_complete"] = cint(frappe.db.get_single_value('System Settings', 'setup_complete'))
	bootinfo["is_first_startup"] = cint(frappe.db.get_single_value('System Settings', 'is_first_startup'))

	return bootinfo

def get_csrf_token():
	if not frappe.local.session.data.csrf_token:
		generate_csrf_token()

	return frappe.local.session.data.csrf_token

def generate_csrf_token():
	frappe.local.session.data.csrf_token = frappe.generate_hash()
	frappe.local.session_obj.update(force=True)

class Session:
	def __init__(self, user, resume=False, full_name=None, user_type=None):
		self.sid = cstr(frappe.form_dict.get('sid') or
			unquote(frappe.request.cookies.get('sid', 'Guest')))
		self.user = user
		self.device = frappe.form_dict.get("device") or "desktop"
		self.user_type = user_type
		self.full_name = full_name
		self.data = frappe._dict({'data': frappe._dict({})})
		self.time_diff = None

		# set local session
		frappe.local.session = self.data

		if resume:
			self.resume()

		else:
			if self.user:
				self.start()

	def start(self):
		"""start a new session"""
		# generate sid
		if self.user=='Guest':
			sid = 'Guest'
		else:
			sid = frappe.generate_hash()

		self.data.user = self.user
		self.data.sid = sid
		self.data.data.user = self.user
		self.data.data.session_ip = frappe.local.request_ip
		if self.user != "Guest":
			self.data.data.update({
				"last_updated": frappe.utils.now(),
				"session_expiry": get_expiry_period(self.device),
				"full_name": self.full_name,
				"user_type": self.user_type,
				"device": self.device,
				"session_country": get_geo_ip_country(frappe.local.request_ip) if frappe.local.request_ip else None,
			})

		# insert session
		if self.user!="Guest":
			self.insert_session_record()

			# update user
			user = frappe.get_doc("User", self.data['user'])
			frappe.db.sql("""UPDATE `tabUser`
				SET
					last_login = %(now)s,
					last_ip = %(ip)s,
					last_active = %(now)s
				WHERE name=%(name)s""", {
					'now': frappe.utils.now(),
					'ip': frappe.local.request_ip,
					'name': self.data['user']
				})
			user.run_notifications("before_change")
			user.run_notifications("on_update")
			frappe.db.commit()

	def insert_session_record(self):
		frappe.db.sql("""insert into `tabSessions`
			(`sessiondata`, `user`, `lastupdate`, `sid`, `status`, `device`)
			values (%s , %s, NOW(), %s, 'Active', %s)""",
				(str(self.data['data']), self.data['user'], self.data['sid'], self.device))

		# also add to memcache
		frappe.cache().hset("session", self.data.sid, self.data)

	def resume(self):
		"""non-login request: load a session"""
		import frappe
		from frappe.auth import validate_ip_address
		data = self.get_session_record()

		if data:
			# set language
			self.data.update({'data': data, 'user':data.user, 'sid': self.sid})
			self.user = data.user
			validate_ip_address(self.user)
			self.device = data.device
		else:
			self.start_as_guest()

		if self.sid != "Guest":
			frappe.local.user_lang = frappe.translate.get_user_lang(self.data.user)
			frappe.local.lang = frappe.local.user_lang

	def get_session_record(self):
		"""get session record, or return the standard Guest Record"""
		from frappe.auth import clear_cookies
		r = self.get_session_data()

		if not r:
			frappe.response["session_expired"] = 1
			clear_cookies()
			self.sid = "Guest"
			r = self.get_session_data()

		return r

	def get_session_data(self):
		if self.sid=="Guest":
			return frappe._dict({"user":"Guest"})

		data = self.get_session_data_from_cache()
		if not data:
			data = self.get_session_data_from_db()
		return data

	def get_session_data_from_cache(self):
		data = frappe.cache().hget("session", self.sid)
		if data:
			data = frappe._dict(data)
			session_data = data.get("data", {})

			# set user for correct timezone
			self.time_diff = frappe.utils.time_diff_in_seconds(frappe.utils.now(),
				session_data.get("last_updated"))
			expiry = get_expiry_in_seconds(session_data.get("session_expiry"))

			if self.time_diff > expiry:
				print('deleting...')
				self.delete_session()
				data = None

		return data and data.data

	def get_session_data_from_db(self):
		self.device = frappe.db.sql('SELECT `device` FROM `tabSessions` WHERE `sid`=%s', self.sid)
		self.device = self.device and self.device[0][0] or 'desktop'

		rec = frappe.db.sql("""
			SELECT `user`, `sessiondata`
			FROM `tabSessions` WHERE `sid`=%s AND
			(NOW() - lastupdate) < %s
			""", (self.sid, get_expiry_period_for_query(self.device)))

		if rec:
			data = frappe._dict(eval(rec and rec[0][1] or '{}'))
			data.user = rec[0][0]
		else:
			self.delete_session()
			data = None

		return data

	def delete_session(self):
		delete_session(self.sid, reason="Session Expired")

	def start_as_guest(self):
		"""all guests share the same 'Guest' session"""
		self.user = "Guest"
		self.start()

	def update(self, force=False):
		"""extend session expiry"""
		if (frappe.session['user'] == "Guest" or frappe.form_dict.cmd=="logout"):
			return

		now = frappe.utils.now()

		self.data['data']['last_updated'] = now
		self.data['data']['lang'] = text_type(frappe.lang)

		# update session in db
		last_updated = frappe.cache().hget("last_db_session_update", self.sid)
		time_diff = frappe.utils.time_diff_in_seconds(now, last_updated) if last_updated else None

		# database persistence is secondary, don't update it too often
		updated_in_db = False
		if force or (time_diff==None) or (time_diff > 600):
			# update sessions table
			frappe.db.sql("""update `tabSessions` set sessiondata=%s,
				lastupdate=NOW() where sid=%s""" , (str(self.data['data']),
				self.data['sid']))

			# update last active in user table
			frappe.db.sql("""update `tabUser` set last_active=%(now)s where name=%(name)s""", {
				"now": now,
				"name": frappe.session.user
			})

			frappe.db.commit()
			frappe.cache().hset("last_db_session_update", self.sid, now)

			updated_in_db = True

		# set in memcache
		frappe.cache().hset("session", self.sid, self.data)

		return updated_in_db

def get_expiry_period_for_query(device=None):
	if frappe.db.db_type == 'postgres':
		return get_expiry_period(device)
	else:
		return get_expiry_in_seconds(device=device)

def get_expiry_in_seconds(expiry=None, device=None):
	if not expiry:
		expiry = get_expiry_period(device)
	parts = expiry.split(":")
	return (cint(parts[0]) * 3600) + (cint(parts[1]) * 60) + cint(parts[2])

def get_expiry_period(device="desktop"):
	if device=="mobile":
		key = "session_expiry_mobile"
		default = "720:00:00"
	else:
		key = "session_expiry"
		default = "06:00:00"

	exp_sec = frappe.defaults.get_global_default(key) or default

	# incase seconds is missing
	if len(exp_sec.split(':')) == 2:
		exp_sec = exp_sec + ':00'

	return exp_sec

def get_geo_from_ip(ip_addr):
	try:
		from geolite2 import geolite2
		with geolite2 as f:
			reader = f.reader()
			data   = reader.get(ip_addr)

			return frappe._dict(data)
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
