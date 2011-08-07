

def get_model_path(name):
	return webnotes.conn.sql("""
		select path from __module_index
		where name=%s
	""", name)[0][0]

class ModelIndex:
	"""
		Model Indexer walks the app folder and indexes all models and
		keeps the list in a table __model_index (name, path, tstamp)
	"""	
	def index_all(self):
		"""
			Walk the app folder and find all .model files
		"""
		import os
		for walk_tuple in os.walk(webnotes.app_path):
			for model_file in filter(lambda x: x.endswith('.model'), walk_tuple[2]):
				fpath = os.path.join(walk_tuple[0], model_file)
				
				# read the collection
				fc = FileCollection(fpath)
				
				self.insert(fc.type, fpath, get_file_tstamp())
					
	def insert(self, name, path, tstamp):
		"""
			Insert a new ModelDef
		"""
		webnotes.conn.sql("""
			insert into __model_index(name, path, tstamp)
			values (%s, %s, %s)
			on duplicate key 
				update __model_index set tstamp=%s where name=%s
		""", (name, path, tstamp, tstamp, name))
	
	def create(self):
		webnotes.conn.sql("""
			create table __model_index (
				name varchar(180) primary key not null,
				path varchar(240) unique not null,
				tstamp varchar(20),
			)
		""")