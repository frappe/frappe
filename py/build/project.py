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

verbose = False
import os				

def generate_hash():
	"""
		 Generates random hash for session id
	"""
	import hashlib, time
	return hashlib.sha224(str(time.time())).hexdigest()
	
def build():
	"""concat / minify js files"""
	from py.build.bundle import Bundle
	bundle = Bundle()
	bundle.make()
	update_version()
	import webnotes.cms.make
	webnotes.cms.make.make(get_version())

def get_version():
	"""get from version.num file and increment it"""
	if os.path.exists('version.num'):
		with open('version.num', 'r') as vfile:
			version = vfile.read()
	else:
		version = generate_hash()

	return version

def update_version():
	"""incremenet version by 1"""
	version = generate_hash()
	with open('version.num', 'w') as vfile:
		vfile.write(str(version))
		
	return version