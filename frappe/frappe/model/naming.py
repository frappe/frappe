# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import now_datetime, cint

def set_new_name(doc):
	if doc.name:
		return

	# amendments
	if getattr(doc, "amended_from", None):
		return _get_amended_name(doc)

	elif hasattr(doc, "run_method"):
		doc.run_method("autoname")
		if doc.name:
			return

	autoname = frappe.get_meta(doc.doctype).autoname

	# based on a field
	if autoname:
		if autoname.startswith('field:'):
			n = doc.get(autoname[6:])
			if not n:
				raise Exception, 'Name is required'
			doc.name = n.strip()

		elif autoname.startswith("naming_series:"):
			if not doc.naming_series:
				doc.naming_series = get_default_naming_series(doc.doctype)

			if not doc.naming_series:
				frappe.msgprint(frappe._("Naming Series mandatory"), raise_exception=True)
			doc.name = make_autoname(doc.naming_series+'.#####')

		# call the method!
		elif autoname=='Prompt':
			# set from __newname in save.py
			if not doc.name:
				frappe.throw(frappe._("Name not set via Prompt"))

		else:
			doc.name = make_autoname(autoname, doc.doctype)

	# default name for table
	elif doc.meta.istable:
		doc.name = make_autoname('hash', doc.doctype)

	elif doc.meta.issingle:
		doc.name = doc.doctype

	# unable to determine a name, use global series
	if not doc.name:
		doc.name = make_autoname('hash', doc.doctype)

	doc.name = doc.name.strip()

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
	elif not "." in key:
		frappe.throw(_("Invalid naming series (. missing)") + (_(" for {0}").format(doctype) if doctype else ""))

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

def revert_series_if_last(key, name):
	if ".#" in key:
		prefix, hashes = key.rsplit(".", 1)
		if "#" not in hashes:
			return
	else:
		prefix = key

	count = cint(name.replace(prefix, ""))
	current = frappe.db.sql("select `current` from `tabSeries` where name=%s for update", (prefix,))

	if current and current[0][0]==count:
		frappe.db.sql("update tabSeries set current=current-1 where name=%s", prefix)

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
		frappe.throw(_('There were some errors setting the name, please contact the administrator'), frappe.NameError)
	if case=='Title Case': name = name.title()
	if case=='UPPER CASE': name = name.upper()
	name = name.strip()

	if not frappe.get_meta(doctype).get("issingle") and doctype == name:
		frappe.throw(_("Name of {0} cannot be {1}").format(doctype, name), frappe.NameError)

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

