"""
Boot session from cache or build

Session bootstraps info needed by common client side activities including
permission, homepage, control panel variables, system defaults etc
"""
import webnotes

@webnotes.whitelist()
def clear():
	"""clear all cache"""
	clear_cache()
	webnotes.response['message'] = "Cache Cleared"

def clear_cache(user=''):
	"""clear cache"""
	if user:
		webnotes.conn.sql("delete from __SessionCache where user=%s", user)
		webnotes.conn.sql("update tabSessions set sessiondata=NULL where user=%s", user)
	else:
		webnotes.conn.sql("delete from __SessionCache")
		webnotes.conn.sql("update tabSessions set sessiondata=NULL")
	
	# rebuild a cache for guest
	
	if webnotes.session:
		webnotes.session['data'] = {}
	
def get():
	"""get session boot info"""
	import webnotes.defs
	
	# get country
	country = webnotes.session['data'].get('ipinfo', {}).get('countryName', 'Unknown Country')

	# check if cache exists
	if not getattr(webnotes.defs,'auto_cache_clear',None):
		cache = load(country)
		if cache:
			return cache
	
	# if not create it
	import webnotes.boot
	bootinfo = webnotes.boot.get_bootinfo()
	add_to_cache(bootinfo, country)
		
	return bootinfo

def load(country):
	"""load from cache"""	
	try:
		sd = webnotes.conn.sql("select cache from __SessionCache where user='%s' %s" % (webnotes.session['user'], (country and (" and country='%s'" % country) or '')))
		if sd:
			return eval(sd[0][0])
		else:
			return None
	except Exception, e:
		if e.args[0]==1146:
			make_cache_table()
		else:
			raise e
	
def add_to_cache(sd, country):
	"""add to cache"""
	import webnotes.model.utils

	if sd.get('docs'):
		sd['docs'] = webnotes.model.utils.compress(sd['docs'])

	# delete earlier (?)
	webnotes.conn.sql("delete from __SessionCache where user=%s and country=%s", (webnotes.session['user'], country))

	# make new
	webnotes.conn.sql("insert into `__SessionCache` (user, country, cache) VALUES (%s, %s, %s)", (webnotes.session['user'], country, str(sd)))
