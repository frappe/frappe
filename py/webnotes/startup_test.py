"""
	startup info for the app
	
	client needs info that is static across all users
	and user specific info like roles and defaults
	
	so calling will be:
	index.cgi?cmd=webnotes.startup.common_info
	index.cgi?cmd=webnotes.startup.user_info&user=x@y.com
	
	to clear startup,
	you must clear all files in the vcs starting with index.cgi?cmd=webnotes.startup
"""

import webnotes


def get_letter_heads():
	"""
		get letter head
	"""
	import webnotes
	try:
		lh = {}
		ret = webnotes.conn.sql("select name, content from `tabLetter Head` where ifnull(disabled,0)=0")
		for r in ret:
			lh[r[0]] = r[1]
		return lh
	except Exception, e:
		if e.args[0]==1146:
			return {}
		else:
			raise Exception, e
	



def get_content_user():
	"""
		get user specific content
	"""
	import webnotes
	import webnotes.utils
	import webnotes.widgets.page
	import webnotes.widgets.menus
	
	user = webnotes.form_dict['user']
	doclist, ret = [], {}

	webnotes.conn.begin()
	ret['profile'] = webnotes.user.load_profile()
	home_page = webnotes.user.get_home_page()
	if home_page:
		doclist += webnotes.widgets.page.get(home_page)
	
	ret['sysdefaults'] = webnotes.utils.get_defaults()
	ret['home_page'] = home_page or ''
	
	# role-wise menus
	ret['start_items'] = webnotes.widgets.menus.get_menu_items()
	
	# bundle
	webnotes.session['data']['profile'] = ret['profile']
	if webnotes.session['data'].get('ipinfo'):
		ret['ipinfo'] = webnotes.session['data']['ipinfo']

	webnotes.conn.commit()
	
	webnotes.response['docs'] = doclist
	
	return ret

def get_content_common():
	"""
		build common startup info
	"""

	import webnotes
	import webnotes.model.doc
	import webnotes.model.doctype
	import webnotes.model
	
	doclist, ret = [], {}
	doclist += webnotes.model.doc.get('Control Panel')	
	doclist += webnotes.model.doctype.get('Event')
	doclist += webnotes.model.doctype.get('Search Criteria')

	cp = doclist[0]
	ret['account_name'] = cp.account_id or ''
	ret['letter_heads'] = get_letter_heads()
	ret['dt_labels'] = webnotes.model.get_dt_labels()

	webnotes.response['docs'] = doclist

	return ret


def common_info():
	"""
		get common startup info (from version or live)
	"""
	get_info('index.cgi?cmd=webnotes.startup.common_info', 'common')

def user_info():
	"""
		get user info
	"""
	user = webnotes.form_dict['user']
	get_info('index.cgi?cmd=webnotes.startup.user_info&user='+user, 'user')

def get_info(fname, key):
	"""
		get info from version or re-build
	"""
	from build.version import VersionControl

	vc = VersionControl()

	# from versions (same static)
	
	if vc.exists(fname):
		content = vc.get_file(fname)['content']
	else:
		content = globals().get('get_content_'+key)()
		import json
		content = json.dumps(content)

		# add in vcs
		vc.add(fname=fname, content=content)
		vc.commit()
	
	vc.close()
	
	webnotes.response['content'] = content
	return





def clear_info(info_type=None):
	"""
		clear startup info and force a new version
		
		parameter: info_type = 'user' or 'common' or 'all'
	"""
	if not info_type:
		info_type = webnotes.form_dict.get('info_type')
		
	from build.version import VersionControl
	vc = VersionControl()

	flist = []

	if info_type=='common':
		flist = ['index.cgi?cmd=webnotes.startup.common_info']
	elif info_type=='user':
		flist = [f[0] for f in vc.repo.sql("""select fname from files where fname like ?""",\
		 	('index.cgi?cmd=webnotes.startup.user_info%',))]
	elif info_type=='all':
		flist = [f[0] for f in vc.repo.sql("""select fname from files where fname like ?""",\
		 	('index.cgi?cmd=webnotes.startup%',))]	
	else:
		webnotes.msgprint("info_type not found: %s" % info_type)
	
	for f in flist:
		print 'clearing %s' % f
		vc.remove(f)
		
	vc.commit()
	vc.close()