# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
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
from frappe.utils import cint
import frappe.model.meta
import frappe.defaults
import frappe.translate

@frappe.whitelist()
def clear(user=None):
	frappe.local.session_obj.update(force=True)
	frappe.local.db.commit()
	clear_cache(frappe.session.user)
	frappe.response['message'] = "Cache Cleared"


def clear_cache(user=None):
	cache = frappe.cache()

	frappe.model.meta.clear_cache()
	cache.delete_value(["app_hooks", "installed_apps", "app_modules", "module_apps", "home_page",
		"time_zone"])

	def delete_user_cache(user):
		for key in ("bootinfo", "lang", "roles", "restrictions"):
			cache.delete_value(key + ":" + user)

	def clear_notifications(user=None):
		if frappe.flags.in_install_app!="frappe":
			if user:
				frappe.db.sql("""delete from `tabNotification Count` where owner=%s""", (user,))
			else:
				frappe.db.sql("""delete from `tabNotification Count`""")

	if user:
		delete_user_cache(user)
		clear_notifications(user)

		if frappe.session:
			if user==frappe.session.user and frappe.session.sid:
				cache.delete_value("session:" + frappe.session.sid)
			else:
				for sid in frappe.db.sql_list("""select sid from tabSessions
					where user=%s""", (user,)):
						cache.delete_value("session:" + sid)

		frappe.defaults.clear_cache(user)
	else:
		for sess in frappe.db.sql("""select user, sid from tabSessions""", as_dict=1):
			delete_user_cache(sess.user)
			cache.delete_value("session:" + sess.sid)

		clear_notifications()
		frappe.defaults.clear_cache()

def clear_sessions(user=None, keep_current=False):
	if not user:
		user = frappe.session.user
	for sid in frappe.db.sql("""select sid from tabSessions where user=%s""", (user,)):
		if keep_current and frappe.session.sid==sid[0]:
			continue
		else:
			frappe.cache().delete_value("session:" + sid[0])
			frappe.db.sql("""delete from tabSessions where sid=%s""", (sid[0],))

def delete_session(sid=None):
	frappe.cache().delete_value("session:" + sid)
	frappe.db.sql("""delete from tabSessions where sid=%s""", sid)

def get():
	"""get session boot info"""
	from frappe.core.doctype.notification_count.notification_count import \
		get_notification_info_for_boot, get_notifications
	from frappe.boot import get_bootinfo, get_startup_js

	bootinfo = None
	if not getattr(frappe.conf,'disable_session_cache', None):
		# check if cache exists
		bootinfo = frappe.cache().get_value('bootinfo:' + frappe.session.user)
		if bootinfo:
			bootinfo['from_cache'] = 1
			bootinfo["user"]["recent"] = json.dumps(frappe.cache().get_value("recent:" + frappe.session.user))
			bootinfo["notification_info"].update(get_notifications())

	if not bootinfo:
		if not frappe.cache().get_stats():
			frappe.msgprint(_("memcached is not working / stopped. Please start memcached for best results."))

		# if not create it
		bootinfo = get_bootinfo()
		bootinfo["notification_info"] = get_notification_info_for_boot()
		frappe.cache().set_value('bootinfo:' + frappe.session.user, bootinfo)

	bootinfo["metadata_version"] = frappe.cache().get_value("metadata_version")
	if not bootinfo["metadata_version"]:
		bootinfo["metadata_version"] = frappe.reset_metadata_version()

	bootinfo["startup_js"] = get_startup_js()
	for hook in frappe.get_hooks("extend_bootinfo"):
		frappe.get_attr(hook)(bootinfo=bootinfo)

	return bootinfo

class Session:
	def __init__(self, user, resume=False):
		self.sid = frappe.form_dict.get('sid') or frappe.request.cookies.get('sid', 'Guest')
		self.user = user
		self.data = frappe._dict({'data': frappe._dict({})})
		self.time_diff = None
		if resume:
			self.resume()
		else:
			self.start()

		# set local session
		frappe.local.session = self.data

	def start(self):
		"""start a new session"""
		# generate sid
		if self.user=='Guest':
			sid = 'Guest'
		else:
			sid = frappe.generate_hash()

		self.data['user'] = self.user
		self.data['sid'] = sid
		self.data['data']['user'] = self.user
		self.data['data']['session_ip'] = frappe.get_request_header('REMOTE_ADDR')
		if self.user != "Guest":
			self.data['data']['last_updated'] = frappe.utils.now()
			self.data['data']['session_expiry'] = self.get_expiry_period()
		self.data['data']['session_country'] = get_geo_ip_country(frappe.get_request_header('REMOTE_ADDR'))

		# insert session
		if self.user!="Guest":
			frappe.db.begin()
			self.insert_session_record()

			# update user
			frappe.db.sql("""UPDATE tabUser SET last_login = %s, last_ip = %s
				where name=%s""", (frappe.utils.now(), frappe.get_request_header('REMOTE_ADDR'), self.data['user']))
			frappe.db.commit()

	def insert_session_record(self):
		frappe.db.sql("""insert into tabSessions
			(sessiondata, user, lastupdate, sid, status)
			values (%s , %s, NOW(), %s, 'Active')""",
				(str(self.data['data']), self.data['user'], self.data['sid']))

		# also add to memcache
		frappe.cache().set_value("session:" + self.data.sid, self.data)

	def resume(self):
		"""non-login request: load a session"""
		import frappe
		data = self.get_session_record()
		if data:
			# set language
			self.data = frappe._dict({'data': data, 'user':data.user, 'sid': self.sid})
		else:
			self.start_as_guest()

		frappe.local.lang = frappe.translate.get_user_lang(self.data.user)

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
		data = frappe._dict(frappe.cache().get_value("session:" + self.sid) or {})
		if data:
			session_data = data.get("data", {})
			self.time_diff = frappe.utils.time_diff_in_seconds(frappe.utils.now(),
				session_data.get("last_updated"))
			expiry = self.get_expiry_in_seconds(session_data.get("session_expiry"))

			if self.time_diff > expiry:
				self.delete_session()
				data = None

		return data and data.data

	def get_session_data_from_db(self):
		rec = frappe.db.sql("""select user, sessiondata
			from tabSessions where sid=%s and
			TIMEDIFF(NOW(), lastupdate) < TIME(%s)""", (self.sid,
				self.get_expiry_period()))
		if rec:
			data = frappe._dict(eval(rec and rec[0][1] or '{}'))
			data.user = rec[0][0]
		else:
			self.delete_session()
			data = None

		return data

	def get_expiry_in_seconds(self, expiry):
		if not expiry: return 3600
		parts = expiry.split(":")
		return (cint(parts[0]) * 3600) + (cint(parts[1]) * 60) + cint(parts[2])

	def delete_session(self):
		delete_session(self.sid)

	def start_as_guest(self):
		"""all guests share the same 'Guest' session"""
		self.user = "Guest"
		self.start()

	def update(self, force=False):
		"""extend session expiry"""
		self.data['data']['last_updated'] = frappe.utils.now()
		self.data['data']['lang'] = unicode(frappe.lang)


		# update session in db
		time_diff = None
		last_updated = frappe.cache().get_value("last_db_session_update:" + self.sid)

		if last_updated:
			time_diff = frappe.utils.time_diff_in_seconds(frappe.utils.now(),
				last_updated)

		if force or (frappe.session['user'] != 'Guest' and \
			((time_diff==None) or (time_diff > 1800))):
			# database persistence is secondary, don't update it too often
			frappe.db.sql("""update tabSessions set sessiondata=%s,
				lastupdate=NOW() where sid=%s""" , (str(self.data['data']),
				self.data['sid']))

		if frappe.form_dict.cmd not in ("frappe.sessions.clear", "logout"):
			frappe.cache().set_value("last_db_session_update:" + self.sid,
				frappe.utils.now())
			frappe.cache().set_value("session:" + self.sid, self.data)

	def get_expiry_period(self):
		exp_sec = frappe.defaults.get_global_default("session_expiry") or "06:00:00"

		# incase seconds is missing
		if exp_sec:
			if len(exp_sec.split(':')) == 2:
				exp_sec = exp_sec + ':00'
		else:
			exp_sec = "2:00:00"

		return exp_sec

def get_geo_ip_country(ip_addr):
	try:
		import pygeoip
	except ImportError:
		return

	import os

	try:
		geo_ip_file = os.path.join(os.path.dirname(frappe.__file__), "data", "GeoIP.dat")
		geo_ip = pygeoip.GeoIP(geo_ip_file, pygeoip.MEMORY_CACHE)
		return geo_ip.country_name_by_addr(ip_addr)
	except Exception:
		return

