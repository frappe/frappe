# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
bootstrap client session
"""

import frappe
import frappe.defaults
import frappe.widgets.page
from frappe.utils import get_gravatar

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

	if frappe.session['user'] != 'Guest':
		bootinfo['user_info'] = get_fullnames()
		bootinfo['sid'] = frappe.session['sid'];

	# home page
	bootinfo.modules = {}
	for app in frappe.get_installed_apps():
		try:
			bootinfo.modules.update(frappe.get_attr(app + ".config.desktop.get_data")() or {})
		except ImportError:
			pass
		except AttributeError:
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
	add_timezone_info(bootinfo)
	load_conf_settings(bootinfo)
	load_print(bootinfo, doclist)

	# ipinfo
	if frappe.session['data'].get('ipinfo'):
		bootinfo['ipinfo'] = frappe.session['data']['ipinfo']

	# add docs
	bootinfo['docs'] = doclist

	for method in hooks.boot_session or []:
		frappe.get_attr(method)(bootinfo)

	if bootinfo.lang:
		bootinfo.lang = unicode(bootinfo.lang)

	bootinfo.error_report_email = frappe.get_hooks("error_report_email")

	return bootinfo

def load_conf_settings(bootinfo):
	from frappe import conf
	for key in ['developer_mode']:
		if key in conf: bootinfo[key] = conf.get(key)

def add_allowed_pages(bootinfo):
	roles = frappe.get_roles()
	bootinfo.page_info = {}
	for p in frappe.db.sql("""select distinct
		tabPage.name, tabPage.modified, tabPage.title
		from `tabPage Role`, `tabPage`
		where `tabPage Role`.role in (%s)
			and `tabPage Role`.parent = `tabPage`.name""" % ', '.join(['%s']*len(roles)),
				roles, as_dict=True):

		bootinfo.page_info[p.name] = {"modified":p.modified, "title":p.title}

	# pages where role is not set are also allowed
	for p in frappe.db.sql("""select name, modified, title
		from `tabPage` where
			(select count(*) from `tabPage Role`
				where `tabPage Role`.parent=tabPage.name) = 0""", as_dict=1):

		bootinfo.page_info[p.name] = {"modified":p.modified, "title":p.title}

def load_translations(bootinfo):
	if frappe.local.lang != 'en':
		bootinfo["__messages"] = frappe.get_lang_dict("boot")
		bootinfo["lang"] = frappe.lang

def get_fullnames():
	"""map of user fullnames"""
	ret = frappe.db.sql("""select name,
		concat(ifnull(first_name, ''),
			if(ifnull(last_name, '')!='', ' ', ''), ifnull(last_name, '')) as fullname,
			user_image as image, gender, email
		from tabUser where ifnull(enabled, 0)=1""", as_dict=1)

	d = {}
	for r in ret:
		if not r.image:
			r.image = get_gravatar()
		d[r.name] = r

	return d

def get_startup_js():
	startup_js = []
	for method in frappe.get_hooks().startup_js or []:
		startup_js.append(frappe.get_attr(method)() or "")
	return "\n".join(startup_js)

def get_user(bootinfo):
	"""get user info"""
	bootinfo.user = frappe.user.load_user()

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

def add_timezone_info(bootinfo):
	user = bootinfo.user.get("time_zone")
	system = bootinfo.sysdefaults.get("time_zone")
	if user and user != system:
		import frappe.utils.momentjs
		bootinfo.timezone_info = {"zones":{}, "rules":{}, "links":{}}

		frappe.utils.momentjs.update(user, bootinfo.timezone_info)
		frappe.utils.momentjs.update(system, bootinfo.timezone_info)

def load_print(bootinfo, doclist):
	print_settings = frappe.db.get_singles_dict("Print Settings")
	print_settings.doctype = ":Print Settings"
	doclist.append(print_settings)
	load_print_css(bootinfo, print_settings)

def load_print_css(bootinfo, print_settings):
	bootinfo.print_css = frappe.get_attr("frappe.templates.pages.print.get_print_style")(print_settings.print_style or "Modern")
