# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
bootstrap client session
"""

import webnotes
import webnotes.defaults
import webnotes.model.doc
import webnotes.widgets.page
import json
import webnotes.webutils

def get_bootinfo():
	"""build and return boot info"""
	bootinfo = webnotes._dict()
	hooks = webnotes.get_hooks()
	doclist = []

	# profile
	get_profile(bootinfo)
	
	# control panel
	cp = webnotes.model.doc.getsingle('Control Panel')
	
	# system info
	bootinfo['control_panel'] = webnotes._dict(cp.copy())
	bootinfo['sysdefaults'] = webnotes.defaults.get_defaults()
	bootinfo['server_date'] = webnotes.utils.nowdate()
	bootinfo["send_print_in_body_and_attachment"] = webnotes.conn.get_value("Email Settings", 
		None, "send_print_in_body_and_attachment")

	if webnotes.session['user'] != 'Guest':
		bootinfo['user_info'] = get_fullnames()
		bootinfo['sid'] = webnotes.session['sid'];
		
	# home page
	bootinfo.modules = {}
	for get_desktop_icons in hooks.get_desktop_icons:
		bootinfo.modules.update(webnotes.get_attr(get_desktop_icons)())

	bootinfo.hidden_modules = webnotes.conn.get_global("hidden_modules")
	bootinfo.doctype_icons = dict(webnotes.conn.sql("""select name, icon from 
		tabDocType where ifnull(icon,'')!=''"""))
	bootinfo.doctype_icons.update(dict(webnotes.conn.sql("""select name, icon from 
		tabPage where ifnull(icon,'')!=''""")))
	
	add_home_page(bootinfo, doclist)
	add_allowed_pages(bootinfo)
	load_translations(bootinfo)
	load_conf_settings(bootinfo)

	# ipinfo
	if webnotes.session['data'].get('ipinfo'):
		bootinfo['ipinfo'] = webnotes.session['data']['ipinfo']
	
	# add docs
	bootinfo['docs'] = doclist
	
	for method in hooks.boot_session:
		webnotes.get_attr(method)(bootinfo)
		
	from webnotes.model.utils import compress
	bootinfo['docs'] = compress(bootinfo['docs'])

	# deal with __slots__ in lang
	if bootinfo.lang:
		bootinfo.lang = unicode(bootinfo.lang)
	
	bootinfo.metadata_version = webnotes.cache().get_value("metadata_version")
	if not bootinfo.metadata_version:
		bootinfo.metadata_version = webnotes.reset_metadata_version()
		
	return bootinfo

def load_conf_settings(bootinfo):
	from webnotes import conf
	for key in ['developer_mode']:
		if key in conf: bootinfo[key] = conf.get(key)

def add_allowed_pages(bootinfo):
	bootinfo.page_info = dict(webnotes.conn.sql("""select distinct parent, modified from `tabPage Role`
		where role in ('%s')""" % "', '".join(webnotes.get_roles())))

def load_translations(bootinfo):
	webnotes.set_user_lang(webnotes.session.user)
	
	if webnotes.lang != 'en':
		bootinfo["__messages"] = webnotes.get_lang_dict("include")
		bootinfo["lang"] = webnotes.lang

def get_fullnames():
	"""map of user fullnames"""
	ret = webnotes.conn.sql("""select name, 
		concat(ifnull(first_name, ''), 
			if(ifnull(last_name, '')!='', ' ', ''), ifnull(last_name, '')), 
			user_image, gender, email
		from tabProfile where ifnull(enabled, 0)=1""", as_list=1)
	d = {}
	for r in ret:
		if not r[2]:
			r[2] = 'lib/images/ui/avatar.png'
		else:
			r[2] = r[2]
			
		d[r[0]]= {'fullname': r[1], 'image': r[2], 'gender': r[3],
			'email': r[4] or r[0]}

	return d
		
def get_profile(bootinfo):
	"""get profile info"""
	bootinfo['profile'] = webnotes.user.load_profile()
	
def add_home_page(bootinfo, doclist):
	"""load home page"""

	if webnotes.session.user=="Guest":
		return
		
	home_page = webnotes.get_application_home_page(webnotes.session.user)

	try:
		page_doclist = webnotes.widgets.page.get(home_page)
	except (webnotes.DoesNotExistError, webnotes.PermissionError), e:
		page_doclist = webnotes.widgets.page.get('desktop')
		
	bootinfo['home_page_html'] = page_doclist[0].content
	bootinfo['home_page'] = page_doclist[0].name
	doclist += page_doclist
