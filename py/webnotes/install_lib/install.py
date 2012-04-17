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

# called from wnf.py
# lib/wnf.py --install [rootpassword] [dbname] [source]

import os,sys

class Installer:
	def __init__(self, root_login, root_password):

		import webnotes
		import webnotes.db
	
		self.root_password = root_password
		from webnotes.model.db_schema import DbManager
		
		self.conn = webnotes.db.Database(user=root_login, password=root_password)			
		webnotes.conn=self.conn
		webnotes.session= {'user':'Administrator'}
		self.dbman = DbManager(self.conn)

	def import_from_db(self, target, source_path='', password = 'admin', verbose=0):
		"""
		a very simplified version, just for the time being..will eventually be deprecated once the framework stabilizes.
		"""
		import conf
		
		# delete user (if exists)
		self.dbman.delete_user(target)

		# create user and db
		self.dbman.create_user(target, conf.db_password)
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

		# fresh app
		if 'Framework.sql' in source_path:
			from webnotes.model.sync import sync_install
			print "Building tables from all module..."
			sync_install()

		# framework cleanups
		self.framework_cleanups(target)
		if verbose: print "Ran framework startups on %s" % target
		
		return target	

	def framework_cleanups(self, target):
		"""create framework internal tables"""
		import webnotes
		self.create_sessions_table()
		self.create_scheduler_log()
		self.create_session_cache()
		self.create_cache_item()

		# set the basic passwords
		webnotes.conn.begin()
		webnotes.conn.sql("""update tabProfile set password = password('admin') 
			where name='Administrator'""")
		webnotes.conn.commit()

	def create_sessions_table(self):
		"""create sessions table"""
		import webnotes
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
	
	def create_scheduler_log(self):
		import webnotes
		self.dbman.drop_table('__SchedulerLog')
		webnotes.conn.sql("""create table __SchedulerLog (
			`timestamp` timestamp,
			method varchar(200),
			error text
		) engine=MyISAM""")
	
	def create_session_cache(self):
		import webnotes
		self.dbman.drop_table('__SessionCache')
		webnotes.conn.sql("""create table `__SessionCache` ( 
			user VARCHAR(120), 
			country VARCHAR(120), 
			cache LONGTEXT)""")

	def create_cache_item(self):
		import webnotes
		self.dbman.drop_table('__CacheItem')
		webnotes.conn.sql("""create table __CacheItem(
			`key` VARCHAR(180) NOT NULL PRIMARY KEY,
			`value` TEXT,
			`expires_on` TIMESTAMP
			)""")
			

		
