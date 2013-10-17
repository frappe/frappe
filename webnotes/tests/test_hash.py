from webnotes import HashAuthenticatedCommand, whitelist

class HashCommand(HashAuthenticatedCommand):

	def __call__(self, *args, **kwargs):
		signature = kwargs.pop('signature')
		if self.verify_signature(kwargs, signature):
			return self.command(*args, **kwargs)
		else:
			raise Exception

	def command(self, *args, **kwargs):
		return "Hello World"

	def get_nonce(self):
		return "5"

hash_cmd = (HashCommand())

# @whitelist(allow_guest=True)
# def get_hash():
# 	return hash_cmd.get_signature({})
# 
# def get_nonce(self):
# 	return "5"

@whitelist(allow_guest=True)
@HashAuthenticatedCommand(nonce_function=get_nonce)
def hash_cmd(*args, **kwargs):
	return "Hello World"
