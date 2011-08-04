"""
Run tests from modules. Sets up database connection, modules path and session before running test

Usage: from shell, run

python tests.py [test modules]

Options:
	test modules: list of modules separated by space
	
if no modules are specified, it will run all "tests.py" files from all modules
"""

import os
import unittest


class TestCase(unittest.TestCase):
	def setUp(self):
		import webnotes
		webnotes.conn.begin()
		webnotes.debug_log = []

	def tearDown(self):
		import webnotes
		webnotes.conn.rollback()
		if webnotes.debug_log:
			print '\n----'.join(webnotes.debug_log)


def set_paths():
	import sys
	# webnotes path
	sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

	import webnotes.defs

	if webnotes.defs.__dict__.get('modules_path'):
		sys.path.append(webnotes.defs.modules_path)

def get_tests():
	"""
	Returns list of test modules identified by "test*.py"
	"""
	import webnotes
	import webnotes.defs
	
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
	set_paths()
	import webnotes
	
	from webnotes.db import Database
	webnotes.conn = Database()
	webnotes.session = {'user':'Administrator'}

if __name__=='__main__':
	import sys
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
