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

# Modules
# -----------

def get_module_items(mod, only_dt=0):
	dl = []
	if only_dt:
		transfer_types = ['DocType']
	else:
		transfer_types = ['Role', 'Page', 'DocType', 'DocType Mapper', 'Search Criteria']
		dl = ['Module Def,'+mod]
	
	for dt in transfer_types:
		try:
			dl2 = sql('select name from `tab%s` where module="%s"' % (dt,mod))
			dl += [(dt+','+e[0]) for e in dl2]
		except:
			pass

	if not only_dt:
		dl1 = sql('select doctype_list from `tabModule Def` where name=%s', mod)
		dl += dl1[0][0].split('\n')
	
	# build finally
	dl = [e.split(',') for e in dl]
	dl = [[e[0].strip(), e[1].strip()] for e in dl] # remove blanks
	return dl