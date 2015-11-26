# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
bootstrap client session
"""

import frappe
import frappe.defaults
import frappe.desk.desk_page
from frappe.utils import get_gravatar, get_url
from frappe.desk.form.load import get_meta_bundle
from frappe.utils.change_log import get_versions

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
	bootinfo.single_types = frappe.db.sql_list("""select name from tabDocType where issingle=1""")
	add_home_page(bootinfo, doclist)
	bootinfo.page_info = get_allowed_pages()
	load_translations(bootinfo)
	add_timezone_info(bootinfo)
	load_conf_settings(bootinfo)
	load_print(bootinfo, doclist)
	doclist.extend(get_meta_bundle("Page"))
	bootinfo.home_folder = frappe.db.get_value("File", {"is_home_folder": 1})

	# ipinfo
	if frappe.session['data'].get('ipinfo'):
		bootinfo['ipinfo'] = frappe.session['data']['ipinfo']

	# add docs
	bootinfo['docs'] = doclist

	for method in hooks.boot_session or []:
		frappe.get_attr(method)(bootinfo)

	if bootinfo.lang:
		bootinfo.lang = unicode(bootinfo.lang)
	bootinfo['versions'] = {k: v['version'] for k, v in get_versions().items()}

	bootinfo.error_report_email = frappe.get_hooks("error_report_email")
	bootinfo.calendars = sorted(frappe.get_hooks("calendars"))

	return bootinfo

def load_conf_settings(bootinfo):
	from frappe import conf
	bootinfo.max_file_size = conf.get('max_file_size') or 5242880
	for key in ['developer_mode']:
		if key in conf: bootinfo[key] = conf.get(key)

def get_allowed_pages():
	roles = frappe.get_roles()
	page_info = {}

	for p in frappe.db.sql("""select distinct
		tabPage.name, tabPage.modified, tabPage.title
		from `tabPage Role`, `tabPage`
		where `tabPage Role`.role in (%s)
			and `tabPage Role`.parent = `tabPage`.name""" % ', '.join(['%s']*len(roles)),
				roles, as_dict=True):

		page_info[p.name] = {"modified":p.modified, "title":p.title}

	# pages where role is not set are also allowed
	for p in frappe.db.sql("""select name, modified, title
		from `tabPage` where
			(select count(*) from `tabPage Role`
				where `tabPage Role`.parent=tabPage.name) = 0""", as_dict=1):

		page_info[p.name] = {"modified":p.modified, "title":p.title}

	return page_info

def load_translations(bootinfo):
	if frappe.local.lang != 'en':
		messages = frappe.get_lang_dict("boot")

		bootinfo["lang"] = frappe.lang

		# load translated report names
		for name in bootinfo.user.all_reports:
			messages[name] = frappe._(name)

		bootinfo["__messages"] = messages

def get_fullnames():
	"""map of user fullnames"""
	ret = frappe.db.sql("""select name,
		concat(ifnull(first_name, ''),
			if(ifnull(last_name, '')!='', ' ', ''), ifnull(last_name, '')) as fullname,
			user_image as image, gender, email
		from tabUser where enabled=1 and user_type!="Website User" """, as_dict=1)

	d = {}
	for r in ret:
		if not r.image:
			r.image = get_gravatar()
		d[r.name] = r

	return d

def get_user(bootinfo):
	"""get user info"""
	bootinfo.user = frappe.get_user().load_user()

def add_home_page(bootinfo, docs):
	"""load home page"""
	if frappe.session.user=="Guest":
		return
	home_page = frappe.db.get_default("desktop:home_page")

	if home_page == "setup-wizard":
		bootinfo.setup_wizard_requires = frappe.get_hooks("setup_wizard_requires")

	try:
		page = frappe.desk.desk_page.get(home_page)
	except (frappe.DoesNotExistError, frappe.PermissionError):
		if frappe.message_log:
			frappe.message_log.pop()
		page = frappe.desk.desk_page.get('desktop')

	bootinfo['home_page'] = page.name
	docs.append(page)

def add_timezone_info(bootinfo):
	system = bootinfo.sysdefaults.get("time_zone")
	import frappe.utils.momentjs
	bootinfo.timezone_info = {"zones":{}, "rules":{}, "links":{}}
	frappe.utils.momentjs.update(system, bootinfo.timezone_info)

def load_print(bootinfo, doclist):
	print_settings = frappe.db.get_singles_dict("Print Settings")
	print_settings.doctype = ":Print Settings"
	doclist.append(print_settings)
	load_print_css(bootinfo, print_settings)

def load_print_css(bootinfo, print_settings):
	bootinfo.print_css = frappe.get_attr("frappe.templates.pages.print.get_print_style")(print_settings.print_style or "Modern", for_legacy=True)
