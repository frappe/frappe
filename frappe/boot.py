# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
bootstrap client session
"""

import frappe
import frappe.defaults
import frappe.widgets.page

def get_bootinfo():
	"""build and return boot info"""
	frappe.set_user_lang(frappe.session.user)
	bootinfo = frappe._dict()
	hooks = frappe.get_hooks()
	doclist = []

	# user
	get_user(bootinfo)

	# system info
	bootinfo['sysdefaults'] = frappe.defaults.get_defaults()
	bootinfo['server_date'] = frappe.utils.nowdate()
	bootinfo["send_print_in_body_and_attachment"] = frappe.db.get_value("Outgoing Email Settings",
		None, "send_print_in_body_and_attachment")

	if frappe.session['user'] != 'Guest':
		bootinfo['user_info'] = get_fullnames()
		bootinfo['sid'] = frappe.session['sid'];

	# home page
	bootinfo.modules = {}
	for app in frappe.get_installed_apps():
		try:
			bootinfo.modules.update(frappe.get_attr(app + ".config.desktop.data") or {})
		except ImportError:
			pass

	bootinfo.module_app = frappe.local.module_app
	bootinfo.hidden_modules = frappe.db.get_global("hidden_modules")
	bootinfo.doctype_icons = dict(frappe.db.sql("""select name, icon from
		tabDocType where ifnull(icon,'')!=''"""))
	bootinfo.doctype_icons.update(dict(frappe.db.sql("""select name, icon from
		tabPage where ifnull(icon,'')!=''""")))

	add_home_page(bootinfo, doclist)
	add_allowed_pages(bootinfo)
	load_translations(bootinfo)
	load_conf_settings(bootinfo)

	# ipinfo
	if frappe.session['data'].get('ipinfo'):
		bootinfo['ipinfo'] = frappe.session['data']['ipinfo']

	# add docs
	bootinfo['docs'] = doclist

	for method in hooks.boot_session or []:
		frappe.get_attr(method)(bootinfo)

	if bootinfo.lang:
		bootinfo.lang = unicode(bootinfo.lang)

	return bootinfo

def load_conf_settings(bootinfo):
	from frappe import conf
	for key in ['developer_mode']:
		if key in conf: bootinfo[key] = conf.get(key)

def add_allowed_pages(bootinfo):
	roles = frappe.get_roles()
	bootinfo.page_info = dict(frappe.db.sql("""select distinct parent, modified from `tabPage Role`
		where role in (%s)""" % ', '.join(['%s']*len(roles)), roles))

	# pages where role is not set are also allowed
	bootinfo.page_info.update(dict(frappe.db.sql("""select parent, modified
		from `tabPage` where
			(select count(*) from `tabPage Role`
				where `tabPage Role`.parent=tabPage.name) = 0""")))

def load_translations(bootinfo):
	if frappe.local.lang != 'en':
		bootinfo["__messages"] = frappe.get_lang_dict("boot")
		bootinfo["lang"] = frappe.lang

def get_fullnames():
	"""map of user fullnames"""
	ret = frappe.db.sql("""select name,
		concat(ifnull(first_name, ''),
			if(ifnull(last_name, '')!='', ' ', ''), ifnull(last_name, '')),
			user_image, gender, email
		from tabUser where ifnull(enabled, 0)=1""", as_list=1)
	d = {}
	for r in ret:
		if not r[2]:
			r[2] = '/assets/frappe/images/ui/avatar.png'
		else:
			r[2] = r[2]

		d[r[0]]= {'fullname': r[1], 'image': r[2], 'gender': r[3],
			'email': r[4] or r[0]}

	return d

def get_startup_js():
	startup_js = []
	for method in frappe.get_hooks().startup_js or []:
		startup_js.append(frappe.get_attr(method)() or "")
	return "\n".join(startup_js)

def get_user(bootinfo):
	"""get user info"""
	bootinfo['user'] = frappe.user.load_user()

def add_home_page(bootinfo, docs):
	"""load home page"""

	if frappe.session.user=="Guest":
		return

	home_page = frappe.db.get_default("desktop:home_page")

	try:
		page = frappe.widgets.page.get(home_page)
	except (frappe.DoesNotExistError, frappe.PermissionError):
		frappe.message_log.pop()
		page = frappe.widgets.page.get('desktop')

	bootinfo['home_page'] = page.name
	docs.append(page)
