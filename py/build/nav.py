class Nav:
	"""
		Build sitemap / navigation tree
	"""
	page_info_template = {
		'description': None,
		'keywords': None,
		'title': 'No Title Set'
	}
	def __init__(self):
		"""
			write out the nav
		"""
		import json, os
		
		self.data = {}
		if os.path.exists('config/sitenav.json'):
			nfile = open('config/sitenav.json')
			self.data = json.loads(nfile.read())
			nfile.close()
	
	def page_info(self):
		"""
			return dict with href as the key
		"""
		ret = {}
		import copy
		
		ul = copy.deepcopy(self.data)
		
		for li in ul:
			ret[li.get('href')] = li
			
			# has subitems, loop
			if li.get('subitems'):
				for lia in li.get('subitems'):
					if not lia.get('href') in ret.keys():
						ul.append(lia)
	
		return ret
	
	def html(self, list_class=''):
		"""
			return nested lists <ul> in html
		"""
		self.list_class = list_class
		return self.make_list(self.data)
	
	def make_list(self, ul):
		"""
			return a list with <li> and <a> elements
		"""
		lis = []
		link_html = '<a href="%(href)s" title="%(title)s">%(label)s</a>'
		
		for li in ul:
			if not 'title' in li:
				li['title'] = 'No Title'
			
			if 'subitems' in li:
				h = ('\t<li>' + link_html + self.make_list(li['subitems']) +'</li>') % li
			else:
				h = ('\t<li>' + link_html + '</li>') % li
			
			lis.append(h)
			
		return '\n<ul class="%s">\n%s\n</ul>' % (self.list_class, '\n'.join(lis))