"""
	Classes for naming of records
	To name a model, use::
		
		NamingControl(model, meta).set_name()
	
"""
import webnotes

class NamingControl:
	"""
	Creates an autoname from the given key:
	"""

	def __init__(self, collection):
		self.collection = collection
	
	def set_name(self):
		"""
			Get the name based on logic
			1. by method
			2. by field
			3. by eval
			4. by numbering
		"""
		self.model = self.collection.parent
		autoname = self.collection.parent._def.parent.autoname
		
		self.model.localname = self.model.name
		
		# clear localname
		if self.model.name and self.model.name.startswith('New '):
			self.model.name = None

		if self.model.amended_from: 
			return self.by_amendment()

		if hasattr(self.collection, 'autoname'):
			return self.by_method()
			
		if autoname and autoname.startswith('field:'):
			return self.by_field()
		
		if autoname and autoname.startswith('eval:'):
			return self.by_eval()
		
		if autoname and autoname!='Prompt': 
			self.model.name = self.process_from_key(autoname)
			return
				
		if self.model.__dict__.get('__newname',''): 
			self.model.name = self.__dict__['__newname']
			return

		# unable to determine a name, use a serial number!
		if not self.model.name:
			self.model.name = self.process_from_key('#########')
	
	def by_method(self):
		"name by function"
		r = self.collection.autoname()
		if r:
			self.model.name = r
	
	def by_field(self):
		"name based on a field"
		n = self.model.__dict__[self.meta.autoname[6:]]
		if not n:
			raise Exception, 'Name is required'
		self.model.name = n.strip()
	
	def by_eval(self):
		"name based on eval"
		model = doc = self.model # for setting
		self.name = eval(self.meta.autoname[5:])		

	def by_amendment(self):
		"get name based on amendment name"
		am_id = 1
		
		am_prefix = self.model.amended_from
		
		# more than one
		if webnotes.conn.sql('select amended_from from `tab%s` where name = "%s"' \
			% (self.model.doctype, self.model.amended_from))[0][0] or '':
			am_id = cint(self.model.amended_from.split('-')[-1]) + 1
			am_prefix = '-'.join(self.model.amended_from.split('-')[:-1]) # except the last hyphen
			
		self.model.name = am_prefix + '-' + str(am_id)
	
	def process_from_key(self, exp):
		"""
			return processed name from `autname` property

			**Autoname rules:**

					* The key is separated by '.'
					* '####' represents a series. The string before this part becomes the prefix:
						Example: ABC.#### creates a series ABC0001, ABC0002 etc
					* 'MM' represents the current month
					* 'YY' and 'YYYY' represent the current year


			*Example:*

					* DE/./.YY./.MM./.##### will create a series like
					  DE/09/01/0001 where 09 is the year, 01 is the month and 0001 is the series
		"""
		n = ''
		l = exp.split('.')
		for e in l:
			en = ''
			if e.startswith('#'):
				digits = len(e)
				en = NumberingSeries(n, digits).next()
			elif e=='YY': 
				import time
				en = time.strftime('%y')
			elif e=='MM': 
				import time
				en = time.strftime('%m')		
			elif e=='YYYY': 
				import time
				en = time.strftime('%Y')		
			else: en = e
			n+=en
		return n



class NumberingSeries:
	"""
		manages multiple series
	"""
	def __init__(self, prefix, digits=6):
		self.prefix = prefix
		self.digits = digits
	
	def next(self):
		"""
			return next value
		"""
		# series created ?
		if webnotes.conn.sql("select name from tabSeries where name='%s'" % self.prefix):

			# yes, update it
			webnotes.conn.sql("update tabSeries set current = current+1 where name='%s'" % self.prefix)

			# find the series counter
			r = webnotes.conn.sql("select current from tabSeries where name='%s'" % self.prefix)
			n = r[0][0]
		else:
			# no, create it
			webnotes.conn.sql("insert into tabSeries (name, current) values ('%s', 1)" % self.prefix)
			n = 1
		return ('%0'+str(self.digits)+'d') % n