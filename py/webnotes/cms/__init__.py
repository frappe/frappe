def get_home_page(user=None):
	"""get home page for user"""
	if not user:
		user = 'Guest'
	import webnotes
	hpl = webnotes.conn.sql("""select home_page 
		from `tabDefault Home Page` 
		where parent='Control Panel' 
		and role in ('%s') order by idx asc limit 1""" % "', '".join(webnotes.get_roles(user)))
		
	if hpl:
		return hpl[0][0]
	else:
		return webnotes.conn.get_value('Control Panel',None,'home_page') or 'Login Page'	