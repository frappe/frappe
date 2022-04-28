import frappe

# this is a separate file since it is imported in frappe.model.document
# to avoid circular imports

EVENT_MAP = {
	"before_insert": "Before Insert",
	"after_insert": "After Insert",
	"before_validate": "Before Validate",
	"validate": "Before Save",
	"on_update": "After Save",
	"before_submit": "Before Submit",
	"on_submit": "After Submit",
	"before_cancel": "Before Cancel",
	"on_cancel": "After Cancel",
	"on_trash": "Before Delete",
	"after_delete": "After Delete",
	"before_update_after_submit": "Before Save (Submitted Document)",
	"on_update_after_submit": "After Save (Submitted Document)",
	"on_payment_authorized": "On Payment Authorization",
}


def run_server_script_for_doc_event(doc, event):
	# run document event method
	if not event in EVENT_MAP:
		return

	if frappe.flags.in_install:
		return

	if frappe.flags.in_migrate:
		return

	scripts = get_server_script_map().get(doc.doctype, {}).get(EVENT_MAP[event], None)
	if scripts:
		# run all scripts for this doctype + event
		for script_name in scripts:
			frappe.get_doc("Server Script", script_name).execute_doc(doc)


def get_server_script_map():
	# fetch cached server script methods
	# {
	# 	'[doctype]': {
	# 		'Before Insert': ['[server script 1]', '[server script 2]']
	# 	},
	# 	'_api': {
	# 		'[path]': '[server script]'
	# 	},
	# 	'permission_query': {
	# 		'DocType': '[server script]'
	# 	}
	# }
	if frappe.flags.in_patch and not frappe.db.table_exists("Server Script"):
		return {}

	script_map = frappe.cache().get_value("server_script_map")
	if script_map is None:
		script_map = {"permission_query": {}}
		enabled_server_scripts = frappe.get_all(
			"Server Script",
			fields=("name", "reference_doctype", "doctype_event", "api_method", "script_type"),
			filters={"disabled": 0},
		)
		for script in enabled_server_scripts:
			if script.script_type == "DocType Event":
				script_map.setdefault(script.reference_doctype, {}).setdefault(
					script.doctype_event, []
				).append(script.name)
			elif script.script_type == "Permission Query":
				script_map["permission_query"][script.reference_doctype] = script.name
			else:
				script_map.setdefault("_api", {})[script.api_method] = script.name

		frappe.cache().set_value("server_script_map", script_map)

	return script_map
