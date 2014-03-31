# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""
	Customize Form is a Single DocType used to mask the Property Setter
	Thus providing a better UI from user perspective
"""
import frappe, json
from frappe.utils import cstr

from frappe.model.document import Document

class CustomizeForm(Document):
	doctype_properties = [
		'search_fields',
		'default_print_format',
		'read_only_onload',
		'allow_print',
		'allow_email',
		'allow_copy',
		'allow_attach',
		'max_attachments' 
	]
	
	docfield_properties = [
		'idx',
		'label',
		'fieldtype',
		'fieldname',
		'options',
		'permlevel',
		'width',
		'print_width',
		'reqd',
		'ignore_restrictions',
		'in_filter',
		'in_list_view',
		'hidden',
		'print_hide',
		'report_hide',
		'allow_on_submit',
		'depends_on',
		'description',
		'default',
		'name',
	]

	property_restrictions = {
		'fieldtype': [['Currency', 'Float'], ['Small Text', 'Data'], ['Text', 'Text Editor', 'Code']],
	}

	def get(self):
		"""
			Gets DocFields applied with Property Setter customizations via Customize Form Field
		"""
		self.clear()

		if self.doc_type:
			meta = frappe.get_meta(self.doc_type)
			for d in meta.get("fields"):
				new = self.append('fields', {})
				self.set({ 'list': self.docfield_properties, 'doc' : d, 'doc_to_set': new })
			self.set({ 'list': self.doctype_properties, 'doc': d })

	def clear(self):
		"""
			Clear fields in the doc
		"""
		# Clear table before adding new doctype's fields
		self.set('fields', [])
		self.set({ 'list': self.doctype_properties, 'value': None })
	
		
	def set(self, args):
		"""
			Set a list of attributes of a doc to a value
			or to attribute values of a doc passed
			
			args can contain:
			* list --> list of attributes to set
			* doc_to_set --> defaults to self
			* value --> to set all attributes to one value eg. None
			* doc --> copy attributes from doc to doc_to_set
		"""
		if not 'doc_to_set' in args:
			args['doc_to_set'] = self

		if 'list' in args:
			if 'value' in args:
				for f in args['list']:
					args['doc_to_set'].set(f, None)
			elif 'doc' in args:
				for f in args['list']:
					args['doc_to_set'].set(f, args['doc'].get(f))
		else:
			frappe.msgprint("Please specify args['list'] to set", raise_exception=1)


	def post(self):
		"""
			Save diff between Customize Form Bean and DocType Bean as property setter entries
		"""
		if self.doc_type:
			from frappe.model import doc
			from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype
			
			this_doclist = self
			ref_doclist = frappe.get_meta(self.doc_type)
			dt_doclist = frappe.get_doc('DocType', self.doc_type)
			
			# get a list of property setter docs
			self.idx_dirty = False
			diff_list = self.diff(this_doclist, ref_doclist, dt_doclist)
			
			if self.idx_dirty:
				self.make_idx_property_setter(this_doclist, diff_list)
			
			self.set_properties(diff_list)

			validate_fields_for_doctype(self.doc_type)

			frappe.clear_cache(doctype=self.doc_type)
			frappe.msgprint("Updated")


	def diff(self, new_dl, ref_dl, dt_dl):
		"""
			Get difference between new_dl doclist and ref_dl doclist
			then check how it differs from dt_dl i.e. default doclist
		"""
		import re
		self.defaults = self.get_defaults()
		diff_list = []
		for new_d in new_dl:
			for ref_d in ref_dl:
				if ref_d.doctype == 'DocField' and new_d.name == ref_d.name:
					for prop in self.docfield_properties:
						# do not set forbidden properties like idx
						if prop=="idx": 
							if ref_d.idx != new_d.idx:
								self.idx_dirty = True
							continue
						
						# check if its custom field:
						if ref_d.get("__custom_field"):
							# update custom field
							if self.has_property_changed(ref_d, new_d, prop):
								# using set_value not bean because validations are called
								# in the end anyways
								frappe.db.set_value("Custom Field", ref_d.name, prop, new_d.get(prop))
						else:
							d = self.prepare_to_set(prop, new_d, ref_d, dt_dl)
							if d: diff_list.append(d)
					break
				
				elif ref_d.doctype == 'DocType' and new_d.doctype == 'Customize Form':
					for prop in self.doctype_properties:
						d = self.prepare_to_set(prop, new_d, ref_d, dt_dl)
						if d: diff_list.append(d)
					break

		return diff_list


	def get_defaults(self):
		"""
			Get fieldtype and default value for properties of a field
		"""
		df_defaults = frappe.db.sql("""
			SELECT fieldname, fieldtype, `default`, label
			FROM `tabDocField`
			WHERE parent='DocField' or parent='DocType'""", as_dict=1)
		
		defaults = {}
		for d in df_defaults:
			defaults[d['fieldname']] = d
		defaults['idx'] = {'fieldname' : 'idx', 'fieldtype' : 'Int', 'default' : 1, 'label' : 'idx'}
		defaults['previous_field'] = {'fieldname' : 'previous_field', 'fieldtype' : 'Data', 'default' : None, 'label' : 'Previous Field'}
		return defaults


	def has_property_changed(self, ref_d, new_d, prop):
		return new_d.get(prop) != ref_d.get(prop) \
		and not \
		( \
			new_d.get(prop) in [None, 0] \
			and ref_d.get(prop) in [None, 0] \
		) and not \
		( \
			new_d.get(prop) in [None, ''] \
			and ref_d.get(prop) in [None, ''] \
		)
		
	def prepare_to_set(self, prop, new_d, ref_d, dt_doclist, delete=0):
		"""
			Prepares docs of property setter
			sets delete property if it is required to be deleted
		"""
		# Check if property has changed compared to when it was loaded 
		if self.has_property_changed(ref_d, new_d, prop):
			#frappe.msgprint("new: " + str(new_d.get(prop)) + " | old: " + str(ref_d.get(prop)))
			# Check if the new property is same as that in original doctype
			# If yes, we need to delete the property setter entry
			for dt_d in dt_doclist:
				if dt_d.name == ref_d.name \
				and (new_d.get(prop) == dt_d.get(prop) \
				or \
				( \
					new_d.get(prop) in [None, 0] \
					and dt_d.get(prop) in [None, 0] \
				) or \
				( \
					new_d.get(prop) in [None, ''] \
					and dt_d.get(prop) in [None, ''] \
				)):
					delete = 1
					break
		
			value = new_d.get(prop)
			
			if prop in self.property_restrictions:
				allow_change = False
				for restrict_list in self.property_restrictions.get(prop):
					if value in restrict_list and \
							ref_d.get(prop) in restrict_list:
						allow_change = True
						break
				if not allow_change:
					frappe.msgprint("""\
						You cannot change '%s' of '%s' from '%s' to '%s'.
						%s can only be changed among %s.
						<i>Ignoring this change and saving.</i>""" % \
						(self.defaults.get(prop, {}).get("label") or prop,
						new_d.get("label") or new_d.get("idx"),
						ref_d.get(prop), value,
						self.defaults.get(prop, {}).get("label") or prop,
						" -or- ".join([", ".join(r) for r in \
							self.property_restrictions.get(prop)])), raise_exception=True)
					return None

			# If the above conditions are fulfilled,
			# create a property setter doc, but dont save it yet.
			d = frappe.get_doc('Property Setter')
			d.doctype_or_field = ref_d.doctype=='DocField' and 'DocField' or 'DocType'
			d.doc_type = self.doc_type
			d.field_name = ref_d.fieldname
			d.property = prop
			d.value = value
			d.property_type = self.defaults[prop]['fieldtype']
			#d.default_value = self.defaults[prop]['default']
			if delete: d.delete = 1
			
			if d.select_item:
				d.select_item = self.remove_forbidden(d.select_item)
			
			# return the property setter doc
			return d

		else: return None


	def make_idx_property_setter(self, doclist, diff_list):
		fields = []
		doclist.sort(lambda a, b: a.idx < b.idx)
		for d in doclist:
			if d.doctype=="Customize Form Field":
				fields.append(d.fieldname)
		
		d = frappe.get_doc('Property Setter')
		d.doctype_or_field = 'DocType'
		d.doc_type = self.doc_type
		d.property = "_idx"
		d.value = json.dumps(fields)
		d.property_type = "Text"
		diff_list.append(d)		

	def set_properties(self, ps_doclist):
		"""
			* Delete a property setter entry
				+ if it already exists
				+ if marked for deletion
			* Save the property setter doc in the list
		"""
		for d in ps_doclist:
			# Delete existing property setter entry
			if not d.get("field_name"):
				frappe.db.sql("""
					DELETE FROM `tabProperty Setter`
					WHERE doc_type = %(doc_type)s
					AND property = %(property)s""", d.fields)
			else:
				frappe.db.sql("""
					DELETE FROM `tabProperty Setter`
					WHERE doc_type = %(doc_type)s
					AND field_name = %(field_name)s
					AND property = %(property)s""", d.fields)
			
			# Save the property setter doc if not marked for deletion i.e. delete=0
			if not d.delete:
				d.insert()

	
	def delete(self):
		"""
			Deletes all property setter entries for the selected doctype
			and resets it to standard
		"""
		if self.doc_type:
			frappe.db.sql("""
				DELETE FROM `tabProperty Setter`
				WHERE doc_type = %s""", self.doc_type)
		
			frappe.clear_cache(doctype=self.doc_type)

		self.get()

	def remove_forbidden(self, string):
		"""
			Replace forbidden characters with a space
		"""
		forbidden = ['%', "'", '"', '#', '*', '?', '`']
		for f in forbidden:
			string.replace(f, ' ')
