_store=None

def store():
	"""
		Return the redis datastore
	"""
	import redis
	global _store

	if not _store:
		_store = redis.Redis('localhost', port=6379, db=0)
	
	return _store
