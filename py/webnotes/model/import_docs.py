# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import webnotes

def import_docs(docs = []):
	from webnotes.model.doc import Document
	import webnotes.model.code

	doc_list = {}
	created_docs = []
	already_exists = []

	out, tmp ="", ""

	for d in docs:
		cur_doc = Document(fielddata = d)
		if not cur_doc.parent in already_exists: # parent should not exist
			try:
				cur_doc.save(1)
				out += "Created: " + cur_doc.name + "\n"
				created_docs.append(cur_doc)

				# make in groups
				if cur_doc.parent:
					if not doc_list.has_key(cur_doc.parent):
						doc_list[cur_doc.parent] = []
					doc_list[cur_doc.parent].append(cur_doc)

			except Exception, e:
				out += "Creation Warning/Error: " + cur_doc.name + " :"+ str(e) + "\n"
				already_exists.append(cur_doc.name)

	# Run scripts for main docs
	for m in created_docs:
		if doc_list.has_key(m.name):
			tmp = webnotes.model.code.run_server_obj(webnotes.model.code.get_server_obj(m, doc_list.get(m.name, [])),'on_update')

			# update database (in case of DocType)
			if m.doctype=='DocType':
				import webnotes.model.doctype
				try: webnotes.model.doctype.update_doctype(doc_list.get(m.name, []))
				except: pass			
			out += 'Executed: '+ str(m.name) + ', Err:' + str(tmp) + "\n"

	return out

#======================================================================================================================================

import webnotes
import webnotes.utils
sql = webnotes.conn.sql
flt = webnotes.utils.flt
cint = webnotes.utils.cint
cstr = webnotes.utils.cstr

class CSVImport:
	def __init__(self):
		self.msg = []
		self.csv_data = None
		self.import_date_format = None
		self.deleted_records = []

	def validate_doctype(self, dt_list):
		cl, tables, self.dt_list, self.prompt_autoname_flag = 0, [t[0] for t in sql("show tables")], [], 0
		self.msg.append('<p><b>Identifying Documents</b></p>')
		dtd = sql("select name, istable, autoname from `tabDocType` where name = '%s' " % dt_list[0])
		if dtd and dtd[0][0]:
			self.msg.append('<div style="color: GREEN">Identified Document: ' + dt_list[0] + '</div>')
			self.dt_list.append(dt_list[0])
			if dtd[0][2] and 'Prompt' in dtd[0][2]: self.prompt_autoname_flag = 1
			if flt(dtd[0][1]):
				res1 = sql("select parent, fieldname from tabDocField where options='%s' and fieldtype='Table' and docstatus!=2" % self.dt_list[0])
				if res1 and res1[0][0] == dt_list[1]:
					self.msg.append('<div style="color: GREEN">Identified Document: ' + dt_list[1] + '</div>')
					self.dt_list.append(dt_list[1])
				else : 
					self.msg.append('<div style="color:RED"> Error: At Row 1, Column 2 => %s is not a valid Document </div>' % dt_list[1])
					self.validate_success = 0

				if res1 and res1[0][1] == dt_list[2]:
					self.msg.append('<div style="color: GREEN" >Identified Document Fieldname: ' + dt_list[2] + '</div>')
					self.dt_list.append(dt_list[2])
				else :
					self.msg.append('<div style="color:RED"> Error: At Row 1, Column 3 => %s is not a valid Fieldname </div>' % dt_list[2])
					self.validate_success = 0
			elif dt_list[1]:
				self.msg.append('<div style="color:RED"> Error: At Row 1, Column 1 => %s is not a Table.	</div>' % dt_list[0])
				self.validate_success = 0
		else:
			self.msg.append('<div style="color:RED"> Error: At Row 1, Column 1 => %s is not a valid Document </div>' % dt_list[0])
			self.validate_success = 0


	def validate_fields(self, lb_list):
		self.msg.append('<p><b>Checking fieldnames for %s</b></p>' % self.dt_list[0])
		
		if self.overwrite and len(self.dt_list) == 1 and 'Name' != lb_list[0]:
			self.msg.append('<div style="color:RED"> Error : At Row 4 and Column 1: To Overwrite fieldname should be Name </div>')
			self.validate_success = 0
			return

		# labelnames
		res = self.validate_success and [d[0] for d in sql("select label from tabDocField where parent='%s' and docstatus!=2 and ifnull(hidden,'') in ('',0)" % self.dt_list[0])] or []
		if len(self.dt_list) > 1 and self.dt_list[1]:
			if self.dt_list[1] not in lb_list:
				self.msg.append('<div style="color:RED"> Error : At Row 4: There should be one column named "'+self.dt_list[1]+'"</div>')
				self.validate_success = 0
				return

			if 'Name' in lb_list:
				self.msg.append('<div style="color:RED"> Error : At Row 4: "Name" column should not be there</div>')
				self.validate_success = 0
				return

			self.fields.append('parent')
			lb_list.pop(lb_list.index(self.dt_list[1]))

		dtd = sql("select autoname from `tabDocType` where name = '%s' " % self.dt_list[0])[0][0]
		if (self.prompt_autoname_flag or self.overwrite) and len(self.dt_list) == 1:
			self.fields.append('name')
			res.append('Name')
			lb_list.pop(lb_list.index('Name'))

		cl = 1
		for l in lb_list:
			try:
				if l:
					if not (l in res):
						self.msg.append('<div style="color: RED">Error : At Row 4 and Column %s Field %s is not present in %s</div>' % (cl, l, self.dt_list[0]))
						self.validate_success = 0
						# this condition is for child doctype
				
					else:	self.fields.append(sql("select fieldname from tabDocField where parent ='%s' and label = '%s' and ifnull(fieldname,'') !='' " % (self.dt_list[0], l))[0][0] or '')
			except Exception, e:
				self.msg.append('<div style="color: RED"> At Row 4 and Column %s : =>ERROR: %s </div>' % ( cl, e))
				self.validate_success = 0
			cl = cl + 1
	
		if not self.overwrite:
			# get_reqd_fields
			reqd_list = [d[0] for d in sql("select label from `tabDocField` where parent = '%s' and ifnull(reqd,'') not in ('', 0)  and docstatus !=2" % self.dt_list[0])	if d[0] not in lb_list] or []
		
			# Check if Reqd field not present in self.fields
			if reqd_list:
				self.msg.append('<div style="color: RED"> Error : At Row 4 Mandatory Fields %s of Document %s are Required. </div>' %(reqd_list , self.dt_list[0]))
				self.validate_success = 0
		if self.validate_success:
			self.msg.append('<div style="color: GREEN">Fields OK for %s</div>' % self.dt_list[0])
					
	def validate_headers(self):
		self.validate_doctype(self.doctype_data)
		if self.validate_success:
			self.validate_fields(self.labels)

	# Date parsing
	# --------------------------------------------------------------------
	def parse_date(self, r, c, d):
		out = ''
		try:
			if self.import_date_format=='yyyy-mm-dd':
				tmpd = d.split('-')
			
				if len(tmpd)==3:
					out = tmpd[0] + '-'+tmpd[1] + '-' + tmpd[2]
		
			elif d and self.import_date_format=='dd-mm-yyyy':
				tmpd = d.split('-')
					
				if len(tmpd)==3:
					out = tmpd[2]+'-'+tmpd[1]+'-'+tmpd[0]
			
			elif d and self.import_date_format=='mm/dd/yyyy':
				tmpd = d.split('/')
			
				if len(tmpd)==3:
					out = tmpd[2]+'-'+tmpd[0]+'-'+tmpd[1]
				
			elif d and self.import_date_format=='mm/dd/yy':
				tmpd = d.split('/')
			
				if len(tmpd)==3:
					out = '20'+tmpd[2]+'-'+tmpd[0]+'-'+tmpd[1]
		
			elif d and self.import_date_format=='dd/mm/yyyy':
				tmpd = d.split('/')
				if len(tmpd)==3:
					out = tmpd[2]+'-'+tmpd[1]+'-'+tmpd[0]

			elif d and self.import_date_format=='dd/mm/yy':
				tmpd = d.split('/')
				if len(tmpd)==3:
					out = '20'+tmpd[2]+'-'+tmpd[1]+'-'+tmpd[0]

			if len(tmpd) != 3:
				self.msg.append('<div style="color: RED"> At Row %s and Column %s : => Date Format selected as %s does not match with Date Format in File</div>' % (r, c, str(self.import_date_format)))
				self.validate_success = 0
			else:
			
				import datetime
				dt = out.split('-')
				datetime.date(int(dt[0]),int(dt[1]), int(dt[2]))
		except Exception, e:
			self.msg.append('<div style="color: RED"> At Row %s and Column %s : =>ERROR: %s </div>' % (r, c, e))
			self.validate_success = 0
		self.msg.append(out)
		return out

	def check_select_link_data(self, r, c, f, d, s = '', l = ''):
		from webnotes.model.doctype import get_field_property
		options = ''
		try:
			if d and f:
				dt = get_field_property(self.dt_list[0], f, 'options')
				lbl = get_field_property(self.dt_list[0], f, 'label')
				
				if dt:
					options = l and dt and [n[0] for n in sql("select name from `tab%s` " % (('link:' in dt and dt[5:]) or dt))] or s and dt.split('\n') or ''
					if options and d not in options :
						msg = '<div style="color: RED">At Row ' + str(r) + ' and Column ' + str(c)+ ' : => Data "' + str(d) + '" in field ['+ str(lbl) +'] Not Found in '
						msg = msg.__add__( s and  str( 'Select Options [' +str(dt.replace('\n', ',')) +']' ) or str('Master ' + str('link:' in dt and dt[5:] or dt)))
						msg = msg.__add__('</div>\n')
						self.msg.append(msg)

						self.validate_success = 0
		except Exception, e:
			self.msg.append('<div style="color: RED"> ERROR: %s </div>' % (str(webnotes.utils.getTraceback())))
			self.validate_success = 0
		return d


	def get_field_type_list(self):
		# get_date_fields
		date_list = [d[0] for d in sql("select fieldname from `tabDocField` where parent = '%s' and fieldtype='Date' and docstatus !=2" % self.dt_list[0])]

		# get_link_fields
		link_list = [d[0] for d in sql("select fieldname from `tabDocField` where parent = '%s' and ((fieldtype='Link' and ifnull(options,'') != '') or (fieldtype='Select' and ifnull(options,'') like '%%link:%%')) and docstatus !=2 " % self.dt_list[0])]

		# get_select_fileds
		select_list = [d[0] for d in sql("select fieldname from `tabDocField` where parent = '%s' and fieldtype='Select' and ifnull(options,'') not like '%%link:%%' and docstatus !=2" % self.dt_list[0])]
		
		# get_reqd_fields
		reqd_list = self.overwrite and ['name'] or [d[0] for d in sql("select fieldname from `tabDocField` where parent = '%s' and ifnull(reqd,'') not in ('', 0)  and docstatus !=2" % self.dt_list[0])]

		if len(self.dt_list)> 1 and 'parent' not in reqd_list: reqd_list.append('parent')

		if self.prompt_autoname_flag and 'name' not in reqd_list: reqd_list.append('name')
			 
		return date_list, link_list, select_list, reqd_list


	def validate_data(self):
		self.msg.append('<p><b>Checking Data for %s</b></p>' % self.dt_list[0])
		date_list, link_list, select_list, reqd_list = self.get_field_type_list()

		# load data
		row = 5
		for d in self.data:
	
			self.validate_success, fd, col = 1, {}, 1
			self.msg.append('<p><b>Checking Row %s </b></p>' % (row))
			for i in range(len(d)):
				if i < len(self.fields):
					f = self.fields[i]
					try:
						# Check Reqd Fields
						if (f in reqd_list) and not d[i]:
							self.msg.append('<div style="color: RED">Error: At Row %s and Column %s, Field %s is Mandatory.</div>' % (row, col, f))
							self.validate_success = 0
					
						# Check Date Fields
						if d[i] and f and f in date_list : fd[f] = self.parse_date(row, col, d[i])
	
						# Check Link Fields
						elif d[i] and f in link_list:
							fd[f] = self.check_select_link_data(row, col, f, d[i], l='Link')
						
						# Check Select Fields
						elif d[i] and f in select_list:
							fd[f] = self.check_select_link_data(row, col, f, d[i], s= 'Select')
												
						# Need To Perform Check For Other Data Type Too	
						else:	fd[f] = d[i]

					except Exception:
						self.msg.append('<div style="color: RED"> ERROR: %sData:%s and %s and %s and %s</div>' % (str(webnotes.utils.getTraceback()) + '\n', str(d), str(f), str(date_list), str(link_list)))
						self.validate_success = 0
				elif d[i]:
					self.validate_success = 0
					self.msg.append('<div style="color: RED">At Row %s and Column %s</div>' % (row,col))
					self.msg.append('<div style="color: ORANGE">Ignored</div>')
				col = col + 1 
			if self.validate_success:
				self.msg.append('<div style="color: GREEN">At Row %s and Column %s, Data Verification Completed </div>' % (row,col))
				self.update_data(fd,row)
			row = row + 1

	def update_data(self, fd, row):

		# load metadata
		from webnotes.model.doc import Document
		cur_doc = Document(fielddata = fd)
		cur_doc.doctype, cur_doc.parenttype, cur_doc.parentfield = self.dt_list[0], len(self.dt_list) > 1 and self.dt_list[1] or '', len(self.dt_list) > 1 and self.dt_list[2] or ''
		obj = ''
		webnotes.message_log = []
		# save the document
		try:
			# Delete data of child tables before over-writing
			if len(self.dt_list) > 1 and self.overwrite and cur_doc.parent and cur_doc.parent not in self.deleted_records:
				webnotes.conn.sql("delete from `tab%s` where parent = '%s'" % (self.dt_list[0], cur_doc.parent))
				self.deleted_records.append(cur_doc.parent)
				self.msg.append('<div style="color: ORANGE">Deleted %s data of %s : %s before re-importing</div>' % (self.dt_list[0], self.dt_list[1], cur_doc.parent))

			if webnotes.conn.in_transaction:
				sql("COMMIT")
			sql("START TRANSACTION")
			if cur_doc.name and webnotes.conn.exists(self.dt_list[0], cur_doc.name):
				if self.overwrite:
					cur_doc.save()
					obj = webnotes.model.code.get_obj(cur_doc.parent and cur_doc.parent_type or cur_doc.doctype, cur_doc.parent or cur_doc.name, with_children = 1)
					self.msg.append('<div style="color: ORANGE">Row %s => Over-written: %s</div>' % (row, cur_doc.name))
				else:
					self.msg.append('<div style="color: ORANGE">Row %s => Ignored: %s</div>' % (row, cur_doc.name))
			elif cur_doc.parent and webnotes.conn.exists(cur_doc.parenttype, cur_doc.parent) or not cur_doc.parent:
				cur_doc.save(1)
				obj = webnotes.model.code.get_obj(cur_doc.parent and cur_doc.parenttype or cur_doc.doctype, cur_doc.parent or cur_doc.name, with_children = 1)
				self.msg.append('<div style="color: GREEN">Row %s => Created: %s</div>' % (row, cur_doc.name))
			else: 
				self.msg.append('<div style="color: RED">Row %s => Invalid %s : %s</div>' % (row, cur_doc.parenttype, cur_doc.parent))
		except Exception:
			self.msg.append('<div style="color: RED"> Validation: %s</div>' % str(webnotes.utils.getTraceback()))
		try:
			if obj:
				if hasattr(obj, 'validate') : obj.validate()
				if hasattr(obj, 'on_update') : obj.on_update()
				if hasattr(obj, 'on_submit') : obj.on_submit()
			sql("COMMIT")

		except Exception:
			sql("ROLLBACK")
			self.msg.append('<div style="color: RED"> Validation Error: %s</div>' % str((webnotes.message_log and webnotes.message_log[0]) or webnotes.utils.getTraceback()))
			self.msg.append('<div style="color: RED"> Did not import</div>')
			
	# do import
	# --------------------------------------------------------------------
	def import_csv(self, csv_data, import_date_format = 'yyyy-mm-dd', overwrite = 0):
		import csv
		self.validate_success = 1
		self.csv_data = self.convert_csv_data_into_list(csv.reader(csv_data.splitlines()))
		self.import_date_format, self.overwrite = import_date_format, overwrite
		if len(self.csv_data) > 4:
			self.doctype_data, self.labels, self.data = self.csv_data[0][:4], self.csv_data[3], self.csv_data[4:]
			self.fields = []
		
			import webnotes.model.code
			from webnotes.model.doc import Document
			sql = webnotes.conn.sql
	        
			self.validate_headers()
			if self.validate_success:
				self.validate_data()
		else:
			self.msg.append('<p><b>No data entered in file.</b></p>')
		
		try:
			out_utf8 = '\n'.join([m.encode('utf-8') for m in self.msg])
		except UnicodeEncodeError, e:
			out_utf8 = """<div>We are unable to detect the encoding of the
					given .csv file. Please save the .csv file with UTF-8
					encoding. (See Data Import Guide -- Do you have Non-English data?)</div>"""

		return out_utf8

	def convert_csv_data_into_list(self,csv_data):
		st_list = []
		for s in csv_data:
			st_list.append([d.strip() for d in s])
		return st_list

# Get Template method
# -----------------------------------------------------------------

def get_template():
	import webnotes.model

	from webnotes.utils import getCSVelement
	
	sql = webnotes.conn.sql
	# get form values
	dt = webnotes.form_dict.get('dt')
	overwrite = cint(webnotes.form_dict.get('overwrite')) or 0

	pt, pf = '', ''
	tmp_lbl, tmp_ml = [],[]
	
	# is table?
	dtd = sql("select istable, autoname from tabDocType where name='%s'" % dt)
	if dtd and dtd[0][0]:
		res1 = sql("select parent, fieldname from tabDocField where options='%s' and fieldtype='Table' and docstatus!=2" % dt)
		if res1:
			pt, pf = res1[0][0], res1[0][1]

	# line 1
	dset = []
	if pt and pf:
		lbl, ml = [pt], ['[Mandatory]']
		line1 = '%s,%s,%s' % (getCSVelement(dt), getCSVelement(pt), getCSVelement(pf))
		line2 = ',,,,,,Please fill valid %(p)s No in %(p)s column.' % {'p':getCSVelement(pt)}
	else:
		if dtd[0][1]=='Prompt' or overwrite:
			lbl, ml= ['Name'], ['[Mandatory][Special Characters are not allowed]']
		else:
			lbl, ml= [], []
		line1 = '%s' % getCSVelement(dt)
		line2 = (overwrite and ',,,,,,Please fill valid %(d)s No in %(n)s' % {'d':dt,'n': 'Name'}) or ',,'

	# Help on Line 
	line1 = line1 + ',,,Please fill columns which are Mandatory., Please do not modify the structure'
	
	# standard fields
	res = sql("select fieldname, fieldtype, label, reqd, hidden from tabDocField where parent='%s' and docstatus!=2" % dt)

	for r in res:
		# restrict trash_reason field, hidden and required fields 
		if not r[1] in webnotes.model.no_value_fields and r[0] != 'trash_reason' and not r[4] and not r[3]:
			tmp_lbl.append(getCSVelement(r[2]))
			tmp_ml.append('')
		# restrict trash_reason field and hidden fields and add Mandatory indicator for required fields
		elif not r[1] in webnotes.model.no_value_fields and r[0] != 'trash_reason' and not r[4] and r[3]:
			lbl.append(getCSVelement(r[2]))
			ml.append(getCSVelement('[Mandatory]'))
	
	dset.append(line1)
	dset.append(line2)
	dset.append(','.join(ml + tmp_ml))
	dset.append(','.join(lbl + tmp_lbl))
	
	txt = '\n'.join(dset)
	webnotes.response['result'] = txt
	webnotes.response['type'] = 'csv'
	webnotes.response['doctype'] = dt

