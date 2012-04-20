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

install_docs = [
	{'doctype':'Module Def', 'name': 'Core', 'module_name':'Core'},

	# roles
	{'doctype':'Role', 'role_name': 'Administrator', 'name': 'Administrator'},
	{'doctype':'Role', 'role_name': 'All', 'name': 'All'},
	{'doctype':'Role', 'role_name': 'System Manager', 'name': 'System Manager'},
	{'doctype':'Role', 'role_name': 'Report Manager', 'name': 'Report Manager'},
	{'doctype':'Role', 'role_name': 'Guest', 'name': 'Guest'},
	
	# profiles
	{'doctype':'Profile', 'name':'Administrator', 'first_name':'Administrator', 
		'email':'admin@localhost', 'enabled':1},
	{'doctype':'Profile', 'name':'Guest', 'first_name':'Guest',
		'email':'guest@localhost', 'enabled':1},
		
	# userroles
	{'doctype':'UserRole', 'parent': 'Administrator', 'role': 'Administrator', 
		'parenttype':'Profile', 'parentfield':'userroles'},
	{'doctype':'UserRole', 'parent': 'Guest', 'role': 'Guest', 
		'parenttype':'Profile', 'parentfield':'userroles'}
]