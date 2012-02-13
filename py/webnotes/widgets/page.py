import webnotes
import webnotes.model.doc
import webnotes.model.code

conn = webnotes.conn

class Page:
	"""
	   A page class helps in loading a Page in the system. On loading
	   
	   * Page will import Client Script from other pages where specified by `$import(page_name)`
	   * Execute dynamic HTML if the `content` starts with `#python`
	"""	
	def __init__(self, name):
		self.name = name

	def get_from_files(self, doc, module):
		"""
			Loads page info from files in module
		"""
		# load js
		doc.fields['__script'] = module.get_doc_file('page',doc.name,'.js').read() or doc.script
		doc.script = None

		# load css
		css = module.get_doc_file('page',doc.name,'.css').read()
		if css: doc.style = css
		
		# html
		doc.content = module.get_doc_file('page',doc.name,'.html').read() or doc.content
	
	def get_template(self, template):
		"""
			Returns the page template content
		"""
		ret = '%(content)s'
		# load code from template
		if template:
			from webnotes.modules import Module
			ret = Module(webnotes.conn.get_value('Page Template', template, 'module'))\
				.get_doc_file('Page Template', template, '.html').read()
			if not ret:
				ret = webnotes.conn.get_value('Page Template', template, 'template')
		
		return ret
					
	def process_content(self, doc):
		"""
			Put in template and generate dynamic if starts with #!python
		"""
		template = self.get_template(doc.template)
		content = ''
		
		# eval content
		if doc.content and doc.content.startswith('#!python'):
			from webnotes.model.code import execute
			content = template % {'content': execute(doc.content).get('content')}
		else:
			content = template % {'content': doc.content or ''}				

		doc.__content = content
			
	def load(self):	
		"""
			Returns :term:`doclist` of the `Page`
		"""
		from webnotes.modules import Module
		
		doclist = webnotes.model.doc.get('Page', self.name)
		doc = doclist[0]

		# load from module
		if doc.module: 
			module = Module(doc.module)
			self.get_from_files(doc, module)

		# process
		self.process_content(doc)

		# add stylesheet
		if doc.stylesheet:
			doclist += self.load_stylesheet(doc.stylesheet)
		
		return doclist

	def load_stylesheet(self, stylesheet):
		import webnotes
		# load stylesheet
		loaded = eval(webnotes.form_dict.get('stylesheets') or '[]')
		if not stylesheet in loaded:
			import webnotes.model.doc
			from webnotes.modules import Module
			
			# doclist
			sslist = webnotes.model.doc.get('Stylesheet', stylesheet)
			
			# stylesheet from file
			css = Module(sslist[0].module).get_doc_file('Stylesheet', stylesheet, '.css').read()
			
			if css: sslist[0].stylesheet = css			
			return sslist
		else:
			return []

@webnotes.whitelist()
def get(name):
	"""
	   Return the :term:`doclist` of the `Page` specified by `name`
	"""
	return Page(name).load()

@webnotes.whitelist(allow_guest=True)
def getpage():
	"""
	   Load the page from `webnotes.form` and send it via `webnotes.response`
	"""
	doclist = get(webnotes.form.getvalue('name'))
		
	# send
	webnotes.response['docs'] = doclist

def get_page_path(page_name, module):
	"""get path of the page html file"""
	import os
	import webnotes.defs
	from webnotes.modules import scrub
	return os.path.join(webnotes.defs.modules_path, 'erpnext', scrub(module), \
		'page', scrub(page_name), scrub(page_name) + '.html')
	
def get_page_html(page_name):
	"""get html of page, called from webnotes.cms.index"""
	p = webnotes.conn.sql("""select module, content from tabPage where name=%s""", \
		page_name, as_dict=1)

	if not p:
		return ''
	else:
		import os
		p=p[0]
		
		path = get_page_path(page_name, p['module'])
		if os.path.exists(path):
			with open(path, 'r') as f:
				return f.read()
		else:
			return p['content']
			
	
