# auto masters
# _ + fieldname is the table
# 'value' is the column name, pkey

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
		fl = webnotes.conn.sql("select fieldname from tabDocField where fieldtype='Data' and options='Suggest' and parent=%s", dt)
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
