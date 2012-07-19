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

# auto masters
# _ + fieldname is the table
# 'value' is the column name, pkey

from __future__ import unicode_literals
import webnotes

# create masters for a doctype
def create_auto_masters(dt):
	fl = webnotes.conn.sql("select fieldname from tabDocField where fieldtype='Data' and options='Suggest' and parent=%s", dt)
	for f in fl:
		make_auto_master(f[0])

# create master table
def make_auto_master(fieldname):
	try:
		webnotes.conn.sql("select `value` from `__%s` limit 1" % fieldname)
	except Exception, e:
		if e.args[0]==1146:
			webnotes.conn.commit()
			webnotes.conn.sql("create table `__%s` (`value` varchar(220), primary key (`value`))" % fieldname)
			webnotes.conn.begin()

# get auto master fields
def get_master_fields(dt):
	if not webnotes.session['data'].get('auto_masters'):
		webnotes.session['data']['auto_masters'] = {}
	
	if webnotes.session['data']['auto_masters'].get(dt, None)==None:
		fl = webnotes.conn.sql("select fieldname from tabDocField where fieldtype='Data' \
			and options='Suggest' and parent=%s", dt)
		webnotes.session['data']['auto_masters'][dt] = fl
	return webnotes.session['data']['auto_masters'][dt]
		

# update value
def update_auto_masters(doc):
	if not doc.doctype:
		return
		
	fl = get_master_fields(doc.doctype)

	# save masters in session cache		
	for f in fl:
		if doc.fields.get(f[0]):
			add_to_master(f[0], doc.fields.get(f[0]))

# add to master
def add_to_master(fieldname, value):
	try:
		webnotes.conn.sql("insert into `__%s` (`value`) values (%s)" % (fieldname,'%s'), value)
	except Exception, e:
		# primary key
		pass
