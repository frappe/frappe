
# remove attachment
#===========================================================================================

def remove_attach():
	import webnotes
	import webnotes.utils.file_manager
	
	fid = webnotes.form.getvalue('fid')
	webnotes.utils.file_manager.delete_file(fid, verbose=1)
	
	# remove from dt dn
	return str(webnotes.utils.file_manager.remove_file_list(webnotes.form.getvalue('dt'), webnotes.form.getvalue('dn'), fid))

# Get Fields - Counterpart to $c_get_fields
#===========================================================================================
def get_fields():
	import webnotes
	r = {}
	args = {
		'select':webnotes.form.getvalue('select')
		,'from':webnotes.form.getvalue('from')
		,'where':webnotes.form.getvalue('where')
	}
	ret = webnotes.conn.sql("select %(select)s from `%(from)s` where %(where)s limit 1" % args)
	if ret:
		fl, i = webnotes.form.getvalue('fields').split(','), 0
		for f in fl:
			r[f], i = ret[0][i], i+1
	webnotes.response['message']=r

# validate link
#===========================================================================================
def validate_link():
	import webnotes
	import webnotes.utils
	
	value, options, fetch = webnotes.form.getvalue('value'), webnotes.form.getvalue('options'), webnotes.form.getvalue('fetch')

	# no options, don't validate
	if not options or options=='null' or options=='undefined':
		webnotes.response['message'] = 'Ok'
		return
		
	if webnotes.conn.sql("select name from `tab%s` where name=%s" % (options, '%s'), value):
	
		# get fetch values
		if fetch:
			webnotes.response['fetch_values'] = [webnotes.utils.parse_val(c) for c in webnotes.conn.sql("select %s from `tab%s` where name=%s" % (fetch, options, '%s'), value)[0]]
	
		webnotes.response['message'] = 'Ok'
