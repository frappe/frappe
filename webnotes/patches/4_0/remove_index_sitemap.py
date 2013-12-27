import webnotes

def execute():
	if webnotes.conn.exists("Website Sitemap", "index"):
		webnotes.delete_doc("Website Sitemap", "index", ignore_permissions=True)
	