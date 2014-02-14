# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
bootstrap client session
"""

import frappe
import frappe.defaults
import frappe.model.doc
import frappe.widgets.page
import json

def get_bootinfo():
	"""build and return boot info"""
	bootinfo = frappe._dict()
	hooks = frappe.get_hooks()
	doclist = []

	# profile
	get_profile(bootinfo)
	
	# control panel
	cp = frappe.model.doc.getsingle('Control Panel')
		
	# system info
	bootinfo['control_panel'] = frappe._dict(cp.copy())
	bootinfo['sysdefaults'] = frappe.defaults.get_defaults()
	bootinfo['server_date'] = frappe.utils.nowdate()
	bootinfo["send_print_in_body_and_attachment"] = frappe.conn.get_value("Email Settings", 
		None, "send_print_in_body_and_attachment")

	if frappe.session['user'] != 'Guest':
		bootinfo['user_info'] = get_fullnames()
		bootinfo['sid'] = frappe.session['sid'];
		
	# home page
	bootinfo.modules = {}
	for app in frappe.get_installed_apps():
		try:
			bootinfo.modules.update(frappe.get_attr(app + ".config.desktop.data") or {})
		except ImportError, e:
			pass

	bootinfo.hidden_modules = frappe.conn.get_global("hidden_modules")
	bootinfo.doctype_icons = dict(frappe.conn.sql("""select name, icon from 
		tabDocType where ifnull(icon,'')!=''"""))
	bootinfo.doctype_icons.update(dict(frappe.conn.sql("""select name, icon from 
		tabPage where ifnull(icon,'')!=''""")))
	
	add_home_page(bootinfo, doclist)
	add_allowed_pages(bootinfo)
	load_translations(bootinfo)
	load_conf_settings(bootinfo)
	load_startup_js(bootinfo)

	# ipinfo
	if frappe.session['data'].get('ipinfo'):
		bootinfo['ipinfo'] = frappe.session['data']['ipinfo']
	
	# add docs
	bootinfo['docs'] = doclist
	
	for method in hooks.boot_session or []:
		frappe.get_attr(method)(bootinfo)
		
	from frappe.model.utils import compress
	bootinfo['docs'] = compress(bootinfo['docs'])

	if bootinfo.lang:
		bootinfo.lang = unicode(bootinfo.lang)
	
	bootinfo.metadata_version = frappe.cache().get_value("metadata_version")
	if not bootinfo.metadata_version:
		bootinfo.metadata_version = frappe.reset_metadata_version()
		
	return bootinfo

def load_conf_settings(bootinfo):
	from frappe import conf
	for key in ['developer_mode']:
		if key in conf: bootinfo[key] = conf.get(key)

def add_allowed_pages(bootinfo):
	bootinfo.page_info = dict(frappe.conn.sql("""select distinct parent, modified from `tabPage Role`
		where role in ('%s')""" % "', '".join(frappe.get_roles())))

def load_translations(bootinfo):
	frappe.set_user_lang(frappe.session.user)
	
	if frappe.lang != 'en':
		bootinfo["__messages"] = frappe.get_lang_dict("include")
		bootinfo["lang"] = frappe.lang

def get_fullnames():
	"""map of user fullnames"""
	ret = frappe.conn.sql("""select name, 
		concat(ifnull(first_name, ''), 
			if(ifnull(last_name, '')!='', ' ', ''), ifnull(last_name, '')), 
			user_image, gender, email
		from tabProfile where ifnull(enabled, 0)=1""", as_list=1)
	d = {}
	for r in ret:
		if not r[2]:
			r[2] = '/assets/frappe/images/ui/avatar.png'
		else:
			r[2] = r[2]
			
		d[r[0]]= {'fullname': r[1], 'image': r[2], 'gender': r[3],
			'email': r[4] or r[0]}

	return d

def load_startup_js(bootinfo):
	bootinfo.startup_js = ""
	for method in frappe.get_hooks().startup_js or []:
		bootinfo.startup_js += frappe.get_attr(method)()
		
def get_profile(bootinfo):
	"""get profile info"""
	bootinfo['profile'] = frappe.user.load_profile()
	
def add_home_page(bootinfo, doclist):
	"""load home page"""

	if frappe.session.user=="Guest":
		return
		
	home_page = frappe.get_application_home_page(frappe.session.user)

	try:
		page_doclist = frappe.widgets.page.get(home_page)
	except (frappe.DoesNotExistError, frappe.PermissionError), e:
		page_doclist = frappe.widgets.page.get('desktop')
		
	bootinfo['home_page_html'] = page_doclist[0].content
	bootinfo['home_page'] = page_doclist[0].name
	doclist += page_doclist
