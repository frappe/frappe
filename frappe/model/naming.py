# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import now_datetime, cint

def set_new_name(doc):
	"""Sets the `name`` property for the document based on various rules.

	1. If amened doc, set suffix.
	3. If `autoname` method is declared, then call it.
	4. If `autoname` property is set in the DocType (`meta`), then build it using the `autoname` property.
	2. If `name` is already defined, use that name
	5. If no rule defined, use hash.

	#### Note:

	:param doc: Document to be named."""

	doc.run_method("before_naming")

	autoname = frappe.get_meta(doc.doctype).autoname
	if getattr(doc, "amended_from", None):
		_set_amended_name(doc)
		return

	elif getattr(doc.meta, "issingle", False):
		doc.name = doc.doctype

	elif hasattr(doc, "autoname"):
		doc.run_method("autoname")

	elif autoname:
		if autoname.startswith('field:'):
			fieldname = autoname[6:]
			doc.name = (doc.get(fieldname) or "").strip()
			if not doc.name:
				frappe.throw(_("{0} is required").format(doc.meta.get_label(fieldname)))
				raise Exception, 'Name is required'
		if autoname.startswith("naming_series:"):
			set_name_by_naming_series(doc)
		elif "#" in autoname:
			doc.name = make_autoname(autoname)
		elif autoname=='Prompt':
			# set from __newname in save.py
			if not doc.name:
				frappe.throw(_("Name not set via Prompt"))

	if not doc.name:
		doc.name = make_autoname('hash', doc.doctype)

	doc.name = validate_name(doc.doctype, doc.name)

def set_name_by_naming_series(doc):
	"""Sets name by the `naming_series` property"""
	if not doc.naming_series:
		doc.naming_series = get_default_naming_series(doc.doctype)

	if not doc.naming_series:
		frappe.throw(frappe._("Naming Series mandatory"))

	doc.name = make_autoname(doc.naming_series+'.#####')

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
		return frappe.generate_hash(doctype, 10)

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

	if not frappe.get_meta(doctype).get("issingle") and (doctype == name) and (name!="DocType"):
		frappe.throw(_("Name of {0} cannot be {1}").format(doctype, name), frappe.NameError)

	return name

def _set_amended_name(doc):
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
			order by length(name) desc, name desc limit 1""".format(doc.doctype, doc.name))

		if last:
			count = str(cint(last[0][0].rsplit("-", 1)[1]) + 1)
		else:
			count = "1"

		doc.name = "{0}-{1}".format(doc.name, count)

def de_duplicate(doctype, name):
	original_name = name
	count = 0
	while True:
		if frappe.db.exists(doctype, name):
			count += 1
			name = "{0}-{1}".format(original_name, count)
		else:
			break

	return name
