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
Run tests from modules. Sets up database connection, modules path and session before running test

Usage: from shell, run

python tests.py [test modules]

Options:
	test modules: list of modules separated by space
	
if no modules are specified, it will run all "tests.py" files from all modules
"""

import sys, os
import unittest

# webnotes path
sys.path.append('lib/py')

# modules path
import webnotes
import webnotes.defs

if webnotes.defs.__dict__.get('modules_path'):
	sys.path.append(webnotes.defs.modules_path)

def get_tests():
	"""
	Returns list of test modules identified by "test*.py"
	"""
	ret = []
	for walk_tuple in os.walk(webnotes.defs.modules_path):
		for test_file in filter(lambda x: x.startswith('test') and x.endswith('.py'), walk_tuple[2]):
			dir_path = os.path.relpath(walk_tuple[0], webnotes.defs.modules_path)
			if dir_path=='.':
				ret.append(test_file[:-3])
			else:
				ret.append(dir_path.replace('/', '.') + '.' + test_file[:-3])			
	return ret

def setup():
	"""
	Sets up connection and session
	"""
	from webnotes.db import Database
	webnotes.conn = Database()
	webnotes.session = {'user':'Administrator', 'profile':'Administrator'}

if __name__=='__main__':
	setup()
		
	if len(sys.argv) > 1:
		tests_list = sys.argv[1:]
		
		# for unittest.main
		sys.argv = sys.argv[:1]
	else:
		tests_list = get_tests()
	
	for tests in tests_list:
		exec 'from %s import *' % str(tests)

	unittest.main()
