import frappe

class MariaDBTable():
    def __init__(self, doctype, meta=None):
		self.doctype = doctype
		self.table_name = 'tab{}'.format(doctype)
		self.meta = meta or frappe.get_meta(doctype)

    def sync(self):
        pass

    def validate(self):
		"""Check if change in varchar length isn't truncating the columns"""
		if self.is_new():
			return

		self.get_columns_from_db()

		columns = [frappe._dict({"fieldname": f, "fieldtype": "Data"}) for f in frappe.db.STANDARD_VARCHAR_COLUMNS]
		columns += self.columns.values()

		for col in columns:
			if len(col.fieldname) >= 64:
				frappe.throw(_("Fieldname is limited to 64 characters ({0})")
					.format(frappe.bold(col.fieldname)))

			if col.fieldtype in frappe.db.type_map and frappe.db.type_map[col.fieldtype][0]=="varchar":

				# validate length range
				new_length = cint(col.length) or cint(frappe.db.VARCHAR_LEN)
				if not (1 <= new_length <= 1000):
					frappe.throw(_("Length of {0} should be between 1 and 1000").format(col.fieldname))

				current_col = self.current_columns.get(col.fieldname, {})
				if not current_col:
					continue
				current_type = self.current_columns[col.fieldname]["type"]
				current_length = re.findall('varchar\(([\d]+)\)', current_type)
				if not current_length:
					# case when the field is no longer a varchar
					continue
				current_length = current_length[0]
				if cint(current_length) != cint(new_length):
					try:
						# check for truncation
						max_length = frappe.db.sql("""select max(char_length(`{fieldname}`)) from `tab{doctype}`"""\
							.format(fieldname=col.fieldname, doctype=self.doctype))

					except frappe.db.InternalError as e:
						if frappe.db.is_missing_column(e):
							# Unknown column 'column_name' in 'field list'
							continue

						else:
							raise

					if max_length and max_length[0][0] and max_length[0][0] > new_length:
						if col.fieldname in self.columns:
							self.columns[col.fieldname].length = current_length

						frappe.msgprint(_("Reverting length to {0} for '{1}' in '{2}'; Setting the length as {3} will cause truncation of data.")\
							.format(current_length, col.fieldname, self.doctype, new_length))

    def is_new(self):
        return self.table_name not in frappe.db.get_tables()
