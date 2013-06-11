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
"""
Contains the Document class representing an object / record
"""

_toc = ["webnotes.model.doc.Document"]

import webnotes
import webnotes.model.meta

from webnotes.utils import *

valid_fields_map = {}

class Document:
	"""
	   The wn(meta-data)framework equivalent of a Database Record.
	   Stores,Retrieves,Updates the record in the corresponding table.
	   Runs the triggers required.

	   The `Document` class represents the basic Object-Relational Mapper (ORM). The object type is defined by
	   `DocType` and the object ID is represented by `name`:: 
	   
	      Please note the anamoly in the Web Notes Framework that `ID` is always called as `name`

	   If both `doctype` and `name` are specified in the constructor, then the object is loaded from the database.
	   If only `doctype` is given, then the object is not loaded
	   If `fielddata` is specfied, then the object is created from the given dictionary.
	       
	      **Note 1:**
	      
		 The getter and setter of the object are overloaded to map to the fields of the object that
		 are loaded when it is instantiated.
	       
		 For example: doc.name will be the `name` field and doc.owner will be the `owner` field

	      **Note 2 - Standard Fields:**
	      
		 * `name`: ID / primary key
		 * `owner`: creator of the record
		 * `creation`: datetime of creation
		 * `modified`: datetime of last modification
		 * `modified_by` : last updating user
		 * `docstatus` : Status 0 - Saved, 1 - Submitted, 2- Cancelled
		 * `parent` : if child (table) record, this represents the parent record
		 * `parenttype` : type of parent record (if any)
		 * `parentfield` : table fieldname of parent record (if any)
		 * `idx` : Index (sequence) of the child record	
	"""
	
	def __init__(self, doctype = None, name = None, fielddata = None, prefix='tab'):
		self._roles = []
		self._perms = []
		self._user_defaults = {}
		self._prefix = prefix
		
		if isinstance(doctype, dict):
			fielddata = doctype
			doctype = None
		
		if fielddata: 
			self.fields = webnotes._dict(fielddata)
		else: 
			self.fields = webnotes._dict()
		
		if not self.fields.has_key('name'):
			self.fields['name']='' # required on save
		if not self.fields.has_key('doctype'):
			self.fields['doctype']='' # required on save
		if not self.fields.has_key('owner'):
			self.fields['owner']='' # required on save

		if doctype:
			self.fields['doctype'] = doctype
		if name:
			self.fields['name'] = name
		self.__initialized = 1

		if (doctype and name):
			self._loadfromdb(doctype, name)
		else:
			if not fielddata:
				self.fields['__islocal'] = 1
		
		if not self.fields.docstatus:
			self.fields.docstatus = 0

	def __nonzero__(self):
		return True

	def __str__(self):
		return str(self.fields)
		
	def __repr__(self):
		return repr(self.fields)
		
	def __unicode__(self):
		return unicode(self.fields)
		
	def __eq__(self, other):
		if isinstance(other, Document):
			return self.fields == other.fields
		else:
			return False

	def __getstate__(self): 
		return self.fields
		
	def __setstate__(self, d): 
		self.fields = d

	def encode(self, encoding='utf-8'):
		"""convert all unicode values to utf-8"""
		for key in self.fields:
			if isinstance(self.fields[key], unicode):
				self.fields[key] = self.fields[key].encode(encoding)

	def _loadfromdb(self, doctype = None, name = None):
		if name: self.name = name
		if doctype: self.doctype = doctype
		
		is_single = False
		try: 
			is_single = webnotes.model.meta.is_single(self.doctype)
		except Exception, e:
			pass
		
		if is_single:
			self._loadsingle()
		else:
			dataset = webnotes.conn.sql('select * from `%s%s` where name="%s"' % (self._prefix, self.doctype, self.name.replace('"', '\"')))
			if not dataset:
				raise Exception, '[WNF] %s %s does not exist' % (self.doctype, self.name)
			self._load_values(dataset[0], webnotes.conn.get_description())

	def _load_values(self, data, description):
		if '__islocal' in self.fields:
			del self.fields['__islocal']
		for i in range(len(description)):
			v = data[i]
			self.fields[description[i][0]] = webnotes.conn.convert_to_simple_type(v)

	def _merge_values(self, data, description):
		for i in range(len(description)):
			v = data[i]
			if v: # only if value, over-write
				self.fields[description[i][0]] = webnotes.conn.convert_to_simple_type(v)
			
	def _loadsingle(self):
		self.name = self.doctype
		self.fields.update(getsingle(self.doctype))

	def __setattr__(self, name, value):
		# normal attribute
		if not self.__dict__.has_key('_Document__initialized'): 
			self.__dict__[name] = value
		elif self.__dict__.has_key(name):
			self.__dict__[name] = value
		else:
			# field attribute
			f = self.__dict__['fields']
			f[name] = value

	def __getattr__(self, name):
		if self.__dict__.has_key(name):
			return self.__dict__[name]
		elif self.fields.has_key(name):
			return self.fields[name]	
		else:
			return ''
	
	def _get_amended_name(self):
		am_id = 1
		am_prefix = self.amended_from
		if webnotes.conn.sql('select amended_from from `tab%s` where name = "%s"' % (self.doctype, self.amended_from))[0][0] or '':
			am_id = cint(self.amended_from.split('-')[-1]) + 1
			am_prefix = '-'.join(self.amended_from.split('-')[:-1]) # except the last hyphen
			
		self.name = am_prefix + '-' + str(am_id)

	def _set_name(self, autoname, istable):
		self.localname = self.name

		# get my object
		import webnotes.model.code
		so = webnotes.model.code.get_server_obj(self, [])

		# amendments
		if self.amended_from: 
			self._get_amended_name()
		# by method
		elif so and hasattr(so, 'autoname'):
			r = webnotes.model.code.run_server_obj(so, 'autoname')
			if r: return r
			
		# based on a field
		elif autoname and autoname.startswith('field:'):
			n = self.fields[autoname[6:]]
			if not n:
				raise Exception, 'Name is required'
			self.name = n.strip()
			
		elif autoname and autoname.startswith("naming_series:"):
			if not self.naming_series:
				# pick default naming series
				from webnotes.model.doctype import get_property
				self.naming_series = get_property(self.doctype, "options", "naming_series")
				if not self.naming_series:
					webnotes.msgprint(webnotes._("Naming Series mandatory"), raise_exception=True)
				self.naming_series = self.naming_series.split("\n")
				self.naming_series = self.naming_series[0] or self.naming_series[1]
			self.name = make_autoname(self.naming_series+'.#####')
			
		# based on expression
		elif autoname and autoname.startswith('eval:'):
			doc = self # for setting
			self.name = eval(autoname[5:])
		
		# call the method!
		elif autoname and autoname!='Prompt': 
			self.name = make_autoname(autoname, self.doctype)
				
		# given
		elif self.fields.get('__newname',''): 
			self.name = self.fields['__newname']

		# default name for table
		elif istable: 
			self.name = make_autoname('#########', self.doctype)
			
		# unable to determine a name, use a serial number!
		if not self.name:
			self.name = make_autoname('#########', self.doctype)
			
	def _insert(self, autoname, istable, case='', make_autoname=1, keep_timestamps=False):
		# set name
		if make_autoname:
			self._set_name(autoname, istable)
		
		# validate name
		self.name = validate_name(self.doctype, self.name, case)
				
		# insert!
		if not keep_timestamps:
			if not self.owner: 
				self.owner = webnotes.session['user']
			self.modified_by = webnotes.session['user']
			if not self.creation:
				self.creation = self.modified = now()
			else:
				self.modified = now()
			
		webnotes.conn.sql("insert into `tab%(doctype)s`" % self.fields \
			+ """ (name, owner, creation, modified, modified_by)
			values (%(name)s, %(owner)s, %(creation)s, %(modified)s,
				%(modified_by)s)""", self.fields)

	def _update_single(self, link_list):
		update_str = ["(%s, 'modified', %s)",]
		values = [self.doctype, now()]
		
		webnotes.conn.sql("delete from tabSingles where doctype='%s'" % self.doctype)
		for f in self.fields.keys():
			if not (f in ('modified', 'doctype', 'name', 'perm', 'localname', 'creation'))\
				and (not f.startswith('__')): # fields not saved

				# validate links
				if link_list and link_list.get(f):
					self.fields[f] = self._validate_link(link_list[f][0], self.fields[f])

				if self.fields[f]==None:
					update_str.append("(%s,%s,NULL)")
					values.append(self.doctype)
					values.append(f)
				else:
					update_str.append("(%s,%s,%s)")
					values.append(self.doctype)
					values.append(f)
					values.append(self.fields[f])
		webnotes.conn.sql("insert into tabSingles(doctype, field, value) values %s" % (', '.join(update_str)), values)

	def validate_links(self, link_list):
		err_list = []
		for f in self.fields.keys():
			# validate links
			old_val = self.fields[f]
			if link_list and link_list.get(f):
				self.fields[f] = self._validate_link(link_list[f][0], self.fields[f])

			if old_val and not self.fields[f]:
				s = link_list[f][1] + ': ' + old_val
				err_list.append(s)
				
		return err_list

	def make_link_list(self):
		res = webnotes.model.meta.get_link_fields(self.doctype)

		link_list = {}
		for i in res: link_list[i[0]] = (i[1], i[2]) # options, label
		return link_list
	
	def _validate_link(self, dt, dn):
		if not dt: return dn
		if not dn: return None
		if dt=="[Select]": return dn
		if dt.lower().startswith('link:'):
			dt = dt[5:]
		if '\n' in dt:
			dt = dt.split('\n')[0]
		tmp = webnotes.conn.sql("""SELECT name FROM `tab%s` 
			WHERE name = %s""" % (dt, '%s'), dn)
		return tmp and tmp[0][0] or ''# match case
	
	def _update_values(self, issingle, link_list, ignore_fields=0, keep_timestamps=False):
		if issingle:
			self._update_single(link_list)
		else:
			update_str, values = [], []
			# set modified timestamp
			if self.modified and not keep_timestamps:
				self.modified = now()
				self.modified_by = webnotes.session['user']
			
			fields_list = ignore_fields and self.get_valid_fields() or self.fields.keys()
			
			for f in fields_list:
				if (not (f in ('doctype', 'name', 'perm', 'localname',
						'creation','_user_tags', "file_list"))) and (not f.startswith('__')): 
						# fields not saved
					
					# validate links
					if link_list and link_list.get(f):
						self.fields[f] = self._validate_link(link_list[f][0],
							self.fields.get(f))

					if self.fields.get(f) is None or self.fields.get(f)=='':
						update_str.append("`%s`=NULL" % f)
					else:
						values.append(self.fields.get(f))
						update_str.append("`%s`=%s" % (f, '%s'))
			if values:
				values.append(self.name)
				r = webnotes.conn.sql("update `tab%s` set %s where name=%s" % \
					(self.doctype, ', '.join(update_str), "%s"), values)
					
	def get_valid_fields(self):
		global valid_fields_map
		if not valid_fields_map.get(self.doctype):
			import webnotes.model.doctype
			if cint(webnotes.conn.get_value("DocType", self.doctype, "issingle")):
				doctypelist = webnotes.model.doctype.get(self.doctype)
				valid_fields_map[self.doctype] = doctypelist.get_fieldnames({
					"fieldtype": ["not in", webnotes.model.no_value_fields]})
			else:
				valid_fields_map[self.doctype] = \
					webnotes.conn.get_table_columns(self.doctype)
			
		return valid_fields_map.get(self.doctype)
		
	def save(self, new=0, check_links=1, ignore_fields=0, make_autoname=1,
			keep_timestamps=False):
		res = webnotes.model.meta.get_dt_values(self.doctype,
			'autoname, issingle, istable, name_case', as_dict=1)
		res = res and res[0] or {}
		
		if new:
			self.fields["__islocal"] = 1

		# add missing parentinfo (if reqd)
		if self.parent and not (self.parenttype and self.parentfield):
			self.update_parentinfo()
			
		if self.parent and not self.idx:
			self.set_idx()

		# if required, make new
		if self.fields.get('__islocal') and (not res.get('issingle')):
			r = self._insert(res.get('autoname'), res.get('istable'), res.get('name_case'),
				make_autoname, keep_timestamps = keep_timestamps)
			if r: 
				return r

		else:
			if not res.get('issingle') and not webnotes.conn.exists(self.doctype, self.name):
				webnotes.msgprint("""This document was updated before your change. Please refresh before saving.""", raise_exception=1)
				
		# save the values
		self._update_values(res.get('issingle'), 
			check_links and self.make_link_list() or {}, ignore_fields=ignore_fields,
			keep_timestamps=keep_timestamps)
		self._clear_temp_fields()

	def insert(self):
		self.fields['__islocal'] = 1
		self.save()
		return self
		
	def update_parentinfo(self):
		"""update parent type and parent field, if not explicitly specified"""

		tmp = webnotes.conn.sql("""select parent, fieldname from tabDocField 
			where fieldtype='Table' and options=%s""", self.doctype)
			
		if len(tmp)==0:
			raise Exception, 'Incomplete parent info in child table (%s, %s)' \
				% (self.doctype, self.fields.get('name', '[new]'))
		
		elif len(tmp)>1:
			raise Exception, 'Ambiguous parent info (%s, %s)' \
				% (self.doctype, self.fields.get('name', '[new]'))

		else:
			self.parenttype = tmp[0][0]
			self.parentfield = tmp[0][1]

	def set_idx(self):
		"""set idx"""
		self.idx = (webnotes.conn.sql("""select max(idx) from `tab%s` 
			where parent=%s and parentfield=%s""" % (self.doctype, '%s', '%s'), 
			(self.parent, self.parentfield))[0][0] or 0) + 1
		
	def _clear_temp_fields(self):
		# clear temp stuff
		keys = self.fields.keys()
		for f in keys:
			if f.startswith('__'): 
				del self.fields[f]

	def clear_table(self, doclist, tablefield, save=0):
		"""
		Clears the child records from the given `doclist` for a particular `tablefield`
		"""
		from webnotes.model.utils import getlist
		
		table_list = getlist(doclist, tablefield)
				
		delete_list = [d.name for d in table_list]
		
		if delete_list:
			#filter doclist
			doclist = filter(lambda d: d.name not in delete_list, doclist)
		
			# delete from db
			webnotes.conn.sql("""\
				delete from `tab%s`
				where parent=%s and parenttype=%s"""
				% (table_list[0].doctype, '%s', '%s'),
				(self.name, self.doctype))

			self.fields['__unsaved'] = 1
		
		return webnotes.doclist(doclist)

	def addchild(self, fieldname, childtype = '', doclist=None):
		"""
	      Returns a child record of the give `childtype`.
	      
	      * if local is set, it does not save the record
	      * if doclist is passed, it append the record to the doclist
		"""
		from webnotes.model.doc import Document
		d = Document()
		d.parent = self.name
		d.parenttype = self.doctype
		d.parentfield = fieldname
		d.doctype = childtype
		d.docstatus = 0;
		d.name = ''
		d.owner = webnotes.session['user']
		d.fields['__islocal'] = 1 # for Client to identify unsaved doc
		
		if doclist != None:
			doclist.append(d)
			
		if doclist:
			d.idx = max([(d.idx or 0) for d in doclist if d.doctype==childtype]) + 1
	
		return d
		
	def get_values(self):
		"""get non-null fields dict withouth standard fields"""
		from webnotes.model import default_fields
		ret = {}
		for key in self.fields:
			if key not in default_fields and self.fields[key]:
				ret[key] = self.fields[key]
				
		return ret
			
def addchild(parent, fieldname, childtype = '', doclist=None):
	"""
	
   Create a child record to the parent doc.
   
   Example::
   
     c = Document('Contact','ABC')
     d = addchild(c, 'contact_updates', 'Contact Update')
     d.last_updated = 'Phone call'
     d.save(1)
	"""
	return parent.addchild(fieldname, childtype, doclist)
			
def make_autoname(key, doctype=''):
	"""
   Creates an autoname from the given key:
   
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
	l = key.split('.')
	series_set = False
	today = now_datetime()
	
	for e in l:
		en = ''
		if e.startswith('#'):
			if not series_set:
				digits = len(e)
				en = getseries(n, digits, doctype)
				series_set = True
		elif e=='YY': 
			en = today.strftime('%y')
		elif e=='MM': 
			en = today.strftime('%m')
		elif e=='DD':
			en = today.strftime("%d")
		elif e=='YYYY': 
			en = today.strftime('%Y')		
		else: en = e
		n+=en
	return n

def getseries(key, digits, doctype=''):
	# series created ?
	if webnotes.conn.sql("select name from tabSeries where name='%s'" % key):

		# yes, update it
		webnotes.conn.sql("update tabSeries set current = current+1 where name='%s'" % key)

		# find the series counter
		r = webnotes.conn.sql("select current from tabSeries where name='%s'" % key)
		n = r[0][0]
	else:
	
		# no, create it
		webnotes.conn.sql("insert into tabSeries (name, current) values ('%s', 1)" % key)
		n = 1
	return ('%0'+str(digits)+'d') % n

def getchildren(name, childtype, field='', parenttype='', from_doctype=0, prefix='tab'):
	import webnotes
	from webnotes.model.doclist import DocList
	
	condition = ""
	values = []
	
	if field: 
		condition += ' and parentfield=%s '
		values.append(field)
	if parenttype:
		condition += ' and parenttype=%s '
		values.append(parenttype)

	dataset = webnotes.conn.sql("""select * from `%s%s` where parent=%s %s order by idx""" \
		% (prefix, childtype, "%s", condition), tuple([name]+values))
	desc = webnotes.conn.get_description()

	l = DocList()
	
	for i in dataset:
		d = Document()
		d.doctype = childtype
		d._load_values(i, desc)
		l.append(d)
	
	return l

def check_page_perm(doc):
	if doc.name=='Login Page':
		return
	if doc.publish:
		return

	if not webnotes.conn.sql("select name from `tabPage Role` where parent=%s and role='Guest'", doc.name):
		webnotes.response['403'] = 1
		raise webnotes.PermissionError, '[WNF] No read permission for %s %s' % ('Page', doc.name)

def get(dt, dn='', with_children = 1, from_controller = 0, prefix = 'tab'):
	"""
	Returns a doclist containing the main record and all child records
	"""	
	import webnotes
	import webnotes.model
	from webnotes.model.doclist import DocList
	
	dn = dn or dt

	# load the main doc
	doc = Document(dt, dn, prefix=prefix)

	if dt=='Page' and webnotes.session['user'] == 'Guest':
		check_page_perm(doc)

	if not with_children:
		# done
		return DocList([doc,])
	
	# get all children types
	tablefields = webnotes.model.meta.get_table_fields(dt)

	# load chilren
	doclist = DocList([doc,])
	for t in tablefields:
		doclist += getchildren(doc.name, t[0], t[1], dt, prefix=prefix)

	return doclist

def getsingle(doctype):
	"""get single doc as dict"""
	dataset = webnotes.conn.sql("select field, value from tabSingles where doctype=%s", doctype)
	return dict(dataset)
	
def copy_common_fields(from_doc, to_doc):
	from webnotes.model import default_fields
	doctype_list = webnotes.get_doctype(to_doc.doctype)
	
	for fieldname, value in from_doc.fields.items():
		if fieldname in default_fields:
			continue
		
		if doctype_list.get_field(fieldname) and to_doc.fields[fieldname] != value:
			to_doc.fields[fieldname] = value
			
def validate_name(doctype, name, case=None, merge=False):
	if not merge:
		if webnotes.conn.sql('select name from `tab%s` where name=%s' % (doctype,'%s'), name):
			raise NameError, 'Name %s already exists' % name
	
	# no name
	if not name: return 'No Name Specified for %s' % doctype
	
	# new..
	if name.startswith('New '+doctype):
		raise NameError, 'There were some errors setting the name, please contact the administrator'
	
	if case=='Title Case': name = name.title()
	if case=='UPPER CASE': name = name.upper()
	
	name = name.strip() # no leading and trailing blanks

	forbidden = ['%', "'", '"', '#', '*', '?', '`']
	for f in forbidden:
		if f in name:
			webnotes.msgprint('%s not allowed in ID (name)' % f, raise_exception =1)
			
	return name
