import webnotes

def upload(arg=None):
	"""
		Upload, do first checks and save attachment as "import_attach.csv"
	"""
	from webnotes.utils.upload_handler import UploadHandler
	uh = UploadHandler()
	
	if uh.file_name:
		# parse
		csv = ImportCSV(uh.content)

		# save	
		from webnotes.utils.file_manager import save_file
		save_file("__importattach.csv", uh.content)
		
		# send first row to callback
		import json
		uh.set_callback("window.parent.pscript.upload_done(%s)" % json.dumps(csv.data[0]))


class ImportCSV:
	def __init__(self, content, doctype=None, mapper={}):
		import csv
		self.data = []
		
		self.mapper = mapper
		self.doctype = doctype
		
		raw = csv.reader(content.splitlines())
		for r in raw:
			self.data.append([c for c in r])
			
		if self.mapper:
			self.convert_labels_to_columns()
		
	def get_columns(self):
		"""
			Returns the columns in the table
		"""
		return self.data[0]
	
	def convert_labels_to_columns(self):
		"""
			Convert label names to column names in mapper
		"""
		n = []
		for c in self.mapper:
			cn = webnotes.conn.sql("select fieldname from tabDocField where label=%s and parent=%s", \
				(c, self.doctype))[0][0]
			n.append(cn)
			
		self.mapper = n
	
	def imp(self):
		"""
			Import the records into table
			Uses webnotes.model.doclist
		"""
		from webnotes.model.doclist import DocList
		for d in self.data[1:]:
			tmp = {}
			for i in range(len(self.mapper)):
				# make dict of Label: data
				tmp[self.mapper[i]] = d[i]
				
				if tmp.get('name'):
					# overwrite
					existing = webnotes.conn.sql("select * from `tab%s` where name=%s" %
						(self.doctype, '%s'), tmp['name'], as_dict=1)[0]
					existing.update(tmp)
					tmp = existing
				else:				
					# new
					tmp['owner'] = webnotes.session['user']
					tmp['__islocal'] = 1 # not saved yet

				tmp['doctype'] = self.doctype
				
				doclist = DocList(docs=[tmp])
				doclist.save()
				
				