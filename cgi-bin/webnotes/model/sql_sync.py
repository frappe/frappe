"""
Sync sql files (that contain triggers, stored procs etc) into the database
calling sync will walk through all .sql files in the modules file structure
and execute them if they are not executed or their timestamps have changed

All sql timestamps will be saved in a table '__sql_timestamps'
"""

# modules path
import webnotes
import webnotes.defs

def get_sql_files():
	"""
		Returns list of .sql files from
	"""
	import os
	ret = []
	for walk_tuple in os.walk(webnotes.defs.modules_path):
		if os.path.split(walk_tuple[0])[-1]=='doctype':
			for sql_file in filter(lambda x: x.endswith('.sql'), walk_tuple[2]):
				ret.append[os.path.join(walk_tuple[0], sql_file)]
	return ret
	
def run_sql_file(fn):
	"""
		Checks if timestamp matches, if not runs it
	"""
	from webnotes.modules import ModuleFile
	mf = ModuleFile(fn)
	if mf.is_new():
		webnotes.conn.sql(mf.read())
		mf.update()
			
def get_sql_timestamp(fn):
	"""
		Returns the last updated timestamp of the sql file
		from the __sql_timestamps table. If the table does not
		exist, it will create it
	"""
	try:
		ts = webnotes.conn.sql("select tstamp from __sql_timestamp where file_name=%s", fn)
		if ts:
			return ts[0][0]
	except Exception, e:
		if e.args[0]==1147:
			# create the table
			webnotes.conn.commit()
			webnotes.conn.sql("""
				create table __sql_timestamp (
					file_name varchar(320) primary key, 
					tstamp varchar(40))""")
			webnotes.conn.begin()
		else:
			raise e
			
def update_sql_timestamp(fn, ts):
	pass