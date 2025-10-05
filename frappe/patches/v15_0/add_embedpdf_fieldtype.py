import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	"""Add EmbedPdf fieldtype to core DocTypes for multi-tenant compatibility"""
	
	# List of DocTypes that need EmbedPdf fieldtype in their options
	doctypes_to_update = [
		"Custom Field",
		"Customize Form Field", 
		"DocField"
	]
	
	for doctype_name in doctypes_to_update:
		try:
			# Get the DocType
			doctype = frappe.get_doc("DocType", doctype_name)
			
			# Find fieldtype field
			fieldtype_field = None
			for field in doctype.fields:
				if field.fieldname == "fieldtype":
					fieldtype_field = field
					break
			
			if not fieldtype_field:
				continue
				
			# Check if EmbedPdf already exists
			if fieldtype_field.options and "EmbedPdf" in fieldtype_field.options:
				continue
				
			# Split options into list
			options_list = fieldtype_field.options.split('\n') if fieldtype_field.options else []
			
			# Find Dynamic Link position and insert EmbedPdf after it
			if "Dynamic Link" in options_list:
				dynamic_link_index = options_list.index("Dynamic Link")
				options_list.insert(dynamic_link_index + 1, "EmbedPdf")
				
				# Update the field options
				fieldtype_field.options = '\n'.join(options_list)
				
				# Save the DocType
				doctype.save()
				
				frappe.log(f"Added EmbedPdf to {doctype_name}")
			else:
				frappe.log(f"Dynamic Link not found in {doctype_name}")
				
		except Exception as e:
			frappe.log(f"Error updating {doctype_name}: {str(e)}")
			continue
			
	# Clear cache to reload DocType definitions
	frappe.clear_cache()