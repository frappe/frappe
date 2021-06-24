# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function

no_cache = 1
base_template_path = "templates/www/app.html"

import os, re
import frappe
from frappe import _
import frappe.sessions

def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in to access this page."), frappe.PermissionError)
	elif frappe.db.get_value("User", frappe.session.user, "user_type") == "Website User":
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	hooks = frappe.get_hooks()
	try:
		boot = frappe.sessions.get()
	except Exception as e:
		boot = frappe._dict(status='failed', error = str(e))
		print(frappe.get_traceback())

	# this needs commit
	csrf_token = frappe.sessions.get_csrf_token()

	frappe.db.commit()

	desk_theme = frappe.db.get_value("User", frappe.session.user, "desk_theme")

	boot_json = frappe.as_json(boot)

	# remove script tags from boot
	boot_json = re.sub(r"\<script[^<]*\</script\>", "", boot_json)

	# TODO: Find better fix
	boot_json = re.sub(r"</script\>", "", boot_json)

	# app_include_js and app_include_css
	app_assets = get_app_assets(hooks)
	context.update(app_assets)

	context.update({
		"no_cache": 1,
		"build_version": frappe.utils.get_build_version(),
		"sounds": hooks["sounds"],
		"boot": boot if context.get("for_mobile") else boot_json,
		"desk_theme": desk_theme or "Light",
		"csrf_token": csrf_token,
		"google_analytics_id": frappe.conf.get("google_analytics_id"),
		"google_analytics_anonymize_ip": frappe.conf.get("google_analytics_anonymize_ip"),
		"mixpanel_id": frappe.conf.get("mixpanel_id")
	})

	return context

def get_app_assets(hooks):
	'''Returns assets that need to be loaded in /app
	
	Will also handle .bundle. files that are introduced in v14 for forward compatibility
	'''

	def get_file_path(file):
		if '.bundle.' in file:
			file_type = 'js' if file.endswith('.js') else 'css'
			asset_path = os.path.join('assets', file_type, file)
			output_file_path = os.path.join(frappe.utils.get_bench_path(), 'sites', asset_path)
			if os.path.exists(output_file_path):
				return '/' + asset_path
		return file

	js = list(map(get_file_path, hooks["app_include_js"]))
	css = list(map(get_file_path, hooks["app_include_css"]))

	return {
		"include_js": js,
		"include_css": css,
	}


@frappe.whitelist()
def get_desk_assets(build_version):
	"""Get desk assets to be loaded for mobile app"""
	data = get_context({"for_mobile": True})
	assets = [{"type": "js", "data": ""}, {"type": "css", "data": ""}]

	if build_version != data["build_version"]:
		# new build, send assets
		for path in data["include_js"]:
			# assets path shouldn't start with /
			# as it points to different location altogether
			if path.startswith('/assets/'):
				path = path.replace('/assets/', 'assets/')
			try:
				with open(os.path.join(frappe.local.sites_path, path) ,"r") as f:
					assets[0]["data"] = assets[0]["data"] + "\n" + frappe.safe_decode(f.read(), "utf-8")
			except IOError:
				pass

		for path in data["include_css"]:
			if path.startswith('/assets/'):
				path = path.replace('/assets/', 'assets/')
			try:
				with open(os.path.join(frappe.local.sites_path, path) ,"r") as f:
					assets[1]["data"] = assets[1]["data"] + "\n" + frappe.safe_decode(f.read(), "utf-8")
			except IOError:
				pass

	return {
		"build_version": data["build_version"],
		"boot": data["boot"],
		"assets": assets
	}
