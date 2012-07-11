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

"""
Contains the Document class representing an object / record
"""

import webnotes
import webnotes.model.meta

from webnotes.utils import *

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
	
	def __init__(self, doctype = '', name = '', fielddata = {}, prefix='tab'):
		self._roles = []
		self._perms = []
		self._user_defaults = {}
		self._prefix = prefix
		
		if fielddata: 
			self.fields = fielddata
		else: 
			self.fields = {}
		
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

	def __nonzero__(self):
		return True

	def __str__(self):
		return str(self.fields)

	# Load Document
	# ---------------------------------------------------------------------------

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

	# Load Fields from dataset
	# ---------------------------------------------------------------------------

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
			
	# Load Single Type
	# ---------------------------------------------------------------------------

	def _loadsingle(self):
		self.name = self.doctype
		self.fields.update(getsingle(self.doctype))

	# Setter
	# ---------------------------------------------------------------------------
			
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

	# Getter
	# ---------------------------------------------------------------------------

	def __getattr__(self, name):
		if self.__dict__.has_key(name):
			return self.__dict__[name]
		elif self.fields.has_key(name):
			return self.fields[name]	
		else:
			return ''

	# Get Amendement number
	# ---------------------------------------------------------------------------
	
	def _get_amended_name(self):
		am_id = 1
		am_prefix = self.amended_from
		if webnotes.conn.sql('select amended_from from `tab%s` where name = "%s"' % (self.doctype, self.amended_from))[0][0] or '':
			am_id = cint(self.amended_from.split('-')[-1]) + 1
			am_prefix = '-'.join(self.amended_from.split('-')[:-1]) # except the last hyphen
			
		self.name = am_prefix + '-' + str(am_id)

	# Set Name
	# ---------------------------------------------------------------------------

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
					
	# Validate Name
	# ---------------------------------------------------------------------------
	
	def _validate_name(self, case):

		if webnotes.conn.sql('select name from `tab%s` where name=%s' % (self.doctype,'%s'), self.name):
			raise NameError, 'Name %s already exists' % self.name
		
		# no name
		if not self.name: return 'No Name Specified for %s' % self.doctype
		
		# new..
		if self.name.startswith('New '+self.doctype):
			return 'There were some errors setting the name, please contact the administrator'
		
		if case=='Title Case': self.name = self.name.title()
		if case=='UPPER CASE': self.name = self.name.upper()
		
		self.name = self.name.strip() # no leading and trailing blanks

		forbidden = ['%', "'", '"', '#', '*', '?', '`']
		for f in forbidden:
			if f in self.name:
				webnotes.msgprint('%s not allowed in ID (name)' % f, raise_exception =1)
				
	# Insert
	# ---------------------------------------------------------------------------
	
	def insert(self, autoname, istable, case='', make_autoname=1):
		# set name
		if make_autoname:
			self._set_name(autoname, istable)
		
		# validate name
		self._validate_name(case)
				
		# insert!
		if not self.owner: self.owner = webnotes.session['user']
		self.modified_by = webnotes.session['user']
		self.creation = self.modified = now()
		webnotes.conn.sql("""insert into `tab%(doctype)s` (name, owner, creation, modified, modified_by) 
		values ('%(name)s', '%(owner)s', '%(creation)s', '%(modified)s', '%(modified_by)s')""" % self.fields)


	# Update Values
	# ---------------------------------------------------------------------------
	
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

	# Validate Links
	# ---------------------------------------------------------------------------

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
		if dt.lower().startswith('link:'):
			dt = dt[5:]
		if '\n' in dt:
			dt = dt.split('\n')[0]
		tmp = webnotes.conn.sql("""SELECT name FROM `tab%s` 
			WHERE name = %s""" % (dt, '%s'), dn)
		return tmp and tmp[0][0] or ''# match case

	# Update query
	# ---------------------------------------------------------------------------
		
	def _update_values(self, issingle, link_list, ignore_fields=0):
		if issingle:
			self._update_single(link_list)
		else:
			update_str, values = [], []
			# set modified timestamp
			self.modified = now()
			self.modified_by = webnotes.session['user']
			for f in self.fields.keys():
				if (not (f in ('doctype', 'name', 'perm', 'localname', 'creation','_user_tags'))) \
					and (not f.startswith('__')): # fields not saved
					
					# validate links
					if link_list and link_list.get(f):
						self.fields[f] = self._validate_link(link_list[f][0], self.fields[f])

					if self.fields[f]==None or self.fields[f]=='':
						update_str.append("`%s`=NULL" % f)
						if ignore_fields:
							try: r = webnotes.conn.sql("update `tab%s` set `%s`=NULL where name=%s" % (self.doctype, f, '%s'), self.name)
							except: pass
					else:
						values.append(self.fields[f])
						update_str.append("`%s`=%s" % (f, '%s'))
						if ignore_fields:
							try: r = webnotes.conn.sql("update `tab%s` set `%s`=%s where name=%s" % (self.doctype, f, '%s', '%s'), (self.fields[f], self.name))
							except: pass
			if values:
				if not ignore_fields:
					# update all in one query
					r = webnotes.conn.sql("update `tab%s` set %s where name='%s'" % (self.doctype, ', '.join(update_str), self.name), values)

	# Save values
	# ---------------------------------------------------------------------------
	
	def save(self, new=0, check_links=1, ignore_fields=0, make_autoname = 1):
		"""
	      Saves the current record in the database. If new = 1, creates a new instance of the record.
	      Also clears temperory fields starting with `__`
	      
	      * if check_links is set, it validates all `Link` fields
	      * if ignore_fields is sets, it does not throw an exception for any field that does not exist in the 
		database table
		"""	
		res = webnotes.model.meta.get_dt_values(self.doctype, 'autoname, issingle, istable, name_case', as_dict=1)
		res = res and res[0] or {}

		# add missing parentinfo (if reqd)
		if self.parent and not (self.parenttype and self.parentfield):
			self.update_parentinfo()
			
		if self.parent and not self.idx:
			self.set_idx()

		# if required, make new
		if new or (not new and self.fields.get('__islocal')) and (not res.get('issingle')):
			r = self.insert(res.get('autoname'), res.get('istable'), res.get('name_case'), \
				make_autoname)
			if r: 
				return r
				
		# save the values
		self._update_values(res.get('issingle'), check_links and self.make_link_list() or {}, ignore_fields)
		self._clear_temp_fields()

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

	# check permissions
	# ---------------------------------------------------------------------------

	def _get_perms(self):
		if not self._perms:
			self._perms = webnotes.conn.sql("""select role, `match` from tabDocPerm
				where parent=%s and ifnull(`read`,0) = 1 
				and ifnull(permlevel,0)=0""", self.doctype)

	def _get_roles(self):
		# check if roles match/
		if not self._roles:
			if webnotes.user:
				self._roles = webnotes.user.get_roles()
			else:
				self._roles = ['Guest']

	def _get_user_defaults(self):
		if not self._user_defaults:
			if webnotes.user:
				self._user_defaults = webnotes.user.get_defaults()
			else:
				self.defaults = {}

	def check_perm(self, verbose=0):
		import webnotes
		
		# Admin has all permissions
		if webnotes.session['user']=='Administrator':
			return 1
		
		# find roles with read access for this record at 0
		self._get_perms()
		self._get_roles()
		self._get_user_defaults()
	
		has_perm, match = 0, []
		
		# loop through everything to find if there is a match
		for r in self._perms:
			if r[0] in self._roles:
				has_perm = 1
				if r[1] and match != -1:
					match.append(r[1]) # add to match check
				else:
					match = -1 # has permission and no match, so match not required!
		
		if has_perm and match and match != -1:
			for m in match:
				if self.fields.get(m, 'no value') in self._user_defaults.get(m, 'no default'):
					has_perm = 1
					break # permission found! break
				else:
					has_perm = 0
					if verbose:
						webnotes.msgprint("Value not allowed: '%s' for '%s'" % (self.fields.get(m, 'no value'), m))
	
				
		return has_perm

	# Cleanup
	# ---------------------------------------------------------------------------
		
	def _clear_temp_fields(self):
		# clear temp stuff
		keys = self.fields.keys()
		for f in keys:
			if f.startswith('__'): 
				del self.fields[f]

	# Table methods
	# ---------------------------------------------------------------------------

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
		
		return doclist

	def addchild(self, fieldname, childtype = '', local=0, doclist=None):
		"""
	      Returns a child record of the give `childtype`.
	      
	      * if local is set, it does not save the record
	      * if doclist is passed, it append the record to the doclist
		"""
		d = Document()
		d.parent = self.name
		d.parenttype = self.doctype
		d.parentfield = fieldname
		d.doctype = childtype
		d.docstatus = 0;
		d.name = ''
		d.owner = webnotes.session['user']
		
		if local:
			d.fields['__islocal'] = '1' # for Client to identify unsaved doc
		else: 
			d.save(new=1)
	
		if doclist != None:
			doclist.append(d)
	
		return d

def addchild(parent, fieldname, childtype = '', local=0, doclist=None):
	"""
	
   Create a child record to the parent doc.
   
   Example::
   
     c = Document('Contact','ABC')
     d = addchild(c, 'contact_updates', 'Contact Update', local = 1)
     d.last_updated = 'Phone call'
     d.save(1)
	"""
	return parent.addchild(fieldname, childtype, local, doclist)
			
# Naming
# ------
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
	for e in l:
		en = ''
		if e.startswith('#'):
			digits = len(e)
			en = getseries(n, digits, doctype)
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

# Get Series for Autoname
# -----------------------
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


# Get Children
# ------------

def getchildren(name, childtype, field='', parenttype='', from_doctype=0, prefix='tab'):
	import webnotes
	
	tmp = ''
	
	if field: 
		tmp = ' and parentfield="%s" ' % field
	if parenttype:
		tmp = ' and parenttype="%s" ' % parenttype

	try:
		dataset = webnotes.conn.sql("select * from `%s%s` where parent='%s' %s order by idx" \
			% (prefix, childtype, name, tmp))
		desc = webnotes.conn.get_description()
	except Exception, e:
		if prefix=='arc' and e.args[0]==1146:
			return []
		else:
			raise e

	l = []
	
	for i in dataset:
		d = Document()
		d.doctype = childtype
		d._load_values(i, desc)
		l.append(d)
	
	return l

# Check if "Guest" is allowed to view this page
# ---------------------------------------------

def check_page_perm(doc):
	if doc.name=='Login Page':
		return
	if doc.publish:
		return

	if not webnotes.conn.sql("select name from `tabPage Role` where parent=%s and role='Guest'", doc.name):
		webnotes.response['403'] = 1
		raise webnotes.PermissionError, '[WNF] No read permission for %s %s' % ('Page', doc.name)

def get_report_builder_code(doc):
	if doc.doctype=='Search Criteria':
		from webnotes.model.code import get_code
		
		if doc.standard != 'No':
			doc.report_script = get_code(doc.module, 'Search Criteria', doc.name, 'js')
			doc.custom_query = get_code(doc.module, 'Search Criteria', doc.name, 'sql')

	
# called from everywhere
# load a record and its child records and bundle it in a list - doclist
# ---------------------------------------------------------------------

def get(dt, dn='', with_children = 1, from_get_obj = 0, prefix = 'tab'):
	"""
	Returns a doclist containing the main record and all child records
	"""	
	import webnotes
	import webnotes.model

	dn = dn or dt

	# load the main doc
	doc = Document(dt, dn, prefix=prefix)

	# check permission - for doctypes, pages
	if (dt in ('DocType', 'Page', 'Control Panel', 'Search Criteria')) or (from_get_obj and webnotes.session.get('user') != 'Guest'):
		if dt=='Page' and webnotes.session['user'] == 'Guest':
			check_page_perm(doc)
	else:
		if not doc.check_perm():
			webnotes.response['403'] = 1
			raise webnotes.ValidationError, '[WNF] No read permission for %s %s' % (dt, dn)

	if not with_children:
		# done
		return [doc,]
	
	# get all children types
	tablefields = webnotes.model.meta.get_table_fields(dt)

	# load chilren
	doclist = [doc,]
	for t in tablefields:
		doclist += getchildren(doc.name, t[0], t[1], dt, prefix=prefix)

	# import report_builder code
	if not from_get_obj:
		get_report_builder_code(doc)

	return doclist

def getsingle(doctype):
	"""get single doc as dict"""
	dataset = webnotes.conn.sql("select field, value from tabSingles where doctype=%s", doctype)
	return dict(dataset)
	
