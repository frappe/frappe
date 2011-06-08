import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
	
	def get_property_list(self, dt):
		return webnotes.conn.sql("""select fieldname, label, fieldtype 
		from tabDocField
		where parent=%s
		and fieldtype not in ('Section Break', 'Column Break', 'HTML', 'Read Only', 'Table') 
		and ifnull(fieldname, '') != ''
		order by label asc""", dt, as_dict=1)
		
	def get_setup_data(self):
		return {
			'doctypes': [d[0] for d in webnotes.conn.sql("select name from tabDocType")],
			'dt_properties': self.get_property_list('DocType'),
			'df_properties': self.get_property_list('DocField')
		}
		
	def get_field_ids(self):
		return webnotes.conn.sql("select name, fieldtype, label, fieldname from tabDocField where parent=%s", self.doc.doc_type, as_dict = 1)
	
	def get_defaults(self):
		if self.doc.doc_type == self.doc.doc_name:
			return webnotes.conn.sql("select * from `tabDocType` where name=%s", self.doc.doc_name, as_dict = 1)[0]
		else:
			return webnotes.conn.sql("select * from `tabDocField` where name=%s", self.doc.doc_name, as_dict = 1)[0]