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
	
def add_to_cache(bootinfo, country):
	"""add to cache"""
	import webnotes.model.utils

	if bootinfo.get('docs'):
		bootinfo['docs'] = webnotes.model.utils.compress(bootinfo['docs'])

	# delete earlier (?)
	webnotes.conn.sql("""delete from __SessionCache where user=%s 
		and country=%s""", (webnotes.session['user'], country))

	# make new
	webnotes.conn.sql("""insert into `__SessionCache` 
		(user, country, cache) VALUES (%s, %s, %s)""", \
			(webnotes.session['user'], country, str(bootinfo)))
