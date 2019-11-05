from __future__ import unicode_literals
import frappe
from frappe.chat.util import filter_dict, safe_json_loads
from frappe.sessions import get_geo_ip_country

import os
from frappe.www.desk import get_build_version, get_assets_data


@frappe.whitelist(allow_guest=True)
def settings(fields=None):
	fields = safe_json_loads(fields)

	dsettings = frappe.get_single('Website Settings')
	response = {
		"socketio": {
			"port": frappe.conf.socketio_port
		},
		"enable": bool(dsettings.chat_enable),
		"enable_from": dsettings.chat_enable_from,
		"enable_to": dsettings.chat_enable_to,
		"room_name": dsettings.chat_room_name,
		"welcome_message": dsettings.chat_welcome_message,
		"operators": [duser.user for duser in dsettings.chat_operators]
	}

	if fields:
		response = filter_dict(response, fields)

	return response


@frappe.whitelist(allow_guest=True)
def token():
	dtoken = frappe.new_doc('Chat Token')

	dtoken.token = frappe.generate_hash()
	dtoken.ip_address = frappe.local.request_ip
	country = get_geo_ip_country(dtoken.ip_address)
	if country:
		dtoken.country = country['iso_code']
	dtoken.save(ignore_permissions=True)

	return dtoken.token


@frappe.whitelist(allow_guest=True)
def get_chat_assets(build_version):
	try:
		boot = frappe.sessions.get()
	except Exception as e:
		boot = frappe._dict(status='failed', error = str(e))
		print(frappe.get_traceback())

	data = {
		'include_js': [
			'assets/js/moment-bundle.min.js',
			'assets/js/chat-bundle.js',
		],
		'include_css': [
			'assets/css/desk.min.css'
		]
	}

	# Get chat assets to be loaded for mobile app
	local_build_version = get_build_version()
	assets = [{"type": "js", "data": ""}, {"type": "css", "data": ""}]
	if build_version != local_build_version:
		get_assets_data(data)

	return {
		"build_version": local_build_version,
		"boot": boot,
		"assets": assets
	}
