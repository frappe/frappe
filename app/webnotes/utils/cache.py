"""
Simple Caching:

Stores key-value pairs in database and enables simple caching

get_item(key).get() returns the cached value if not expired (else returns null)
get_item(key).set(interval = 60000) sets a value to cache, expiring after x seconds
get_item(key).clear() clears an old value
setup() sets up cache
"""

import webnotes

class CacheItem:
	def __init__(self, key):
		"""create a new cache"""
		self.key = key
	
	def get(self):
		"""get value"""
		try:
			return webnotes.conn.sql("select `value` from __CacheItem where `key`=%s and expires_on > NOW()", self.key)[0][0]
		except Exception:
			return None
	
	def set(self, value, interval=6000):
		"""set a new value, with interval"""
		try:
			self.clear()
			webnotes.conn.sql("""INSERT INTO 
					__CacheItem (`key`, `value`, expires_on) 
				VALUES 
					(%s, %s, addtime(now(), sec_to_time(%s)))
				""", (self.key, str(value), interval))
		except Exception, e:
			if e.args[0]==1146: 
				setup()
				self.set(value, interval)
			else: raise e
	
	def clear(self):
		"""clear the item"""
		webnotes.conn.sql("delete from __CacheItem where `key`=%s", self.key)

def setup():
	webnotes.conn.commit()
	webnotes.conn.sql("""create table __CacheItem(
		`key` VARCHAR(180) NOT NULL PRIMARY KEY,
		`value` TEXT,
		`expires_on` TIMESTAMP
		)""")
	webnotes.conn.begin()

def get_item(key):
	"""returns get CacheItem object"""
	return CacheItem(key)
	pass