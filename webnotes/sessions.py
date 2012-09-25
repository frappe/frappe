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
Boot session from cache or build

Session bootstraps info needed by common client side activities including
permission, homepage, control panel variables, system defaults etc
"""
import webnotes
import conf
import json

@webnotes.whitelist()
def clear(user=None):
	"""clear all cache"""
	clear_cache(user)
	webnotes.response['message'] = "Cache Cleared"

def clear_cache(user=''):
	"""clear cache"""
	webnotes.cache().flush_keys("bootinfo:")
	webnotes.cache().flush_keys("doctype:")

	# doctype cache
	from webnotes.utils.cache import clear
	clear()

	# rebuild a cache for guest
	if webnotes.session:
		webnotes.session['data'] = {}

def get():
	"""get session boot info"""
	
	# check if cache exists
	if not getattr(conf,'auto_cache_clear',None):
		cache = webnotes.cache().get_value('bootinfo:' + webnotes.session.user)
		if cache:
			return cache
	
	# if not create it
	from webnotes.boot import get_bootinfo
	bootinfo = get_bootinfo()
	webnotes.cache().set_value('bootinfo:' + webnotes.session.user, bootinfo)
		
	return bootinfo