import webnotes

def get_context(context):
	return {
		"title": webnotes._("Login"),
		"content": context.template.render(context)
	}