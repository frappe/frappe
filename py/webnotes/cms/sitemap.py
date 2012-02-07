# to generate sitemaps

frame_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s
</urlset>"""

link_xml = """\n<url><loc>%s</loc><lastmod>%s</lastmod></url>"""

# generate the sitemap XML
def generate(domain):
	global frame_xml, link_xml
	import urllib
	import webnotes

	# settings
	max_doctypes = 10
	max_items = 1000
	
	site_map = ''
	page_list = []
	
	if domain:
		# list of all Guest pages (static content)
		for r in webnotes.conn.sql("""SELECT distinct t1.name, t1.modified 
				FROM tabPage t1, `tabPage Role` t2
				WHERE t1.name = t2.parent
				and t2.role = 'Guest'
				ORDER BY modified DESC"""):

			page_url = domain + '#!' + urllib.quote(r[0])
			site_map += link_xml % (page_url, r[1].strftime('%Y-%m-%d'))
		

	return frame_xml % site_map
