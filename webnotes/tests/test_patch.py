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