import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d,dl
	
	def on_update(self):
		"""
			On update, create/update a DocFormat record corresponding to DocType and Print Format Name
		"""
		if self.doc.doc_type:
			from webnotes.model.doc import Document
			res = webnotes.conn.sql("""
				SELECT * FROM `tabDocFormat`
				WHERE format=%s""", self.doc.name)
			if res and res[0]:
				d = Document('DocFormat', res[0][0])
				d.parent = self.doc.doc_type
				d.parenttype = 'DocType'
				d.parentfield = 'formats'
				d.format = self.doc.name
				d.save()
			else:
				max_idx = webnotes.conn.sql("""
					SELECT MAX(idx) FROM `tabDocFormat`
					WHERE parent=%s
					AND parenttype='DocType'
					AND parentfield='formats'""", self.doc.doc_type)[0][0]
				d = Document('DocFormat')
				d.parent = self.doc.doc_type
				d.parenttype = 'DocType'
				d.parentfield = 'formats'
				d.format = self.doc.name
				d.idx = max_idx + 1
				d.save(1)
