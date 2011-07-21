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

	def get_from_files(self, doc):
		"""
			Loads page info from files in module
		"""
		from webnotes.modules import compress
		from webnotes.model.code import get_code

		# load js
		doc.fields['__script'] = compress.get_page_js(doc)
		doc.script = None

		# load css
		css = get_code(doc.module, 'page', doc.name, 'css')
		if css: doc.style = css
		
		# html
		doc.content = get_code(doc.module, 'page', doc.name, 'html') or doc.content
		
	def load(self):	
		"""
			Returns :term:`doclist` of the `Page`
		"""
		from webnotes.model.code import get_code
		
		doclist = webnotes.model.doc.get('Page', self.name)
		doc = doclist[0]

		if doc.module: self.get_from_files(doc)

		template = '%(content)s'
		# load code from template
		if doc.template:
			template = get_code(webnotes.conn.get_value('Page Template', doc.template, 'module'), 'Page Template', doc.template, 'html', fieldname='template')
				
		# execute content
		if doc.content and doc.content.startswith('#!python'):
			doc.__content = template % {'content': webnotes.model.code.execute(doc.content).get('content')}
		else:
			doc.__content = template % {'content': doc.content or ''}

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
			from webnotes.model.code import get_code
			
			# doclist
			sslist = webnotes.model.doc.get('Stylesheet', stylesheet)
			
			# stylesheet from file
			css = get_code(sslist[0].module, 'Stylesheet', stylesheet, 'css')
			
			if css: sslist[0].stylesheet = css
			
			return sslist
		else:
			return []

def get(name):
	"""
	   Return the :term:`doclist` of the `Page` specified by `name`
	"""
	return Page(name).load()

def getpage():
	"""
	   Load the page from `webnotes.form` and send it via `webnotes.response`
	"""
	doclist = get(webnotes.form.getvalue('name'))
		
	# send
	webnotes.response['docs'] = doclist
	
