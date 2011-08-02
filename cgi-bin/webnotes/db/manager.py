class DbManager:
	"""
	Basically, a wrapper for oft-used mysql commands. like show tables,databases, variables etc... 

	#TODO:
		0.  Simplify / create settings for the restore database source folder 
		0a. Merge restore database and extract_sql(from webnotes_server_tools).
		1. Setter and getter for different mysql variables.
		2. Setter and getter for mysql variables at global level??
	"""	
	def __init__(self,conn):
		"""
		Pass root_conn here for access to all databases.
		"""
 		if conn:
 			self.conn = conn
		

	def get_variables(self,regex):
		"""
		Get variables that match the passed pattern regex
		"""
		return list(self.conn.sql("SHOW VARIABLES LIKE '%s'"%regex))

			
	def get_table_schema(self,table):
		"""
		Just returns the output of Desc tables.
		"""
		return list(self.conn.sql("DESC %s"%table))
		
			
	def get_tables_list(self,target):	
		"""
		
		"""
		try:
			self.conn.use(target)
			res = self.conn.sql("SHOW TABLES;")
			table_list = []
			for table in res:
				table_list.append(table[0])
			return table_list

		except Exception,e:
			raise e

	def create_user(self,user,password):
		#Create user if it doesn't exist.
		try:
			if password:
				self.conn.sql("CREATE USER '%s'@'localhost' IDENTIFIED BY '%s';" % (user[:16], password))
			else:
				self.conn.sql("CREATE USER '%s'@'localhost';"%user[:16])
		except Exception, e:
			raise e


	def delete_user(self,target):
	# delete user if exists
		try:
			self.conn.sql("DROP USER '%s'@'localhost';" % target)
		except Exception, e:
			if e.args[0]==1396:
				pass
			else:
				raise e

	def create_database(self,target):
		
		try:
			self.conn.sql("CREATE DATABASE IF NOT EXISTS `%s` ;" % target)
		except Exception,e:
			raise e

	def grant_all_privileges(self,target,user):
		try:
			self.conn.sql("GRANT ALL PRIVILEGES ON `%s` . * TO '%s'@'localhost';" % (target, user))
		except Exception,e:
			raise e

	def grant_select_privilges(self,db,table,user):
		try:
			if table:
				self.conn.sql("GRANT SELECT ON %s.%s to '%s'@'localhost';" % (db,table,user))
			else:
				self.conn.sql("GRANT SELECT ON %s.* to '%s'@'localhost';" % (db,user))
		except Exception,e:
			raise e

	def flush_privileges(self):
		try:
			self.conn.sql("FLUSH PRIVILEGES")
		except Exception,e:
			raise e


	def get_database_list(self):
		try:
			db_list = []
			ret_db_list = self.conn.sql("SHOW DATABASES")
			for db in ret_db_list:
				if db[0] not in ['information_schema', 'mysql', 'test', 'accounts']:
					db_list.append(db[0])
			return db_list
		except Exception,e:
			raise e

	def restore_database(self,target,source,root_password):
		import webnotes.defs
		mysql_path = getattr(webnotes.defs, 'mysql_path', None)
		mysql = mysql_path and os.path.join(mysql_path, 'mysql') or 'mysql'
		
		try:
			ret = os.system("%s -u root -p%s %s < %s"%(mysql, root_password.replace(" ", "\ "), target, source))
		except Exception,e:
			raise e

	def drop_table(self,table_name):
		try:
			self.conn.sql("DROP TABLE IF EXISTS %s "%(table_name))
		except Exception,e:
			raise e	

	def set_transaction_isolation_level(self,scope='SESSION',level='READ COMMITTED'):
		#Sets the transaction isolation level. scope = global/session
		try:
			self.conn.sql("SET %s TRANSACTION ISOLATION LEVEL %s"%(scope,level))
		except Exception,e:
			raise e
