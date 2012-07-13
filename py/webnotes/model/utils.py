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
Model utilities, unclassified functions
"""

def expand(docs):
	"""
		Expand a doclist sent from the client side. (Internally used by the request handler)
	"""
	def xzip(a,b):
		d = {}
		for i in range(len(a)):
			d[a[i]] = b[i]
		return d

	from webnotes.utils import load_json

	docs = load_json(docs)
	clist = []
	for d in docs['_vl']:
		doc = xzip(docs['_kl'][d[0]], d);
		clist.append(doc)
	return clist

def compress(doclist):
	"""
	   Compress a doclist before sending it to the client side. (Internally used by the request handler)

	"""
	if doclist and hasattr(doclist[0],'fields'):
		docs = [d.fields for d in doclist]
	else:
		docs = doclist

	kl, vl = {}, []
	forbidden = ['server_code_compiled']

	# scan for keys & values
	for d in docs:
		dt = d['doctype']
		if not (dt in kl.keys()):
			kl[dt] = ['doctype','localname','__oldparent','__unsaved']	

		# add client script for doctype, doctype due to ambiguity
		if dt=='DocType' and '__client_script' not in kl[dt]: 
			kl[dt].append('__client_script')

		for f in d.keys():
			if not (f in kl[dt]) and not (f in forbidden):
				# if key missing, then append
				kl[dt].append(f)

		# build values
		tmp = []
		for f in kl[dt]:
			v = d.get(f)
			if type(v)==long:
				v=int(v)
			tmp.append(v)

		vl.append(tmp)
	#errprint(str({'_vl':vl,'_kl':kl}))
	return {'_vl':vl,'_kl':kl}


def getlist(doclist, field):
	"""
   Filter a list of records for a specific field from the full doclist

   Example::

     # find all phone call details
     dl = getlist(self.doclist, 'contact_updates')
     pl = []
     for d in dl:
       if d.type=='Phone':
         pl.append(d)
	"""
	from webnotes.utils import cint
	l = []
	for d in doclist:
		if d.parent and (not d.parent.lower().startswith('old_parent:')) and d.parentfield == field:
			l.append(d)

	l.sort(lambda a, b: cint(a.idx) - cint(b.idx))

	return l

# Copy doclist
# ------------

def copy_doclist(doclist, no_copy = []):
	"""
      Save & return a copy of the given doclist
      Pass fields that are not to be copied in `no_copy`
	"""
	from webnotes.model.doc import Document

	cl = []

	# main doc
	c = Document(fielddata = doclist[0].fields.copy())

	# clear no_copy fields
	for f in no_copy:
		if c.fields.has_key(f):
			c.fields[f] = None

	c.name = None
	c.save(1)
	cl.append(c)

	# new parent name
	parent = c.name

	# children
	for d in doclist[1:]:
		c = Document(fielddata = d.fields.copy())
		c.name = None

		# clear no_copy fields
		for f in no_copy:
			if c.fields.has_key(f):
				c.fields[f] = None

		c.parent = parent
		c.save(1)
		cl.append(c)

	return cl

def getvaluelist(doclist, fieldname):
	"""
		Returns a list of values of a particualr fieldname from all Document object in a doclist
	"""
	l = []
	for d in doclist:
		l.append(d.fields[fieldname])
	return l

def _make_html(doc, link_list):

	from webnotes.utils import cstr
	out = '<table class="simpletable">'
	for k in doc.fields.keys():
		if k!='server_code_compiled':
			v = cstr(doc.fields[k])

			# link field
			if v and (k in link_list.keys()):
				dt = link_list[k]
				if isinstance(dt, basestring) and dt.startswith('link:'):
					dt = dt[5:]
				v = '<a href="index.cgi?page=Form/%s/%s">%s</a>' % (dt, v, v)

			out += '\t<tr><td>%s</td><td>%s</td></tr>\n' % (cstr(k), v)

	out += '</table>'
	return out

def to_html(doclist):
	"""
	Return a simple HTML format of the doclist
	"""
	out = ''
	link_lists = {}

	for d in doclist:
		if not link_lists.get(d.doctype):
			link_lists[d.doctype] = d.make_link_list()

		out += _make_html(d, link_lists[d.doctype])

	return out

def commonify_doclist(doclist, with_comments=1):
	"""
		Makes a doclist more readable by extracting common properties.
		This is used for printing Documents in files
	"""
	from webnotes.utils import get_common_dict, get_diff_dict

	def make_common(doclist):
		c = {}
		if with_comments:
			c['##comment'] = 'These values are common in all dictionaries'
		for k in common_keys:
			c[k] = doclist[0][k]
		return c

	def strip_common_and_idx(d):
		for k in common_keys:
			if k in d: del d[k]
			
		if 'idx' in d: del d['idx']
		return d

	def make_common_dicts(doclist):

		common_dict = {} # one per doctype

		# make common dicts for all records
		for d in doclist:
			if not d['doctype'] in common_dict:
				d1 = d.copy()
				del d1['name']
				common_dict[d['doctype']] = d1
			else:
				common_dict[d['doctype']] = get_common_dict(common_dict[d['doctype']], d)
		return common_dict

	common_keys = ['owner','docstatus','creation','modified','modified_by']
	common_dict = make_common_dicts(doclist)

	# make docs
	final = []
	for d in doclist:
		f = strip_common_and_idx(get_diff_dict(common_dict[d['doctype']], d))
		f['doctype'] = d['doctype'] # keep doctype!

		# strip name for child records (only an auto generated number!)
		if f['doctype'] != doclist[0]['doctype']:
			del f['name']

		if with_comments:
			f['##comment'] = d['doctype'] + ('name' in f and (', ' + f['name']) or '')
		final.append(f)

	# add commons
	commons = []
	for d in common_dict.values():
		d['name']='__common__'
		if with_comments:
			d['##comment'] = 'These values are common for all ' + d['doctype']
		commons.append(strip_common_and_idx(d))

	common_values = make_common(doclist)
	return [common_values]+commons+final

def uncommonify_doclist(dl):
	"""
		Expands an commonified doclist
	"""
	# first one has common values
	common_values = dl[0]
	common_dict = {}
	final = []
	idx_dict = {}

	for d in dl[1:]:
		if 'name' in d and d['name']=='__common__':
			# common for a doctype - 
			del d['name']
			common_dict[d['doctype']] = d
		else:
			dt = d['doctype']
			if not dt in idx_dict: idx_dict[dt] = 1;
			d1 = common_values.copy()

			# update from common and global
			d1.update(common_dict[dt])
			d1.update(d)

			# idx by sequence
			d1['idx'] = idx_dict[dt]
			
			# increment idx
			idx_dict[dt] += 1

			final.append(d1)

	return final

def pprint_doclist(doclist, with_comments = 1):
	"""
		Pretty Prints a doclist with common keys separated and comments
	"""
	from webnotes.utils import pprint_dict

	dictlist =[pprint_dict(d) for d in commonify_doclist(doclist, with_comments)]
	title = '# '+doclist[0]['doctype']+', '+doclist[0]['name']
	return title + '\n[\n' + ',\n'.join(dictlist) + '\n]'

def peval_doclist(txt):
	"""
		Restore a pretty printed doclist
	"""
	if txt.startswith('#'):
		return uncommonify_doclist(eval(txt))
	else:
		return eval(txt)

	return uncommonify_doclist(eval(txt))