"""Utilities needed to prepare the system to use original names for amended docs.

From Version 14, The naming pattern is changed in a way that amended documents will
have the original name `orig_name` instead of `orig_name-X`. To make this happen
the cancelled document naming pattern is changed to 'orig_name-CANC-X'.

In version 13, whenever a submittable document is amended it's name is set to orig_name-X,
where X is a counter and it increments when amended again and so on. We are backporting
the version-14 styled naming into version-13 and will be available through system settings.
"""

import functools
import traceback

import frappe

def get_submittable_doctypes():
	"""Returns list of submittable doctypes in the system.
	"""
	return frappe.db.get_all('DocType', filters={'is_submittable': 1}, pluck='name')

def get_cancelled_doc_names(doctype):
	"""Return names of cancelled document names those are in old format.
	"""
	docs = frappe.db.get_all(doctype, filters={'docstatus': 2}, pluck='name')
	return [each for each in docs if not (each.endswith('-CANC') or ('-CANC-' in each))]

@functools.lru_cache()
def get_linked_doctypes():
	"""Returns list of doctypes those are linked with given doctype using 'Link' fieldtype.
	"""
	filters=[['fieldtype','=', 'Link']]
	links = frappe.get_all("DocField",
		fields=["parent", "fieldname", "options as linked_to"],
		filters=filters,
		as_list=1)

	links+= frappe.get_all("Custom Field",
		fields=["dt as parent", "fieldname", "options as linked_to"],
		filters=filters,
		as_list=1)

	links_by_doctype = {}
	for doctype, fieldname, linked_to in links:
		links_by_doctype.setdefault(linked_to, []).append((doctype, fieldname))
	return links_by_doctype

@functools.lru_cache()
def get_single_doctypes():
	return frappe.get_all("DocType", filters={'issingle': 1}, pluck='name')

@functools.lru_cache()
def get_dynamic_linked_doctypes():
	filters=[['fieldtype','=', 'Dynamic Link']]

	# find dynamic links of parents
	links = frappe.get_all("DocField",
		fields=["parent as doctype", "fieldname", "options as doctype_fieldname"],
		filters=filters,
		as_list=1)
	links+= frappe.get_all("Custom Field",
		fields=["dt as doctype", "fieldname", "options as doctype_fieldname"],
		filters=filters,
		as_list=1)
	return links

@functools.lru_cache()
def get_child_tables():
	"""
	"""
	filters =[['fieldtype', 'in', ('Table', 'Table MultiSelect')]]
	links = frappe.get_all("DocField",
		fields=["parent as doctype", "options as child_table"],
		filters=filters,
		as_list=1)

	links+= frappe.get_all("Custom Field",
		fields=["dt as doctype", "options as child_table"],
		filters=filters,
		as_list=1)

	map = {}
	for doctype, child_table in links:
		map.setdefault(doctype, []).append(child_table)
	return map

def update_cancelled_document_names(doctype, cancelled_doc_names):
	return frappe.db.sql("""
		update
			`tab{doctype}`
		set
			name=CONCAT(name, '-CANC')
		where
			docstatus=2
			and
			name in %(cancelled_doc_names)s;
	""".format(doctype=doctype), {'cancelled_doc_names': cancelled_doc_names})

def update_amended_field(doctype, cancelled_doc_names):
	return frappe.db.sql("""
		update
			`tab{doctype}`
		set
			amended_from=CONCAT(amended_from, '-CANC')
		where
			amended_from in %(cancelled_doc_names)s;
	""".format(doctype=doctype), {'cancelled_doc_names': cancelled_doc_names})

def update_attachments(doctype, cancelled_doc_names):
	frappe.db.sql("""
		update
			`tabFile`
		set
			attached_to_name=CONCAT(attached_to_name, '-CANC')
		where
			attached_to_doctype=%(dt)s and attached_to_name in %(cancelled_doc_names)s
		""", {'cancelled_doc_names': cancelled_doc_names, 'dt': doctype})

def update_versions(doctype, cancelled_doc_names):
	frappe.db.sql("""
		UPDATE
			`tabVersion`
		SET
			docname=CONCAT(docname, '-CANC')
		WHERE
			ref_doctype=%(dt)s AND docname in %(cancelled_doc_names)s
		""", {'cancelled_doc_names': cancelled_doc_names, 'dt': doctype})

def update_linked_doctypes(doctype, cancelled_doc_names):
	single_doctypes = get_single_doctypes()

	for linked_dt, field in get_linked_doctypes().get(doctype, []):
		if linked_dt not in single_doctypes:
			frappe.db.sql("""
				update
					`tab{linked_dt}`
				set
					`{column}`=CONCAT(`{column}`, '-CANC')
				where
					`{column}` in %(cancelled_doc_names)s;
			""".format(linked_dt=linked_dt, column=field),
				{'cancelled_doc_names': cancelled_doc_names})
		else:
			doc = frappe.get_single(linked_dt)
			if getattr(doc, field) in cancelled_doc_names:
				setattr(doc, field, getattr(doc, field)+'-CANC')
				doc.flags.ignore_mandatory=True
				doc.flags.ignore_validate=True
				doc.save(ignore_permissions=True)

def update_dynamic_linked_doctypes(doctype, cancelled_doc_names):
	single_doctypes = get_single_doctypes()

	for linked_dt, fieldname, doctype_fieldname in get_dynamic_linked_doctypes():
		if linked_dt not in single_doctypes:
			frappe.db.sql("""
				update
					`tab{linked_dt}`
				set
					`{column}`=CONCAT(`{column}`, '-CANC')
				where
					`{column}` in %(cancelled_doc_names)s and {doctype_fieldname}=%(dt)s;
			""".format(linked_dt=linked_dt, column=fieldname, doctype_fieldname=doctype_fieldname),
				{'cancelled_doc_names': cancelled_doc_names, 'dt': doctype})
		else:
			doc = frappe.get_single(linked_dt)
			if getattr(doc, doctype_fieldname) == doctype and getattr(doc, fieldname) in cancelled_doc_names:
				setattr(doc, fieldname, getattr(doc, fieldname)+'-CANC')
				doc.flags.ignore_mandatory=True
				doc.flags.ignore_validate=True
				doc.save(ignore_permissions=True)

def update_child_tables(doctype, cancelled_doc_names):
	child_tables = get_child_tables().get(doctype, [])
	single_doctypes = get_single_doctypes()

	for table in child_tables:
		if table not in single_doctypes:
			frappe.db.sql("""
				update
					`tab{table}`
				set
					parent=CONCAT(parent, '-CANC')
				where
					parenttype=%(dt)s and parent in %(cancelled_doc_names)s;
			""".format(table=table), {'cancelled_doc_names': cancelled_doc_names, 'dt': doctype})
		else:
			doc = frappe.get_single(table)
			if getattr(doc, 'parenttype')==doctype and getattr(doc, 'parent') in cancelled_doc_names:
				setattr(doc, 'parent', getattr(doc, 'parent')+'-CANC')
				doc.flags.ignore_mandatory=True
				doc.flags.ignore_validate=True
				doc.save(ignore_permissions=True)

def rename_cancelled_docs():
	submittable_doctypes = get_submittable_doctypes()

	for dt in submittable_doctypes:
		for retry in range(2):
			try:
				cancelled_doc_names = tuple(get_cancelled_doc_names(dt))
				if not cancelled_doc_names:
					break
				update_cancelled_document_names(dt, cancelled_doc_names)
				update_amended_field(dt, cancelled_doc_names)
				update_child_tables(dt, cancelled_doc_names)
				update_linked_doctypes(dt, cancelled_doc_names)
				update_dynamic_linked_doctypes(dt, cancelled_doc_names)
				update_attachments(dt, cancelled_doc_names)
				update_versions(dt, cancelled_doc_names)
				print(f"Renaming cancelled records of {dt} doctype")
				frappe.db.commit()
				break
			except Exception:
				if retry == 1:
					msg = f"Failed to rename the cancelled records of {dt} doctype"
					frappe.log_error(message=frappe.get_traceback(), title=msg)
					print(msg + ", moving on!")
					traceback.print_exc()
				frappe.db.rollback()

