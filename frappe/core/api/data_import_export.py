# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Public data import/export API — imports, exports and customization dumps.

Endpoints were consolidated from the Data Import doctype, the Data Export
exporter, `frappe.utils.csvutils` and `frappe.modules.utils`; the old
dotted paths keep working via aliases in the original modules.
"""

import os
from typing import TYPE_CHECKING, Any

from rq.command import send_stop_job_command
from rq.exceptions import InvalidJobOperation

import frappe
from frappe import _, scrub
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.model.utils.user_settings import get_user_settings
from frappe.modules.utils import get_module_path
from frappe.public_api import public
from frappe.utils import cint, cstr
from frappe.utils.background_jobs import get_redis_conn

if TYPE_CHECKING:
	from frappe.core.doctype.data_import.data_import import DataImport

# ---------------------------------------------------------------------------
# Data import
# ---------------------------------------------------------------------------


@public(group="Data Import/Export")
@frappe.whitelist()
def get_preview_from_template(
	data_import: str, import_file: str | None = None, google_sheets_url: str | None = None
) -> dict:
	"""Return a preview of the rows and columns of a data import's file.

	:param data_import: name of the Data Import
	:param import_file: file path of the uploaded import file
	:param google_sheets_url: URL of a Google Sheet to import instead of a file
	:return: The preview data (columns, rows, warnings).
	"""
	di: DataImport = frappe.get_doc("Data Import", data_import)
	di.check_permission("read")
	return di.get_preview_from_template(import_file, google_sheets_url)


@public(group="Data Import/Export")
@frappe.whitelist()
def form_start_import(data_import: str) -> bool:
	"""Start (enqueue) a data import.

	:param data_import: name of the Data Import
	:return: True if the import job was enqueued.
	"""
	di: DataImport = frappe.get_doc("Data Import", data_import)
	di.check_permission("write")
	return di.start_import()


@public(group="Data Import/Export")
@frappe.whitelist()
def stop_data_import(doc_name: str) -> dict:
	"""Stop a running data import job.

	:param doc_name: name of the Data Import
	:return: Dict with `status` and `message`.
	"""
	data_import = frappe.get_doc("Data Import", doc_name)
	data_import.check_permission("write")

	rq_job_id = f"{frappe.local.site}||data_import||{doc_name}"
	job_id = rq_job_id.replace(":", "|")  # patching the change in job id format (for timestamp part)
	try:
		send_stop_job_command(connection=get_redis_conn(), job_id=job_id)
	except InvalidJobOperation:
		frappe.msgprint(_("Job is not running."), title=_("Invalid Operation"))
	return {"status": "success", "message": "Job stopped successfully"}


@public(group="Data Import/Export")
@frappe.whitelist()
def download_template(
	doctype: str,
	export_fields: str | dict[str, list[str]] | None = None,
	export_records: str | None = None,
	export_filters: str | dict[str, Any] | list[list[Any]] | None = None,
	file_type: str = "CSV",
) -> None:
	"""Download an import template, optionally prefilled with existing records.

	:param doctype: Document Type
	:param export_fields: fields to export as dict, e.g. {'Sales Invoice': ['name', 'customer'], 'Sales Invoice Item': ['item_code']}
	:param export_records: one of 'all', 'by_filter', '5_records', 'blank_template'
	:param export_filters: filters for 'by_filter' exports
	:param file_type: file type to export into
	"""
	from frappe.core.doctype.data_import.exporter import Exporter

	frappe.has_permission(doctype, "read", throw=True)

	export_fields = frappe.parse_json(export_fields)
	export_filters = frappe.parse_json(export_filters)
	export_data = export_records != "blank_template"

	list_settings = frappe.parse_json(get_user_settings(doctype)).get("List", {})
	sort_by = list_settings.get("sort_by")
	sort_order = list_settings.get("sort_order")

	if sort_by and not frappe.get_meta(doctype).get_field(sort_by):
		sort_by = None

	if sort_order and sort_order.upper() not in ("ASC", "DESC"):
		sort_order = None

	order_by = f"{sort_by} {sort_order}" if sort_by and sort_order else None

	e = Exporter(
		doctype,
		export_fields=export_fields,
		export_data=export_data,
		export_filters=export_filters,
		file_type=file_type,
		export_page_length=5 if export_records == "5_records" else None,
		order_by=order_by,
	)
	e.build_response()


@public(group="Data Import/Export")
@frappe.whitelist()
def download_errored_template(data_import_name: str) -> None:
	"""Download the rows of a data import that failed to import.

	:param data_import_name: name of the Data Import
	"""
	data_import: DataImport = frappe.get_doc("Data Import", data_import_name)
	data_import.check_permission("read")
	data_import.export_errored_rows()


@public(group="Data Import/Export")
@frappe.whitelist()
def download_skipped_rows(data_import_name: str) -> None:
	"""Download the rows that were skipped during a data import.

	:param data_import_name: name of the Data Import
	"""
	data_import: DataImport = frappe.get_doc("Data Import", data_import_name)
	data_import.check_permission("read")
	data_import.export_skipped_rows()


@public(group="Data Import/Export")
@frappe.whitelist()
def download_import_log(data_import_name: str) -> None:
	"""Download the log of a data import as JSON.

	:param data_import_name: name of the Data Import
	"""
	data_import: DataImport = frappe.get_doc("Data Import", data_import_name)
	data_import.check_permission("read")
	data_import.download_import_log()


@public(group="Data Import/Export")
@frappe.whitelist()
def get_import_status(data_import_name: str) -> dict:
	"""Return the progress of a data import.

	:param data_import_name: name of the Data Import
	:return: Dict with status, total/success/failed counts and upsert breakdown.
	"""
	from frappe.core.doctype.data_import.importer import ACTION_INSERT, ACTION_UPDATE, UPSERT

	data_import: DataImport = frappe.get_doc("Data Import", data_import_name)
	data_import.check_permission("read")

	import_status = {
		"status": data_import.status,
		"total_records": data_import.payload_count,
	}
	is_upsert = data_import.import_type == UPSERT
	group_by = "success, import_action" if is_upsert else "success"
	log_fields = [{"COUNT": "*", "as": "count"}, "success"]
	if is_upsert:
		log_fields.append("import_action")

	for log in frappe.get_all(
		"Data Import Log",
		fields=log_fields,
		filters={"data_import": data_import_name},
		group_by=group_by,
	):
		count = log.get("count")
		if log.get("success"):
			import_status["success"] = import_status.get("success", 0) + count
			if is_upsert:
				if log.get("import_action") == ACTION_INSERT:
					import_status["inserted"] = count
				elif log.get("import_action") == ACTION_UPDATE:
					import_status["updated"] = count
		else:
			import_status["failed"] = count

	if is_upsert:
		import_status.setdefault("inserted", 0)
		import_status.setdefault("updated", 0)

	logged_total = import_status.get("success", 0) + import_status.get("failed", 0)
	if logged_total:
		import_status["total_records"] = logged_total

	return import_status


@public(group="Data Import/Export")
@frappe.whitelist(methods=["GET"])
@frappe.read_only()
def get_import_log_count(data_import: str) -> int:
	"""Return the number of log entries of a data import.

	:param data_import: name of the Data Import
	:return: Number of Data Import Log entries.
	"""
	doc = frappe.get_doc("Data Import", data_import)
	doc.check_permission("read")

	return frappe.db.count("Data Import Log", {"data_import": data_import})


@public(group="Data Import/Export")
@frappe.whitelist()
def get_import_logs(data_import: str) -> list:
	"""Return the log entries of a data import.

	:param data_import: name of the Data Import
	:return: The Data Import Log entries in import order.
	"""
	doc = frappe.get_doc("Data Import", data_import)
	doc.check_permission("read")

	return frappe.get_all(
		"Data Import Log",
		fields=["success", "docname", "messages", "exception", "row_indexes", "import_action"],
		filters={"data_import": data_import},
		limit_page_length=5000,
		order_by="log_index",
	)


@public(group="Data Import/Export")
@frappe.whitelist()
def export_data(
	doctype: str | list[str | dict[str, Any]] | None = None,
	parent_doctype: str | None = None,
	all_doctypes: bool | int | str = True,
	with_data: bool | int | str = False,
	select_columns: str | dict[str, list[str]] | None = None,
	file_type: str = "CSV",
	template: bool | str = False,
	filters: str | dict[str, Any] | list | None = None,
	export_without_column_meta: bool | str = False,
) -> None:
	"""Download records of a doctype (and its child tables) as CSV or Excel.

	:param doctype: DocType to export, or a list with parent and child doctypes
	:param parent_doctype: parent DocType when exporting a child table
	:param all_doctypes: include all child tables
	:param with_data: include existing records
	:param select_columns: columns to export as dict per doctype
	:param file_type: "CSV" or "Excel"
	:param template: export as an importable template
	:param filters: filter the exported records
	:param export_without_column_meta: omit the column metadata rows
	"""
	from frappe.core.doctype.data_export.exporter import DataExporter

	_doctype = doctype
	if isinstance(_doctype, list):
		_doctype = _doctype[0]
	make_access_log(
		doctype=_doctype,
		file_type=file_type,
		columns=select_columns,
		filters=filters,
		method=parent_doctype,
	)

	template_bool = template
	if isinstance(template, str):
		template_bool = template.lower() == "true"

	export_without_column_meta_bool = export_without_column_meta
	if isinstance(export_without_column_meta, str):
		export_without_column_meta_bool = export_without_column_meta.lower() == "true"

	exporter = DataExporter(
		doctype=doctype,
		parent_doctype=parent_doctype,
		all_doctypes=all_doctypes,
		with_data=with_data,
		select_columns=select_columns,
		file_type=file_type,
		template=template_bool,
		filters=filters,
		export_without_column_meta=export_without_column_meta_bool,
	)
	exporter.build_response()


@public(group="Data Import/Export")
@frappe.whitelist()
def send_csv_to_client(args: str | dict[str, Any]) -> None:
	"""Download the given data as a CSV file.

	:param args: dict/JSON with `data` (rows) and `filename`
	"""
	from frappe.utils.csvutils import to_csv

	args = frappe._dict(frappe.parse_json(args))

	frappe.response["result"] = cstr(to_csv(args.data))
	frappe.response["doctype"] = args.filename
	frappe.response["type"] = "csv"


@public(group="Data Import/Export")
@frappe.whitelist()
def export_customizations(
	module: str,
	doctype: str,
	sync_on_migrate: bool = False,
	with_permissions: bool = False,
	apply_module_export_filter: bool = False,
) -> str | None:
	"""Export Custom Fields and Property Setters of a doctype to the module's app folder.

	The exported customizations are synced on bench migrate. Only allowed in
	developer mode.

	:param module: module (app folder) to export into
	:param doctype: DocType whose customizations are exported
	:param sync_on_migrate: mark the export to be synced on migrate
	:param with_permissions: also export custom permission rules
	:param apply_module_export_filter: export only customizations belonging to `module`
	:return: Path of the exported file, if anything was exported.
	"""

	sync_on_migrate = cint(sync_on_migrate)
	with_permissions = cint(with_permissions)
	apply_module_export_filter = cint(apply_module_export_filter)

	cf_filters = {"dt": doctype}
	ps_filters = {"doc_type": doctype}

	if apply_module_export_filter:
		cf_filters["module"] = module
		ps_filters["module"] = module

	if not frappe.conf.developer_mode:
		frappe.throw(_("Only allowed to export customizations in developer mode"))

	custom = {
		"custom_fields": frappe.get_all(
			"Custom Field",
			fields="*",
			filters=cf_filters,
			order_by="name",
		),
		"property_setters": frappe.get_all(
			"Property Setter",
			fields="*",
			filters=ps_filters,
			order_by="name",
		),
		"custom_perms": [],
		"links": frappe.get_all("DocType Link", fields="*", filters={"parent": doctype}, order_by="name"),
		"doctype": doctype,
		"sync_on_migrate": sync_on_migrate,
	}

	if with_permissions:
		custom["custom_perms"] = frappe.get_all(
			"Custom DocPerm", fields="*", filters={"parent": doctype}, order_by="name"
		)

	# also update the custom fields and property setters for all child tables
	for d in frappe.get_meta(doctype).get_table_fields():
		export_customizations(
			module, d.options, sync_on_migrate, with_permissions, apply_module_export_filter
		)

	if custom["custom_fields"] or custom["property_setters"] or custom["custom_perms"]:
		folder_path = os.path.join(get_module_path(module), "custom")
		if not os.path.exists(folder_path):
			os.makedirs(folder_path)

		path = os.path.join(folder_path, scrub(doctype) + ".json")
		with open(path, "w") as f:
			f.write(frappe.as_json(custom))

		frappe.msgprint(_("Customizations for <b>{0}</b> exported to:<br>{1}").format(doctype, path))
		return path
