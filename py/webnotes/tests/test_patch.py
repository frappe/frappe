"""
test with erpnext
"""

import unittest, sys

sys.path.append('lib/py')

import webnotes
webnotes.connect()

import webnotes.modules.patch_handler
from webnotes.modules.patch_handler import run_all, run_single, reload_doc

class TestPatch(unittest.TestCase):
	def test_run_single(self):
		webnotes.modules.patch_handler.log_list = []
		run_single('patches.jan_mar_2012.subdomain_login_patch')
		print webnotes.modules.patch_handler.log_list
		self.assertTrue(webnotes.conn.sql("""select patch from __PatchLog
			where patch='subdomain_login_patch'"""))
		webnotes.conn.sql(	"""delete from __PatchLog
				where patch='subdomain_login_patch'""")

	def test_reload(self):
		webnotes.modules.patch_handler.log_list = []
		mod1 = webnotes.conn.sql("""select modified from tabDocType
			where name='Print Format'""")[0][0]
		reload_doc({"module":"core", "dt":"DocType", "dn":"Print Format"})
		print webnotes.modules.patch_handler.log_list
		mod2 = webnotes.conn.sql("""select modified from tabDocType
			where name='Print Format'""")[0][0]
		self.assertNotEquals(mod1, mod2)

	def test_multiple(self):
		webnotes.modules.patch_handler.log_list = []
		run_all([{"patch_file":"subdomain_login_patch", "patch_module":"patches.jan_mar_2012"}])
		webnotes.conn.sql(	"""delete from __PatchLog
				where patch='subdomain_login_patch'""")
		print webnotes.modules.patch_handler.log_list

if __name__=='__main__':
	unittest.main()