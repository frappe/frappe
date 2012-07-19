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

	from webnotes.utils import cint
	
	# system info
	bootinfo['control_panel'] = cp.copy()
	bootinfo['account_name'] = cp.get('account_id')
	bootinfo['sysdefaults'] = webnotes.utils.get_defaults()

	if webnotes.session['user'] != 'Guest':
		import webnotes.widgets.menus
		bootinfo['user_info'] = get_fullnames()
		bootinfo['sid'] = webnotes.session['sid'];
		
	# home page
	add_home_page(bootinfo, doclist)

	# ipinfo
	if webnotes.session['data'].get('ipinfo'):
		bootinfo['ipinfo'] = webnotes.session['data']['ipinfo']
	
	# add docs
	bootinfo['docs'] = doclist
	
	# plugins
	try:
		import startup.event_handlers
		if getattr(startup.event_handlers, 'boot_session', None):
			startup.event_handlers.boot_session(bootinfo)

	except ImportError:
		pass

	webnotes.conn.commit()
	
	return bootinfo

def get_fullnames():
	"""map of user fullnames"""
	import webnotes
	ret = webnotes.conn.sql("""select name, 
		concat(ifnull(first_name, ''), 
			if(ifnull(last_name, '')!='', ' ', ''), ifnull(last_name, '')), 
			user_image, gender
		from tabProfile where ifnull(enabled, 0)=1""", as_list=1)
	d = {}
	for r in ret:
		if not r[2]:
			r[2] = 'images/lib/ui/no_img_m.gif'
		else:
			r[2] = 'files/' + r[2]
			
		d[r[0]]= {'fullname': r[1], 'image': r[2], 'gender': r[3]}

	return d
		
def get_profile(bootinfo):
	"""get profile info"""
	import webnotes
	bootinfo['profile'] = webnotes.user.load_profile()
	webnotes.session['data']['profile'] = bootinfo['profile']
	
def add_home_page(bootinfo, doclist):
	"""load home page"""
	import webnotes
	import webnotes.widgets.page
	import webnotes.cms

	home_page = webnotes.cms.get_home_page(webnotes.session['user']) or 'Login Page'

	try:
		page_doclist = webnotes.widgets.page.get(home_page)
	except webnotes.PermissionError, e:
		page_doclist = webnotes.widgets.page.get('Login Page')
		
	bootinfo['home_page_html'] = page_doclist[0].content
	bootinfo['home_page'] = page_doclist[0].name
	doclist += page_doclist
