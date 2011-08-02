import webnotes

# -------------------------------------------------
# sync table - called from form.py
# -------------------------------------------------

def updatedb(dt, archive=0):
	"""
	Syncs a `DocType` to the table
	   * creates if required
	   * updates columns
	   * updates indices
	"""
	res = webnotes.conn.sql("select ifnull(issingle, 0) from tabDocType where name=%s", dt)
	if not res:
		raise Exception, 'Wrong doctype "%s" in updatedb' % dt
	
	if not res[0][0]:
		from webnotes.db.table import DatabaseTable
		webnotes.conn.commit()
		tab = DatabaseTable(dt, archive and 'arc' or 'tab')
		tab.sync()
		webnotes.conn.begin()

# patch to remove foreign keys
# ----------------------------

def remove_all_foreign_keys():
	webnotes.conn.sql("set foreign_key_checks = 0")
	webnotes.conn.commit()
	for t in webnotes.conn.sql("select name from tabDocType where ifnull(issingle,0)=0"):
		from webnotes.db.table import DatabaseTable
		dbtab = DatabaseTable(t[0])
		try:
			fklist = dbtab.get_foreign_keys()
		except Exception, e:
			if e.args[0]==1146:
				fklist = []
			else:
				raise e
				
		for f in fklist:
			webnotes.conn.sql("alter table `tab%s` drop foreign key `%s`" % (t[0], f[1]))