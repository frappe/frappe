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

"""
bootstrap client session
"""


def get_bootinfo():
	"""build and return boot info"""
	import webnotes
	bootinfo = {}	
	doclist = []

	webnotes.conn.begin()
	# profile
	get_profile(bootinfo)
	
	# control panel
	import webnotes.model.doc
	cp = webnotes.model.doc.getsingle('Control Panel')

	# remove email settings from control panel dict
	for field in ['mail_login', 'mail_password', 'mail_port', 'outgoing_mail_server', 'use_ssl']:
		del cp[field]
	
	# system info
	bootinfo['control_panel'] = cp.copy()
	bootinfo['account_name'] = cp.get('account_id')
	bootinfo['sysdefaults'] = webnotes.utils.get_defaults()

	if webnotes.session['user'] != 'Guest':
		import webnotes.widgets.menus
		bootinfo['start_items'] = webnotes.widgets.menus.get_menu_items()
		bootinfo['dt_labels'] = get_dt_labels()
		
	# home page
	get_home_page(bootinfo, doclist)

	# ipinfo
	if webnotes.session['data'].get('ipinfo'):
		bootinfo['ipinfo'] = webnotes.session['data']['ipinfo']
	
	# add docs
	bootinfo['docs'] = doclist
	
	# plugins
	import startup.event_handlers
	if getattr(startup.event_handlers, 'boot_session'):
		startup.event_handlers.boot_session(bootinfo)

	webnotes.conn.commit()
	
	return bootinfo

def get_profile(bootinfo):
	"""get profile info"""
	import webnotes
	bootinfo['profile'] = webnotes.user.load_profile()
	webnotes.session['data']['profile'] = bootinfo['profile']
	
def get_home_page(bootinfo, doclist):
	"""load home page"""
	import webnotes
	home_page = webnotes.user.get_home_page()
	if home_page:
		import webnotes.widgets.page
		page_doclist = webnotes.widgets.page.get(home_page)
		doclist += webnotes.widgets.page.get(home_page)
		bootinfo['home_page_html'] = page_doclist[0].content

	bootinfo['home_page'] = home_page or ''

def get_dt_labels():
	import webnotes
	res = webnotes.conn.sql("select name, dt_label from `tabDocType Label`")
	return dict(res)
