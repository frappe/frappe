from __future__ import unicode_literals
import frappe
from   frappe.chat.util import filter_dict, safe_json_loads

from   frappe.sessions  import get_geo_ip_country

import os
import re
from frappe.www.desk import get_build_version

@frappe.whitelist(allow_guest = True)
def settings(fields = None):
	fields	= safe_json_loads(fields)

	dsettings = frappe.get_single('Website Settings')
	response  = dict(
		socketio		 = dict(
			port		 = frappe.conf.socketio_port
		),
		enable		   = bool(dsettings.chat_enable),
		enable_from	  = dsettings.chat_enable_from,
		enable_to		= dsettings.chat_enable_to,
		room_name		= dsettings.chat_room_name,
		welcome_message  = dsettings.chat_welcome_message,
		operators		= [
			duser.user for duser in dsettings.chat_operators
		]
	)

	if fields:
		response = filter_dict(response, fields)

	return response

@frappe.whitelist(allow_guest = True)
def token():
	dtoken			 = frappe.new_doc('Chat Token')

	dtoken.token	   = frappe.generate_hash()
	dtoken.ip_address  = frappe.local.request_ip
	country			= get_geo_ip_country(dtoken.ip_address)
	if country:
		dtoken.country = country['iso_code']
	dtoken.save(ignore_permissions = True)

	return dtoken.token


@frappe.whitelist(allow_guest=True)
def get_chat_assets(build_version):
	try:
		boot = frappe.sessions.get()
	except Exception as e:
		boot = frappe._dict(status='failed', error = str(e))
		print(frappe.get_traceback())

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()

	boot_json = frappe.as_json(boot)
	boot_json = re.sub("\<script\>[^<]*\</script\>", "", boot_json)

	include_js = [
		'assets/js/frappe-web.min.js',
		'assets/js/bootstrap-4-web.min.js',
		'assets/js/dialog.min.js',
		'assets/js/control.min.js'
		'assets/js/chat.js',
	]
	include_css = []
	local_build_version = get_build_version()

	"""Get chat assets to be loaded for mobile app"""
	assets = [{"type": "js", "data": ""}, {"type": "css", "data": ""}]

	if build_version != local_build_version:
		# new build, send assets
		for path in include_js:
			if path.startswith('/assets/'):
				path = path.replace('/assets/', 'assets/')
			try:
				with open(os.path.join(frappe.local.sites_path, path) ,"r") as f:
					assets[0]["data"] = assets[0]["data"] + "\n" + frappe.safe_decode(f.read(), "utf-8")
			except IOError:
				pass

		for path in include_css:
			if path.startswith('/assets/'):
				path = path.replace('/assets/', 'assets/')
			try:
				with open(os.path.join(frappe.local.sites_path, path) ,"r") as f:
					assets[1]["data"] = assets[1]["data"] + "\n" + frappe.safe_decode(f.read(), "utf-8")
			except IOError:
				pass

	return {
		"build_version": local_build_version,
		"boot": boot_json,
		"assets": assets
	}
