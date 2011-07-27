import webnotes
def runserverobj(arg=None):
	import webnotes.widgets.form
	webnotes.widgets.form.runserverobj()

def logout():
	webnotes.login_manager.logout()
