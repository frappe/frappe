import nts


# no context object is accepted
def get_context():
	context = nts._dict()
	context.body = "Custom Content"
	return context
