# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.utils import now_datetime, cint

def set_new_name(doc):
	if getattr(doc, "_new_name_set", False):
		# already set by doc
		return

	doc._new_name_set = True
	autoname = frappe.get_meta(doc.doctype).autoname

	# amendments
	if getattr(doc, "amended_from", None):
		return _get_amended_name(doc)
	else:
		tmp = getattr(doc, "autoname", None)
		if tmp and not isinstance(tmp, basestring):
			# autoname in a function, not a property
			doc.autoname()
		if doc.name:
			return

	# based on a field
	if autoname and autoname.startswith('field:'):
		n = doc.get(autoname[6:])
		if not n:
			raise Exception, 'Name is required'
		doc.name = n.strip()

	elif autoname and autoname.startswith("naming_series:"):
		if not doc.naming_series:
			doc.naming_series = get_default_naming_series(doc.doctype)

		if not doc.naming_series:
			frappe.msgprint(frappe._("Naming Series mandatory"), raise_exception=True)
		doc.name = make_autoname(doc.naming_series+'.#####')

	# call the method!
	elif autoname and autoname!='Prompt':
		doc.name = make_autoname(autoname, doc.doctype)

	# given
	elif doc.get('__newname', None):
		doc.name = doc.get('__newname')

	# default name for table
	elif doc.meta.istable:
		doc.name = make_autoname('#########', doc.doctype)

	# unable to determine a name, use global series
	if not doc.name:
		doc.name = make_autoname('#########', doc.doctype)

	validate_name(doc.doctype, doc.name)

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
	if key=="hash":
		return frappe.generate_hash(doctype)

	if not "#" in key:
		key = key + ".#####"

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
	current = frappe.db.sql("select `current` from `tabSeries` where name=%s for update", (key,))
	if current and current[0][0] is not None:
		current = current[0][0]
		# yes, update it
		frappe.db.sql("update tabSeries set current = current+1 where name=%s", (key,))
		current = cint(current) + 1
	else:
		# no, create it
		frappe.db.sql("insert into tabSeries (name, current) values (%s, 1)", (key,))
		current = 1
	return ('%0'+str(digits)+'d') % current

def get_default_naming_series(doctype):
	"""get default value for `naming_series` property"""
	naming_series = frappe.get_meta(doctype).get_field("naming_series").options or ""
	if naming_series:
		naming_series = naming_series.split("\n")
		return naming_series[0] or naming_series[1]
	else:
		return None

def validate_name(doctype, name, case=None, merge=False):
	if not name: return 'No Name Specified for %s' % doctype
	if name.startswith('New '+doctype):
		raise frappe.NameError, 'There were some errors setting the name, please contact the administrator'
	if case=='Title Case': name = name.title()
	if case=='UPPER CASE': name = name.upper()
	name = name.strip()
	return name

def _get_amended_name(doc):
	am_id = 1
	am_prefix = doc.amended_from
	if frappe.db.get_value(doc.doctype, doc.amended_from, "amended_from"):
		am_id = cint(doc.amended_from.split('-')[-1]) + 1
		am_prefix = '-'.join(doc.amended_from.split('-')[:-1]) # except the last hyphen

	doc.name = am_prefix + '-' + str(am_id)
	return doc.name

def append_number_if_name_exists(doc):
	if frappe.db.exists(doc.doctype, doc.name):
		last = frappe.db.sql("""select name from `tab{}`
			where name regexp '{}-[[:digit:]]+'
			order by name desc limit 1""".format(doc.doctype, doc.name))

		if last:
			count = str(cint(last[0][0].rsplit("-", 1)[1]) + 1)
		else:
			count = "1"

		doc.name = "{0}-{1}".format(doc.name, count)

