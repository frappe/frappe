import os,sys

cgi_bin_path = os.path.sep.join(__file__.split(os.path.sep)[:-3])

sys.path.append(cgi_bin_path)


		
#
# make a copy of defs.py (if not exists)
#		
def copy_defs():
	global cgi_bin_path
	if not os.path.exists(os.path.join(cgi_bin_path, 'webnotes', 'defs.py')):
		ret = os.system('cp '+ os.path.join(cgi_bin_path, 'webnotes', 'defs_template.py')+\
			' '+os.path.join(cgi_bin_path, 'webnotes', 'defs.py'))
		print 'Made copy of defs.py'

#
# Main Installer Class
#
class Installer:
	def __init__(self, root_login, root_password):

		import webnotes
		import webnotes.db
		import webnotes.defs
	
		self.root_password = root_password
		from webnotes.model.db_schema import DbManager
		
		self.conn = webnotes.db.Database(user=root_login, password=root_password)			
		webnotes.conn=self.conn
		webnotes.session= {'user':'Administrator'}
		self.dbman = DbManager(self.conn)
		self.mysql_path = hasattr(webnotes.defs, 'mysql_path') and webnotes.defs.mysql_path or ''

	#
	# run framework related cleanups
	#
	def framework_cleanups(self, target):

		import webnotes
		self.dbman.drop_table('__DocTypeCache')
		webnotes.conn.sql("""create table `__DocTypeCache` 
			(name VARCHAR(120), modified DATETIME, content TEXT, server_code_compiled TEXT)""")

		self.dbman.drop_table('__SessionCache')
		webnotes.conn.sq.("""create table `__SessionCache` 
			(user VARCHAR(120), country VARCHAR(120), cache LONGTEXT)""")

		create_sessions_table()

		# set the basic passwords
		webnotes.conn.begin()
		webnotes.conn.sql("update tabProfile set password = password('admin') where name='Administrator'")
		webnotes.conn.commit()

	def create_sessions_table(self):
		self.dbman.drop_table('tabSessions')
		webnotes.conn.sql("""CREATE TABLE `tabSessions` (
		  `user` varchar(40) DEFAULT NULL,
		  `sid` varchar(120) DEFAULT NULL,
		  `sessiondata` longtext,
		  `ipaddress` varchar(16) DEFAULT NULL,
		  `lastupdate` datetime DEFAULT NULL,
		  `status` varchar(20) DEFAULT NULL,
		  KEY `sid` (`sid`)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8""")
		
	def import_core_module(self):
		"""
			Imports the "Core" module from .txt file and creates
			Creates profile Administrator
		"""
		import webnotes
		from webnotes.modules import Module
		core = Module('core')

		core.reload('doctype','doctype')
		core.reload('doctype','docfield')
		core.reload('doctype','docperm')
		core.sync_all(verbose=1)
		
	def create_users(self):
		"""
			Create Administrator / Guest
		"""
		webnotes.conn.begin()
		
		from webnotes.model.doc import Document
		p = Document('Profile')
		p.name = p.first_name = 'Administrator'
		p.email = 'admin@localhost'
		p.save(new = 1)
		
		ur = Document('UserRole')
		ur.parent = 'Administrator'
		ur.role = 'Administrator'
		ur.parenttype = 'Profile'
		ur.parentfield = 'userroles'
		p.enabled = 1
		ur.save(1)

		p = Document('Profile')
		p.name = p.first_name = 'Guest'
		p.email = 'guest@localhost'
		p.enabled = 1
		p.save(new = 1)
		
		ur = Document('UserRole')
		ur.parent = 'Guest'
		ur.role = 'Guest'
		ur.parenttype = 'Profile'
		ur.parentfield = 'userroles'
		ur.save(1)

		webnotes.conn.commit()

	def get_db_password(self, db_name):
		"""
			Get the db_password by method
		"""
		import webnotes.defs
		if hasattr(webnotes.defs, 'get_db_password'):
			return webnotes.defs.get_db_password(db_name)
		if hasattr(webnotes.defs, 'db_password'):
			return webnotes.defs.db_password
		return ''

	def import_from_db(self, target, source_path='', password = 'admin', verbose=0):
		"""
		a very simplified version, just for the time being..will eventually be deprecated once the framework stabilizes.
		"""
		import webnotes.defs		
		
		# delete user (if exists)
		self.dbman.delete_user(target)

		# create user and db
		self.dbman.create_user(target,self.get_db_password(target))
		if verbose: print "Created user %s" % target
	
		# create a database
		self.dbman.create_database(target)
		if verbose: print "Created database %s" % target
		
		# grant privileges to user
		self.dbman.grant_all_privileges(target,target)
		if verbose: print "Granted privileges to user %s and database %s" % (target, target)

		# flush user privileges
		self.dbman.flush_privileges()

		self.conn.use(target)
		
		# import in target
		if verbose: print "Starting database import..."

		# get the path of the sql file to import
		source_given = True
		if not source_path:
			source_given = False
			source_path = os.path.join(os.path.sep.join(os.path.abspath(webnotes.__file__).split(os.path.sep)[:-3]), 'data', 'Framework.sql')

		self.dbman.restore_database(target, source_path, self.root_password)
		if verbose: print "Imported from database %s" % source_path

		if not source_given:
			if verbose: print "Importing core module..."
			self.import_core_module()
			self.create_users()

		# framework cleanups
		self.framework_cleanups(target)
		if verbose: print "Ran framework startups on %s" % target
		
		return target		

def make_scheduler(root_login, root_password, verbose):
	"""
		Make the database where all scheduler events will be stored from multiple datbases
		See webnotes.utils.scheduler for more information
	"""
	conn = webnotes.db.Database(user=root_login, password=root_password)			

	from webnotes.model.db_schema import DbManager

	dbman = DbManager(conn)
	
	# delete user (if exists)
	dbman.delete_user('master_scheduler')

	# create user and db
	dbman.create_user('master_scheduler', getattr(webnotes.defs,'scheduler_password',None))
	if verbose: print "Created user master_scheduler"

	# create a database
	dbman.create_database('master_scheduler')
	if verbose: print "Created database master_scheduler" 

	# grant privileges to user
	dbman.grant_all_privileges('master_scheduler','master_scheduler')

	# flush user privileges
	dbman.flush_privileges()
	
	conn.use('master_scheduler')
	
	# create events table
	conn.sql("""create table Event(
		`db_name` varchar(60),
		`event` varchar(180),
		`interval` int(20),
		`next_execution` timestamp,
		`recurring` int(1),
		primary key (`db_name`, `event`),
		index next_execution(next_execution)
		)""")
	
	conn.sql("""create table EventLog(
		`db_name` varchar(180), 
		`event` varchar(180),
		`executed_on` timestamp,
		`log` text,
		index executed_on(executed_on))
	""")
#
# load the options
#
def get_parser():
	from optparse import OptionParser

	parser = OptionParser(usage="usage: %prog [options] ROOT_LOGIN ROOT_PASSWORD DBNAME")
	parser.add_option("-x", "--database-password", dest="password", default="admin", help="Optional: New password for the Framework Administrator, default 'admin'")	
	parser.add_option("-s", "--source", dest="source_path", default=None, help="Optional: Path of the sql file from which you want to import the instance, default 'data/Framework.sql'")
	
	return parser


#
# execution here
#
if __name__=='__main__':

	parser = get_parser()
	(options, args)	= parser.parse_args()
	
	try:
	
		import webnotes
		import webnotes.db
		import webnotes.defs
	except ImportError:
		copy_defs()
		import webnotes
		import webnotes.db
		import webnotes.defs

	if len(args)==3:
		
		root_login, root_password, db_name = args[0], args[1], args[2]
		
		if db_name=='master_scheduler':
			make_scheduler(root_login, root_password, 1)
		else:
			inst = Installer(root_login, root_password)

			inst.import_from_db(db_name, source_path=options.source_path, \
				password = options.password, verbose = 1)


			print "Database created, please edit defs.py to get started"		
	else:
		parser.print_help()
		
