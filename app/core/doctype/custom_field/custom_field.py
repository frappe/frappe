# Please edit this list and import only required elements
import webnotes

from webnotes.utils import cint, cstr, flt, formatdate, now
from webnotes.model.doc import Document
from webnotes import msgprint, errprint

sql = webnotes.conn.sql
	
# -----------------------------------------------------------------------------------------


class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

	# Get Fields
	# -----------
	def get_fields_label(self):
		label_name = []
		for i in sql("SELECT idx, label FROM tabDocField WHERE parent = '%s' and ifnull(hidden,0) = 0 and fieldname != '%s' order by idx" % (self.doc.dt, cstr(self.doc.fieldname))):	i[1] and i[0] and label_name.append(i[1]+' - '+cstr(i[0]))
		return "\n".join(label_name)


# *************************** Validate *******************************
	# Set Field name
	# ----------------
	def set_fieldname(self):
		if not self.doc.fieldname:
			# remove special characters from fieldname
			self.doc.fieldname = filter(lambda x: x.isdigit() or x.isalpha() or '_', cstr(self.doc.label).lower().replace(' ','_'))


	# Validate Field
	# ---------------
	def validate_field(self):
		if self.doc.__islocal == 1 and sql("select name from tabDocField where parent = %s and (label = %s or fieldname = %s)" , (self.doc.dt, self.doc.label, self.doc.fieldname)):
			msgprint("%s field already exists in Document : %s" % (self.doc.label, self.doc.dt))
			raise Exception

		if self.doc.fieldtype=='Link' and self.doc.options:
			if not sql("select name from tabDocType where name=%s", self.doc.options):
				msgprint("%s is not a valid Document" % self.doc.options)
				raise Exception


	# Update Field
	# -------------
	def update_field(self, df, new):
		import webnotes.model
		sql("update tabDocField set idx = idx + 1, modified = %s where parent = %s and idx > %s", (now(),self.doc.dt, self.idx))
		for k in self.doc.fields:
			if k not in webnotes.model.default_fields and k not in self.ignore_fields and not k.startswith('_'):
				df.fields[k] = self.doc.fields[k]
		df.parent = self.doc.dt
		df.parenttype = 'DocType'
		df.parentfield = 'fields'
		df.idx = self.idx+1
		df.save(new)


	# Add Field
	# ----------
	def add_field(self):
		field_exists = sql("select name from tabDocField where parent = %s and (label = %s or fieldname = %s)" , (self.doc.dt, self.doc.label, self.doc.fieldname))
		field_exists = field_exists and field_exists[0][0] or ''
		self.ignore_fields = ['dt','trash_reason','insert_after','index','customfield1','length']
		if field_exists:
			df = Document('DocField',field_exists)
			self.update_field(df, new = 0)
		else:
			df = Document('DocField')
			self.update_field(df, new = 1)
	

	# Validate
	# ---------
	def validate(self):
		self.set_fieldname()
		self.validate_field()
		self.idx = cint((self.doc.insert_after).split(' - ')[1])
		self.add_field()
		
		# update the schema
		from webnotes.db.utils import updatedb
		updatedb(self.doc.dt)

	# Trash
	# ------
	def on_trash(self):
		sql("update tabDocField set idx = idx - 1 where parent = %s and idx > %s" , (self.doc.dt, cint((self.doc.insert_after).split(' - ')[1])))
		sql("delete from tabDocField where parent = %s and fieldname = %s", (self.doc.dt, self.doc.fieldname))


	# Restore
	# --------
	def on_restore(self):
		self.validate_field()
		self.idx = cint((self.doc.insert_after).split(' - ')[1])
		self.add_field()
