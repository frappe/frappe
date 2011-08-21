# Please edit this list and import only required elements
import webnotes

from webnotes.utils import add_days, add_months, add_years, cint, cstr, date_diff, default_fields, flt, fmt_money, formatdate, generate_hash, getTraceback, get_defaults, get_first_day, get_last_day, getdate, has_common, month_name, now, nowdate, replace_newlines, sendmail, set_default, str_esc_quote, user_format, validate_email_add
from webnotes.model import db_exists
from webnotes.model.doc import Document, addchild, removechild, getchildren, make_autoname, SuperDocType
from webnotes.model.doclist import getlist, copy_doclist
from webnotes.model.code import get_obj, get_server_obj, run_server_obj, updatedb, check_syntax
from webnotes import session, form, is_testing, msgprint, errprint

set = webnotes.conn.set
sql = webnotes.conn.sql
get_value = webnotes.conn.get_value
in_transaction = webnotes.conn.in_transaction
convert_to_lists = webnotes.conn.convert_to_lists
	
# -----------------------------------------------------------------------------------------


class DocType:
	def __init__(self,d,dl):
		self.doc, self.doclist = d,dl
		
	def generate_children(self):
		if not getlist(self.doclist,'items') and not self.doc.widget_code:
			obj = Document(self.doc.doctype, self.doc.name)
			
			doc_type = [['DocType','name','name','Forms',"(istable is null or istable=0) and (issingle is null or issingle=0)"],['Page','name','page_name','Pages','(show_in_menu=1 or show_in_menu=0)'],['Search Criteria','doc_type','criteria_name','Reports',"(disabled is null or disabled=0)"]]
			for dt in doc_type:
				dn = [[d[0] or '', d[1] or ''] for d in sql("select %s,%s from `tab%s` where module = '%s' and %s" % (dt[1],dt[2],dt[0],self.doc.name,dt[4]))]

				if dn:
					r = addchild(obj,'items','Module Def Item',1)
					r.doc_type = 'Separator'
					r.doc_name = dt[3]
					r.save(1)

					for d in dn:
						r = addchild(obj,'items','Module Def Item',1)
						r.doc_type = dt[3]
						r.doc_name = d[0]
						r.display_name = d[1]
						r.save(1)

	def on_update(self, from_update=0):
		from webnotes import defs
		from webnotes.utils.transfer import in_transfer
		
		if (not in_transfer) and getattr(defs,'developer_mode', 0):
			from webnotes.modules.export_module import export_to_files
			export_to_files(record_list=[[self.doc.doctype, self.doc.name]])
			