# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
"""
bootstrap client session
"""

import webnotes
import webnotes.model.doc
import webnotes.widgets.page

def get_bootinfo():
	"""build and return boot info"""
	bootinfo = webnotes._dict()
	doclist = []

	# profile
	get_profile(bootinfo)
	
	# control panel
	cp = webnotes.model.doc.getsingle('Control Panel')

	
	# system info
	bootinfo['control_panel'] = webnotes._dict(cp.copy())
	bootinfo['sysdefaults'] = webnotes.utils.get_defaults()
	bootinfo['server_date'] = webnotes.utils.nowdate()

	if webnotes.session['user'] != 'Guest':
		bootinfo['user_info'] = get_fullnames()
		bootinfo['sid'] = webnotes.session['sid'];
		
	# home page
	add_home_page(bootinfo, doclist)
	add_allowed_pages(bootinfo)
	load_translations(bootinfo)
	load_country_and_currency(bootinfo, doclist)

	# ipinfo
	if webnotes.session['data'].get('ipinfo'):
		bootinfo['ipinfo'] = webnotes.session['data']['ipinfo']
	
	# add docs
	bootinfo['docs'] = doclist
	
	# plugins
	try:
		from startup import event_handlers
		if getattr(event_handlers, 'boot_session', None):
			event_handlers.boot_session(bootinfo)

	except ImportError:
		pass
	
	from webnotes.model.utils import compress
	bootinfo['docs'] = compress(bootinfo['docs'])
	
	return bootinfo

def load_country_and_currency(bootinfo, doclist):
	if bootinfo.control_panel.country and \
		webnotes.conn.exists("Country", bootinfo.control_panel.country):
		doclist += [webnotes.doc("Country", bootinfo.control_panel.country)]
		
	doclist += webnotes.conn.sql("""select * from tabCurrency
		where ifnull(enabled,0)=1""", as_dict=1, update={"doctype":"Currency"})

def add_allowed_pages(bootinfo):
	bootinfo.allowed_pages = [p[0] for p in webnotes.conn.sql("""select distinct parent from `tabPage Role`
		where role in ('%s')""" % "', '".join(webnotes.get_roles()))]

def load_translations(bootinfo):
	try:
		from startup import lang_list, lang_names
	except ImportError:
		return
		
	user_lang_pref = webnotes.conn.get_value("Profile", webnotes.session.user, "language")
	if user_lang_pref and (user_lang_pref in lang_names):
		webnotes.lang = lang_names[user_lang_pref]
		webnotes.user_lang = True
		
	if webnotes.lang != 'en':
		from webnotes.translate import get_lang_data
		# framework
		bootinfo["__messages"] = get_lang_data("../lib/public/js/wn", None, "js")
		# doctype and module names
		bootinfo["__messages"].update(get_lang_data('../app/public/js', None, "js"))
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
	except webnotes.PermissionError, e:
		page_doclist = webnotes.widgets.page.get('Login Page')
		
	bootinfo['home_page_html'] = page_doclist[0].content
	bootinfo['home_page'] = page_doclist[0].name
	doclist += page_doclist
