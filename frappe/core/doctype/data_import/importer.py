# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import os
import re
import timeit
from datetime import date, datetime, time

import frappe
from frappe import _
from frappe.core.doctype.version.version import get_diff
from frappe.model import no_value_fields
from frappe.utils import cint, cstr, duration_to_seconds, flt, update_progress_bar
from frappe.utils.csvutils import get_csv_content_from_google_sheets, read_csv_content
from frappe.utils.data import escape_html
from frappe.utils.xlsxutils import (
	read_xls_file_from_attached_file,
	read_xlsx_file_from_attached_file,
)

INVALID_VALUES = ("", None)
MAX_ROWS_IN_PREVIEW = 10
INSERT = "Insert New Records"
UPDATE = "Update Existing Records"
UPSERT = "Insert or Update Records"
ACTION_INSERT = "Insert"
ACTION_UPDATE = "Update"
DURATION_PATTERN = re.compile(r"^(?:(\d+d)?((^|\s)\d+h)?((^|\s)\d+m)?((^|\s)\d+s)?)$")


def _get_fixed_csv_delimiter(custom_delimiters, delimiter_options) -> str | None:
	if not cint(custom_delimiters) or not delimiter_options:
		return None
	options = delimiter_options.strip()
	return options if len(options) == 1 else None


class Importer:
	def __init__(
		self, doctype, data_import=None, file_path=None, import_type=None, console=False, use_sniffer=False
	):
		self.doctype = doctype
		self.console = console
		self.use_sniffer = use_sniffer

		self.data_import = data_import
		if not self.data_import:
			self.data_import = frappe.get_doc(doctype="Data Import")
			if import_type:
				self.data_import.import_type = import_type

		self.template_options = frappe.parse_json(self.data_import.template_options or "{}")
		self.import_type = self.data_import.import_type

		self.import_file = ImportFile(
			doctype,
			file_path or data_import.google_sheets_url or data_import.import_file,
			self.template_options,
			self.import_type,
			data_import_name=self.data_import.name,
			reference_doctype=doctype,
			console=self.console,
			use_sniffer=self.use_sniffer,
			custom_delimiters=data_import.custom_delimiters,
			delimiter_options=data_import.delimiter_options,
		)

	def get_data_for_import_preview(self):
		out = self.import_file.get_data_for_import_preview()

		out.import_log = frappe.get_all(
			"Data Import Log",
			fields=["row_indexes", "success"],
			filters={"data_import": self.data_import.name},
			order_by="log_index",
			limit=10,
		)

		return out

	def before_import(self):
		# set user lang for translations
		frappe.cache.hdel("lang", frappe.session.user)
		frappe.set_user_lang(frappe.session.user)

		# set flags
		frappe.flags.in_import = True
		frappe.flags.mute_emails = self.data_import.mute_emails

		self.data_import.db_set("template_warnings", "")
		self._inserted_name_map = {}
		meta = frappe.get_meta(self.doctype)
		self._tree_parent_field = meta.nsm_parent_field if meta.is_nested_set() else None
		header = getattr(self.import_file, "header", None)
		self._tree_alias_field = getattr(header, "tree_alias_field", None)
		self._id_fieldname = getattr(header, "id_fieldname", None) or get_id_field(self.doctype).fieldname
		self._uses_tree_aliases = bool(self._tree_alias_field)
		self._prime_inserted_name_map_from_db()

	def _prime_inserted_name_map_from_db(self):
		"""Pre-fetch DB name mappings for parent links not defined as rows in this file."""
		if not self._tree_parent_field:
			return

		parent_column = next(
			(
				col
				for col in self.import_file.header.columns
				if col.df and col.df.fieldname == self._tree_parent_field and not col.skip_import
			),
			None,
		)
		if not parent_column:
			return

		parent_values = {cstr(v).strip() for v in parent_column.column_values if v not in INVALID_VALUES}
		header = self.import_file.header
		in_file_refs = (header.import_ids or set()) | (header.import_aliases or set())
		if self.import_type == UPDATE:
			refs_to_fetch = parent_values
		else:
			refs_to_fetch = parent_values - in_file_refs
		if not refs_to_fetch:
			return

		self._inserted_name_map.update(
			_build_db_tree_parent_name_map(self.doctype, refs_to_fetch, self._tree_alias_field)
		)

	def import_data(self):
		self.before_import()

		# parse docs from rows
		payloads = self.import_file.get_payloads_for_import()
		if self.data_import.name:
			self.data_import.db_set("payload_count", len(payloads))

		# dont import if there are non-ignorable warnings
		from frappe.core.doctype.data_import.value_mapping import (
			get_blocking_warnings,
			get_skipped_row_numbers,
		)

		warnings = get_blocking_warnings(
			self.import_file.get_all_warnings(), self.import_file, self.data_import
		)

		if warnings:
			if self.console:
				self.print_grouped_warnings(warnings)
			else:
				self.data_import.db_set("template_warnings", json.dumps(warnings))
				frappe.publish_realtime(
					"data_import_blocked",
					{"data_import": self.data_import.name},
					user=frappe.session.user,
				)
			return

		# setup import log
		# Only use import log for retry/resume when Data Import is persisted in DB.
		# For bench data-import (CLI), the doc is never inserted, so we must not reuse logs
		import_log = []
		if self.data_import.name and frappe.db.exists("Data Import", self.data_import.name):
			import_log = (
				frappe.get_all(
					"Data Import Log",
					fields=["row_indexes", "success", "log_index"],
					filters={"data_import": self.data_import.name},
					order_by="log_index",
				)
				or []
			)

		log_index = 0

		# Do not remove rows in case of retry after an error or pending data import
		if (
			self.data_import.status in ("Partial Success", "Error")
			and len(import_log) >= self.data_import.payload_count
		):
			# remove previous failures from import log only in case of retry after partial success
			import_log = [log for log in import_log if log.get("success")]
			frappe.db.delete("Data Import Log", {"success": 0, "data_import": self.data_import.name})

		# get successfully imported rows
		imported_rows = set()
		for log in import_log:
			log = frappe._dict(log)
			if log.success or len(import_log) < self.data_import.payload_count:
				imported_rows.update(json.loads(log.row_indexes))

			log_index = log.log_index

		# start import
		total_payload_count = len(payloads)
		skipped_rows = get_skipped_row_numbers(self.data_import)
		skipped_payload_count = 0
		batch_size = frappe.conf.data_import_batch_size or 1000

		for batch_index, batched_payloads in enumerate(frappe.utils.create_batch(payloads, batch_size)):
			for i, payload in enumerate(batched_payloads):
				doc = payload.doc
				row_indexes = [row.row_number for row in payload.rows]
				current_index = (i + 1) + (batch_index * batch_size)
				row_set = set(row_indexes)

				if row_set.intersection(skipped_rows):
					skipped_payload_count += 1
					self._publish_skip_progress(current_index, total_payload_count)
					continue

				if row_set.intersection(imported_rows):
					print("Skipping imported rows", row_indexes)
					self._publish_skip_progress(current_index, total_payload_count)
					continue

				try:
					start = timeit.default_timer()
					doc, import_action = self.process_doc(doc)
					processing_time = timeit.default_timer() - start
					eta = self.get_eta(current_index, total_payload_count, processing_time)

					if self.console:
						update_progress_bar(
							f"Importing {self.doctype}: {total_payload_count} records",
							current_index - 1,
							total_payload_count,
						)
					elif total_payload_count > 5:
						frappe.publish_realtime(
							"data_import_progress",
							{
								"current": current_index,
								"total": total_payload_count,
								"docname": doc.name,
								"data_import": self.data_import.name,
								"success": True,
								"row_indexes": row_indexes,
								"eta": eta,
							},
							user=frappe.session.user,
						)

					log_details = {
						"success": True,
						"docname": doc.name,
						"row_indexes": row_indexes,
					}
					if self.import_type == UPSERT:
						log_details["import_action"] = import_action

					create_import_log(self.data_import.name, log_index, log_details)

					log_index += 1

					if self.data_import.status != "Partial Success":
						self.data_import.db_set("status", "Partial Success")

					# commit after every successful import
					frappe.db.commit()

				except Exception:
					messages = frappe.local.message_log
					frappe.clear_messages()

					# rollback if exception
					frappe.db.rollback()

					create_import_log(
						self.data_import.name,
						log_index,
						{
							"success": False,
							"exception": frappe.get_traceback(),
							"messages": messages,
							"row_indexes": row_indexes,
						},
					)

					log_index += 1

		# Logs are db inserted directly so will have to be fetched again
		import_log = (
			frappe.get_all(
				"Data Import Log",
				fields=["row_indexes", "success", "log_index"],
				filters={"data_import": self.data_import.name},
				order_by="log_index",
			)
			or []
		)

		# set status
		successes = []
		failures = []
		for log in import_log:
			if log.get("success"):
				successes.append(log)
			else:
				failures.append(log)
		attempted_payload_count = total_payload_count - skipped_payload_count
		if attempted_payload_count == 0 or len(successes) == attempted_payload_count:
			status = "Success"
		elif len(failures) >= attempted_payload_count and len(successes) == 0:
			status = "Error"
		elif len(failures) > 0 and len(successes) > 0:
			status = "Partial Success"
		else:
			status = "Pending"

		if self.console:
			self.print_import_log(import_log)
		else:
			self.data_import.db_set("status", status)

		self.after_import()

		return import_log

	def after_import(self):
		frappe.flags.in_import = False
		frappe.flags.mute_emails = False

	def _publish_skip_progress(self, current_index, total_payload_count):
		if total_payload_count > 5:
			frappe.publish_realtime(
				"data_import_progress",
				{
					"current": current_index,
					"total": total_payload_count,
					"skipping": True,
					"data_import": self.data_import.name,
				},
				user=frappe.session.user,
			)

	def process_doc(self, doc):
		"""Process one import payload; returns ``(document, import_action)``."""
		if self.import_type == INSERT:
			return self.insert_record(doc), None
		if self.import_type == UPDATE:
			return self.update_record(doc), None
		return self.upsert_record(doc)

	def upsert_record(self, doc):
		"""Update the record when it exists, otherwise insert it."""
		id_field = get_id_field(self.doctype)
		id_value = doc.get(id_field.fieldname)
		if id_value and frappe.db.exists(self.doctype, id_value):
			result = self.update_record(doc, raise_if_no_changes=False)
			if self._uses_tree_aliases:
				self._register_inserted_name(doc, result)
			return result, ACTION_UPDATE
		return self.insert_record(doc), ACTION_INSERT

	def insert_record(self, doc):
		meta = frappe.get_meta(self.doctype)
		new_doc = frappe.new_doc(self.doctype)
		new_doc.update(doc)

		if not doc.name and (meta.autoname or "").lower() != "prompt":
			# name can only be set directly if autoname is prompt
			new_doc.set("name", None)

		if self._uses_tree_aliases and self._tree_parent_field:
			self._resolve_tree_parent_link(doc)
			new_doc.set(self._tree_parent_field, doc.get(self._tree_parent_field))

		new_doc.flags.updater_reference = {
			"doctype": self.data_import.doctype,
			"docname": self.data_import.name,
			"label": _("via Data Import"),
		}

		new_doc.insert()
		if self._uses_tree_aliases:
			self._register_inserted_name(doc, new_doc)
		if meta.is_submittable and self.data_import.submit_after_import:
			new_doc.submit()
		return new_doc

	def _resolve_tree_parent_link(self, doc):
		"""Swap parent link aliases from the file with document names (in-file or DB)."""
		parent = doc.get(self._tree_parent_field)
		if parent in INVALID_VALUES:
			return

		parent = cstr(parent).strip()
		resolved = self._inserted_name_map.get(parent)
		if resolved:
			doc[self._tree_parent_field] = resolved

	def _register_inserted_name(self, doc, new_doc):
		"""Track alias/id values from the file against the generated document name."""
		if self._tree_alias_field:
			alias = new_doc.get(self._tree_alias_field) or doc.get(self._tree_alias_field)
			if alias not in INVALID_VALUES:
				self._inserted_name_map[cstr(alias).strip()] = new_doc.name

		id_value = doc.get(self._id_fieldname)
		if id_value not in INVALID_VALUES:
			self._inserted_name_map[cstr(id_value).strip()] = new_doc.name

	def update_record(self, doc, raise_if_no_changes=True):
		id_field = get_id_field(self.doctype)
		updated_doc = frappe.get_doc(self.doctype, doc.get(id_field.fieldname))
		existing_doc = frappe.copy_doc(updated_doc)

		updated_doc.update(doc)

		if self._uses_tree_aliases and self._tree_parent_field:
			self._resolve_tree_parent_link(doc)
			updated_doc.set(self._tree_parent_field, doc.get(self._tree_parent_field))

		if get_diff(existing_doc, updated_doc):
			# update doc if there are changes
			updated_doc.flags.updater_reference = {
				"doctype": self.data_import.doctype,
				"docname": self.data_import.name,
				"label": _("via Data Import"),
			}
			updated_doc.save()
			return updated_doc

		if raise_if_no_changes:
			frappe.throw(_("No changes to update"))
		return updated_doc

	def get_eta(self, current, total, processing_time):
		self.last_eta = getattr(self, "last_eta", 0)
		remaining = total - current
		eta = processing_time * remaining
		if not self.last_eta or eta < self.last_eta:
			self.last_eta = eta
		return self.last_eta

	def export_errored_rows(self):
		from frappe.utils.csvutils import build_csv_response

		if not self.data_import:
			return

		import_log = (
			frappe.get_all(
				"Data Import Log",
				fields=["row_indexes", "success"],
				filters={"data_import": self.data_import.name},
				order_by="log_index",
			)
			or []
		)

		failures = [log for log in import_log if not log.get("success")]
		row_indexes = []
		for f in failures:
			row_indexes.extend(json.loads(f.get("row_indexes", [])))

		# de duplicate
		row_indexes = list(set(row_indexes))
		row_indexes.sort()

		header_row = [col.header_title for col in self.import_file.columns]
		rows = [header_row]
		rows += [row.data for row in self.import_file.data if row.row_number in row_indexes]

		build_csv_response(rows, _(self.doctype))

	def export_skipped_rows(self):
		from frappe.utils.csvutils import build_csv_response

		if not self.data_import or not self.data_import.skipped_rows:
			return

		header_row = [col.header_title for col in self.import_file.columns]
		rows = [header_row]
		for skipped in sorted(self.data_import.skipped_rows, key=lambda r: r.row_number):
			rows.append(frappe.parse_json(skipped.row_data))

		build_csv_response(rows, _(self.doctype))

	def export_import_log(self):
		from frappe.utils.csvutils import build_csv_response

		if not self.data_import:
			return

		import_log = frappe.get_all(
			"Data Import Log",
			fields=["row_indexes", "success", "messages", "exception", "docname"],
			filters={"data_import": self.data_import.name},
			order_by="log_index",
		)

		header_row = ["Row Numbers", "Status", "Message", "Exception"]

		rows = [header_row]

		for log in import_log:
			row_number = json.loads(log.get("row_indexes"))[0]
			status = "Success" if log.get("success") else "Failure"
			message = (
				"Successfully Imported {}".format(log.get("docname"))
				if log.get("success")
				else log.get("messages")
			)
			exception = frappe.utils.cstr(log.get("exception", ""))
			rows += [[row_number, status, message, exception]]

		build_csv_response(rows, self.doctype)

	def print_import_log(self, import_log):
		failed_records = [log for log in import_log if not log.success]
		successful_records = [log for log in import_log if log.success]

		if successful_records:
			print()
			print(f"Successfully imported {len(successful_records)} records out of {len(import_log)}")

		if failed_records:
			print(f"Failed to import {len(failed_records)} records")
			file_name = f"{self.doctype}_import_on_{frappe.utils.now()}.txt"
			print("Check {} for errors".format(os.path.join("sites", file_name)))
			text = ""
			for w in failed_records:
				text += "Row Indexes: {}\n".format(str(w.get("row_indexes", [])))
				text += "Messages:\n{}\n".format("\n".join(w.get("messages", [])))
				text += "Traceback:\n{}\n\n".format(w.get("exception"))

			with open(file_name, "w") as f:
				f.write(text)

	def print_grouped_warnings(self, warnings):
		warnings_by_row = {}
		other_warnings = []
		for w in warnings:
			if w.get("row"):
				warnings_by_row.setdefault(w.get("row"), []).append(w)
			else:
				other_warnings.append(w)

		for row_number, warnings in warnings_by_row.items():
			print(f"Row {row_number}")
			for w in warnings:
				print(w.get("message"))

		for w in other_warnings:
			print(w.get("message"))


class ImportFile:
	def __init__(
		self,
		doctype,
		file,
		template_options=None,
		import_type=None,
		*,
		data_import_name=None,
		reference_doctype=None,
		console=False,
		use_sniffer=False,
		custom_delimiters=False,
		delimiter_options=None,
	):
		self.doctype = doctype
		self.reference_doctype = reference_doctype or doctype
		self.template_options = template_options or frappe._dict(column_to_field_map=frappe._dict())
		self.column_to_field_map = self.template_options.column_to_field_map
		self.import_type = import_type
		from frappe.core.doctype.data_import.value_mapping import build_lookup_for_data_import

		self.value_lookup = build_lookup_for_data_import(data_import_name, self.reference_doctype)
		self.warnings = []
		self.console = console
		self.use_sniffer = use_sniffer
		self.custom_delimiters = custom_delimiters
		self.delimiter_options = delimiter_options

		self.file_doc = self.file_path = self.google_sheets_url = None
		if isinstance(file, str):
			if frappe.db.exists("File", {"file_url": file}):
				self.file_doc = frappe.get_doc("File", {"file_url": file})
			elif "docs.google.com/spreadsheets" in file:
				self.google_sheets_url = file
			elif os.path.exists(file):
				self.file_path = file

		if not self.file_doc and not self.file_path and not self.google_sheets_url:
			frappe.throw(_("Invalid template file for import"))

		self.raw_data = self.get_data_from_template_file()
		self.parse_data_from_template()

	def get_data_from_template_file(self):
		content = None
		extension = None

		if self.file_doc:
			parts = self.file_doc.get_extension()
			extension = parts[1]
			content = self.file_doc.get_content()
			extension = extension.lstrip(".")

		elif self.file_path:
			content, extension = self.read_file(self.file_path)

		elif self.google_sheets_url:
			content = get_csv_content_from_google_sheets(self.google_sheets_url)
			extension = "csv"

		if not content:
			frappe.throw(_("Invalid or corrupted content for import"))

		if not extension:
			extension = "csv"

		if content:
			return self.read_content(content, extension)

	def parse_data_from_template(self):
		header = None
		data = []

		for i, row in enumerate(self.raw_data):
			if all(v in INVALID_VALUES for v in row):
				# empty row
				continue

			if not header:
				header = Header(
					i,
					row,
					self.doctype,
					self.raw_data[i + 1 :],
					self.column_to_field_map,
					self.value_lookup,
					self.reference_doctype,
				)
			else:
				row_obj = Row(i, row, self.doctype, header, self.import_type)
				data.append(row_obj)

		self.header = header
		self.columns = self.header.columns
		self.data = data
		meta = frappe.get_meta(self.doctype)
		self.header.id_fieldname = _get_id_fieldname_from_meta(meta)
		self.header.tree_alias_field = _get_tree_alias_field_from_meta(meta)
		self.header.import_ids, self.header.import_aliases = _build_import_reference_sets(
			self, self.header.id_fieldname, self.header.tree_alias_field
		)
		self.header.import_refs = self.header.import_ids | self.header.import_aliases
		self._refresh_self_referential_link_validation()
		self.__dict__.pop("_tree_preview_cache", None)

		if len(data) < 1:
			frappe.throw(
				_("Import template should contain a Header and atleast one row."),
				title=_("Template Error"),
			)

	def _refresh_self_referential_link_validation(self):
		"""Re-validate parent Link columns after IDs from the file are known."""
		from frappe.core.doctype.data_import.value_mapping import warn_invalid_link_select_values

		alias_field = self.header.tree_alias_field
		if alias_field:
			link_values = set()
			for col in self.header.columns:
				if not col.df or col.skip_import or col.df.fieldtype != "Link":
					continue
				if col.df.options != self.doctype:
					continue
				for value in col.column_values:
					if value not in INVALID_VALUES:
						link_values.add(cstr(value).strip())
			if link_values:
				self.header.import_refs |= _get_existing_tree_parent_refs(
					self.doctype, link_values, alias_field
				)

		for col in self.header.columns:
			if not col.df or col.skip_import or col.df.fieldtype != "Link":
				continue
			if col.df.options != self.doctype:
				continue

			col.import_refs = self.header.import_refs
			col.invalid_value_items = None
			col.warnings = [w for w in col.warnings if w.get("type") != "value_mapping"]
			warn_invalid_link_select_values(col)

	def get_data_for_import_preview(self):
		"""Adds a serial number column as the first column"""

		columns = [frappe._dict({"header_title": _("Sr. No"), "skip_import": True})]
		columns += [col.as_dict() for col in self.columns]
		for col in columns:
			# only pick useful fields in docfields to minimise the payload
			if col.df:
				col.df = {
					"fieldtype": col.df.fieldtype,
					"fieldname": col.df.fieldname,
					"label": col.df.label,
					"options": col.df.options,
					"parent": col.df.parent,
					"reqd": col.df.reqd,
					"default": col.df.default,
					"read_only": col.df.read_only,
				}

		data = [[row.row_number, *row.as_list()] for row in self.data]

		tree_preview = self.get_tree_preview()

		out = frappe._dict()
		out.data = data
		out.columns = columns
		out.warnings = self.get_warnings()
		if tree_preview:
			out.tree_preview = tree_preview
			out.warnings += tree_preview.tree_warnings
		total_number_of_rows = len(out.data)
		out.total_number_of_rows = total_number_of_rows
		if total_number_of_rows > MAX_ROWS_IN_PREVIEW:
			out.data = out.data[:MAX_ROWS_IN_PREVIEW]
			out.max_rows_exceeded = True
			out.max_rows_in_preview = MAX_ROWS_IN_PREVIEW
		from frappe.core.doctype.data_import.value_mapping import get_mapping_hints

		out.mapping_hints = get_mapping_hints(self, self.reference_doctype, self.value_lookup)

		return out

	def get_payloads_for_import(self):
		payloads = []
		# make a copy
		data = list(self.data)
		while data:
			prev_len = len(data)
			doc, rows, data = self.parse_next_row_for_import(data)
			assert len(data) < prev_len, "each iteration must consume at least one row to terminate"
			payloads.append(frappe._dict(doc=doc, rows=rows))
		return sort_tree_payloads(payloads, self.doctype, self.import_type)

	def parse_next_row_for_import(self, data):
		"""
		Parse rows that make up a doc. A doc maybe built from a single row or multiple rows.
		Return the doc, rows, and data without the rows.
		"""
		doctypes = self.header.doctypes

		# first row is included by default
		first_row = data[0]
		rows = [first_row]

		# if there are child doctypes, find the subsequent rows
		if len(doctypes) > 1:
			# subsequent rows that have blank values in parent columns
			# are considered as child rows
			parent_column_indexes = self.header.get_column_indexes(self.doctype)

			data_without_first_row = data[1:]
			for row in data_without_first_row:
				row_values = row.get_values(parent_column_indexes)
				# if the row is blank, it's a child row doc
				if all(v in INVALID_VALUES for v in row_values):
					rows.append(row)
					continue
				# if we encounter a row which has values in parent columns,
				# then it is the next doc
				break

		parent_doc = None
		for row in rows:
			for doctype, table_df in doctypes:
				if doctype == self.doctype and not parent_doc:
					parent_doc = row.parse_doc(doctype)

				if doctype != self.doctype and table_df:
					child_doc = row.parse_doc(doctype, parent_doc, table_df)
					if child_doc is None:
						continue
					parent_doc[table_df.fieldname] = parent_doc.get(table_df.fieldname, [])
					parent_doc[table_df.fieldname].append(child_doc)

		doc = parent_doc

		return doc, rows, data[len(rows) :]

	def get_warnings(self):
		warnings = []

		# ImportFile warnings
		warnings += self.warnings

		# Column warnings
		for col in self.header.columns:
			warnings += col.warnings

		# Row warnings
		for row in self.data:
			warnings += row.warnings

		return warnings

	def get_all_warnings(self):
		"""Row/column warnings plus tree-structure warnings used to block import."""
		warnings = self.get_warnings()
		tree_preview = self.get_tree_preview()
		if tree_preview:
			warnings += tree_preview.tree_warnings
		return warnings

	def get_tree_preview(self):
		"""Cached tree preview; invalidated when parse_data_from_template re-parses the file."""
		if "_tree_preview_cache" not in self.__dict__:
			self._tree_preview_cache = build_tree_preview(self)
		return self._tree_preview_cache

	######

	def read_file(self, file_path: str):
		extn = os.path.splitext(file_path)[1][1:]

		file_content = None

		if self.console:
			file_content = frappe.read_file(file_path, True)
			return file_content, extn

		file_name = frappe.db.get_value("File", {"file_url": file_path})
		if file_name:
			file = frappe.get_doc("File", file_name)
			file_content = file.get_content()

		return file_content, extn

	def read_content(self, content, extension):
		error_title = _("Template Error")
		if extension not in ("csv", "xlsx", "xls"):
			frappe.throw(_("Import template should be of type .csv, .xlsx or .xls"), title=error_title)

		if extension == "csv":
			data = read_csv_content(
				content,
				use_sniffer=self.use_sniffer,
				delimiter=_get_fixed_csv_delimiter(self.custom_delimiters, self.delimiter_options),
			)
		elif extension == "xlsx":
			data = read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
		elif extension == "xls":
			data = read_xls_file_from_attached_file(content)
		return data


def get_value_row_map(column_values, value_row_numbers):
	"""Map each distinct cell value to sorted 1-based sheet row numbers (first-seen order)."""
	value_rows = {}
	for value, row_number in zip(column_values, value_row_numbers, strict=False):
		if value in INVALID_VALUES:
			continue
		key = cstr(value)
		value_rows.setdefault(key, [])
		if row_number not in value_rows[key]:
			value_rows[key].append(row_number)
	for rows in value_rows.values():
		rows.sort()
	return value_rows


def format_row_numbers_for_warning(rows: list, max_shown: int = 6) -> str:
	"""Compact row list for warnings: first ``max_shown`` rows, then …, then the last row."""
	if len(rows) <= max_shown:
		return ", ".join(str(r) for r in rows)
	return f"{', '.join(str(r) for r in rows[:max_shown])}, ... {rows[-1]}"


def _get_id_fieldname_from_meta(meta) -> str:
	if meta.autoname and meta.autoname.startswith("field:"):
		return meta.autoname[6:]
	return "name"


def _get_tree_alias_field_from_meta(meta) -> str | None:
	"""Title field for parent-by-alias tree imports; None when names come from a ``field:`` autoname."""
	if (
		not meta.is_nested_set()
		or (meta.autoname and meta.autoname.startswith("field:"))
		or not meta.title_field
	):
		return None

	if meta.title_field == _get_id_fieldname_from_meta(meta):
		return None

	return meta.title_field


def get_tree_alias_fieldname(doctype):
	"""Title field for parent-by-alias tree imports; None when names come from a ``field:`` autoname."""
	return _get_tree_alias_field_from_meta(frappe.get_meta(doctype))


def uses_tree_alias_references(doctype):
	"""Whether tree parent links may use title-field values instead of generated names."""
	return bool(get_tree_alias_fieldname(doctype))


def _get_tree_node_key(doc, id_fieldname, alias_field=None):
	"""Stable row identity for tree sorting/preview: explicit id, else title-field alias."""
	node_id = doc.get(id_fieldname)
	if node_id not in INVALID_VALUES:
		return cstr(node_id).strip()

	if alias_field:
		alias = doc.get(alias_field)
		if alias not in INVALID_VALUES:
			return cstr(alias).strip()

	return None


def _is_same_file_tree_reference(value, header) -> bool:
	"""Whether a self-referential link value exists elsewhere in the import file."""
	import_refs = getattr(header, "import_refs", None)
	return bool(import_refs and cstr(value).strip() in import_refs)


def _get_import_column_index(columns, fieldname):
	column = next(
		(col for col in columns if col.df and col.df.fieldname == fieldname and not col.skip_import),
		None,
	)
	return column.index if column else None


def _build_import_reference_sets(
	import_file: "ImportFile", id_fieldname: str, alias_field: str | None
) -> tuple[set[str], set[str]]:
	"""Collect id and alias values from the template in a single pass."""
	columns = import_file.header.columns
	id_index = _get_import_column_index(columns, id_fieldname)
	alias_index = _get_import_column_index(columns, alias_field) if alias_field else None

	if id_index is None and alias_index is None:
		return set(), set()

	ids = set()
	aliases = set()
	for row in import_file.data:
		if id_index is not None:
			value = row.get(id_index)
			if value not in INVALID_VALUES:
				ids.add(cstr(value).strip())
		if alias_index is not None:
			value = row.get(alias_index)
			if value not in INVALID_VALUES:
				aliases.add(cstr(value).strip())

	return ids, aliases


def _get_existing_tree_parent_refs(doctype: str, parent_refs: set, alias_field: str | None) -> set:
	"""Return parent values from the file that already exist in the DB (by name or alias)."""
	parent_list = list(parent_refs)
	if not parent_list:
		return set()

	limit = len(parent_list)
	existing = set(
		frappe.get_all(
			doctype,
			filters={"name": ("in", parent_list)},
			pluck="name",
			limit=limit,
		)
	)
	if alias_field:
		existing |= set(
			frappe.get_all(
				doctype,
				filters={alias_field: ("in", parent_list)},
				pluck=alias_field,
				limit=limit,
			)
		)
	return existing


def _build_db_tree_parent_name_map(doctype: str, parent_refs: set, alias_field: str | None) -> dict:
	"""Map parent link values from the file to existing document names."""
	parent_list = list(parent_refs)
	if not parent_list:
		return {}

	name_map = {}
	limit = len(parent_list)
	for name in frappe.get_all(
		doctype,
		filters={"name": ("in", parent_list)},
		pluck="name",
		limit=limit,
	):
		name_map[name] = name

	if alias_field:
		for row in frappe.get_all(
			doctype,
			filters={alias_field: ("in", parent_list)},
			fields=["name", alias_field],
			limit=limit,
		):
			name_map[cstr(row[alias_field]).strip()] = row.name

	return name_map


def build_tree_preview(import_file: "ImportFile") -> frappe._dict | None:
	"""Build a flat, depth-ordered node list for tree DocType import preview."""
	meta = frappe.get_meta(import_file.doctype)
	if not meta.is_nested_set():
		return None

	parent_field = meta.nsm_parent_field or f"parent_{frappe.scrub(import_file.doctype)}"
	id_fieldname = getattr(import_file.header, "id_fieldname", None) or _get_id_fieldname_from_meta(meta)
	alias_field = getattr(import_file.header, "tree_alias_field", None)
	label_fieldname = meta.title_field or id_fieldname
	is_group_field = "is_group" if meta.has_field("is_group") else None
	parent_column = next(
		(
			col
			for col in import_file.header.columns
			if col.df and col.df.fieldname == parent_field and not col.skip_import
		),
		None,
	)

	nodes = []
	id_to_rows: dict[str, list[int]] = {}

	for row in import_file.data:
		doc = row.parse_doc(import_file.doctype)
		if not doc:
			continue

		node_id = _get_tree_node_key(doc, id_fieldname, alias_field)
		if not node_id:
			continue

		parent = _get_tree_parent_value(row, parent_column, doc, parent_field)

		label = doc.get(label_fieldname) or node_id
		label = cstr(label).strip() if label not in INVALID_VALUES else node_id

		is_group = cint(doc.get(is_group_field)) if is_group_field else 0

		id_to_rows.setdefault(node_id, []).append(row.row_number)
		nodes.append(
			frappe._dict(
				id=node_id,
				label=label,
				parent=parent,
				row_number=row.row_number,
				is_group=is_group,
				warnings=[],
			)
		)

	tree_warnings = []
	nodes_by_id = {node.id: node for node in nodes}
	duplicate_messages = {}

	for node_id, row_numbers in id_to_rows.items():
		if len(row_numbers) > 1:
			message = _("Duplicate ID {0} in rows {1}").format(
				frappe.bold(node_id), format_row_numbers_for_warning(row_numbers)
			)
			tree_warnings.append({"message": message})
			duplicate_messages[node_id] = message

	for node in nodes:
		if message := duplicate_messages.get(node.id):
			node.warnings.append(message)

	for node in nodes:
		parent_id = node.parent
		if not parent_id or parent_id not in nodes_by_id:
			continue
		if _has_parent_cycle(node.id, nodes_by_id):
			message = _("Circular parent reference for {0}").format(frappe.bold(node.id))
			node.warnings.append(message)
			if not any(w.get("message") == message for w in tree_warnings):
				tree_warnings.append({"row": node.row_number, "message": message})

	parents_needing_db_check = {
		node.parent
		for node in nodes
		if node.parent
		and node.parent not in nodes_by_id
		and not _is_same_file_tree_reference(node.parent, import_file.header)
	}
	existing_parents_in_db = _get_existing_tree_parent_refs(
		import_file.doctype, parents_needing_db_check, alias_field
	)

	allow_any_existing_parent = import_file.import_type == UPDATE
	for node in nodes:
		parent_id = node.parent
		if not parent_id or parent_id in nodes_by_id:
			continue
		if _is_same_file_tree_reference(parent_id, import_file.header):
			continue
		if allow_any_existing_parent or parent_id in existing_parents_in_db:
			continue

		message = _("Parent {0} not found in file").format(frappe.bold(parent_id))
		node.warnings.append(message)
		tree_warnings.append({"row": node.row_number, "message": message})

	if is_group_field:
		_append_non_group_parent_warnings(nodes, nodes_by_id, tree_warnings, is_group_field)

	display_nodes = _order_tree_preview_nodes(nodes)

	return frappe._dict(
		nodes=display_nodes,
		tree_warnings=tree_warnings,
		total_nodes=len(nodes),
	)


def _append_non_group_parent_warnings(
	nodes: list, nodes_by_id: dict, tree_warnings: list, is_group_field: str
):
	"""Warn when a node is used as a parent in the file but Is Group is unchecked."""
	children_by_parent: dict[str, list] = {}
	for node in nodes:
		if node.parent and node.parent in nodes_by_id:
			children_by_parent.setdefault(node.parent, []).append(node)

	for parent_id, _children in children_by_parent.items():
		parent = nodes_by_id.get(parent_id)
		if not parent or parent.is_group:
			continue

		display_name = parent.label or parent.id
		message = _("{0} has children but Is Group is 0 — parent must be a group node").format(
			frappe.bold(display_name)
		)
		if message not in parent.warnings:
			parent.warnings.append(message)
		if not any(w.get("message") == message for w in tree_warnings):
			tree_warnings.append({"row": parent.row_number, "message": message})


def _get_tree_parent_value(row: "Row", parent_column, doc: frappe._dict, parent_field: str):
	"""Parent link values are often unset in preview because targets are not in DB yet."""
	if parent_column:
		value = row.get(parent_column.index)
		if value not in INVALID_VALUES:
			return cstr(value).strip()

	value = doc.get(parent_field)
	return cstr(value).strip() if value not in INVALID_VALUES else None


def _has_parent_cycle(node_id: str, nodes_by_id: dict) -> bool:
	seen = set()
	current = node_id
	while current:
		if current in seen:
			return True
		seen.add(current)
		node = nodes_by_id.get(current)
		if not node or not node.parent or node.parent not in nodes_by_id:
			return False
		current = node.parent
	return False


def sort_tree_payloads(payloads: list, doctype: str, import_type: str | None) -> list:
	"""Return payloads in parent-before-child order for nested-set inserts."""
	meta = frappe.get_meta(doctype)
	if import_type not in (INSERT, UPSERT) or not meta.is_nested_set() or not payloads:
		return payloads

	parent_field = meta.nsm_parent_field or f"parent_{frappe.scrub(doctype)}"
	id_fieldname = _get_id_fieldname_from_meta(meta)
	alias_field = _get_tree_alias_field_from_meta(meta)

	payload_keys = []
	for payload in payloads:
		node_id = _get_tree_node_key(payload.doc, id_fieldname, alias_field)
		parent = payload.doc.get(parent_field)
		parent = cstr(parent).strip() if parent not in INVALID_VALUES else None
		payload_keys.append((payload, node_id, parent))

	payload_by_id = {node_id: payload for payload, node_id, _parent in payload_keys if node_id}

	children_by_parent: dict[str, list] = {}
	roots = []

	for payload, node_id, parent in payload_keys:
		if not node_id:
			continue
		if parent and parent in payload_by_id:
			children_by_parent.setdefault(parent, []).append(payload)
		else:
			roots.append(payload)

	for children in children_by_parent.values():
		children.sort(key=lambda payload: payload.rows[0].row_number)
	roots.sort(key=lambda payload: payload.rows[0].row_number)

	ordered = []
	seen = set()
	payload_id_by_payload = {id(payload): node_id for payload, node_id, _parent in payload_keys}

	stack = list(reversed(roots))
	while stack:
		payload = stack.pop()
		node_id = payload_id_by_payload[id(payload)]
		if not node_id or node_id in seen:
			continue
		seen.add(node_id)
		ordered.append(payload)
		stack.extend(reversed(children_by_parent.get(node_id, [])))

	for payload, node_id, _parent in payload_keys:
		if not node_id or node_id not in seen:
			ordered.append(payload)

	return ordered


def _order_tree_preview_nodes(nodes: list) -> list:
	in_file_ids = {node.id for node in nodes}
	children_by_parent: dict[str | None, list] = {}

	for node in nodes:
		parent_key = node.parent if node.parent in in_file_ids else None
		children_by_parent.setdefault(parent_key, []).append(node)

	for children in children_by_parent.values():
		children.sort(key=lambda n: n.row_number)

	ordered = []
	seen = set()

	stack = [(node, 0) for node in reversed(children_by_parent.get(None, []))]
	while stack:
		node, depth = stack.pop()
		if node.id in seen:
			continue
		seen.add(node.id)
		node.depth = depth
		ordered.append(node)
		stack.extend((child, depth + 1) for child in reversed(children_by_parent.get(node.id, [])))

	for node in nodes:
		if node.id not in seen:
			node.depth = 0
			node.orphan = True
			ordered.append(node)

	return ordered


class Row:
	def __init__(self, index, row, doctype, header, import_type):
		self.index = index
		self.row_number = index + 1
		self.doctype = doctype
		self.data = row
		self.header = header
		self.import_type = import_type
		self.warnings = []

		len_row = len(self.data)
		len_columns = len(self.header.columns)
		if len_row != len_columns:
			less_than_columns = len_row < len_columns
			message = (
				_("This row has fewer cells than the header — check for missing commas or columns")
				if less_than_columns
				else _("This row has more cells than the header — check for extra commas or columns")
			)
			self.warnings.append(
				{
					"row": self.row_number,
					"message": message,
				}
			)

	def parse_doc(self, doctype, parent_doc=None, table_df=None):
		col_indexes = self.header.get_column_indexes(doctype, table_df)
		values = self.get_values(col_indexes)

		if all(v in INVALID_VALUES for v in values):
			# if all values are invalid, no need to parse it
			return None

		columns = self.header.get_columns(col_indexes)
		return self._parse_doc(doctype, columns, values, parent_doc, table_df)

	def _parse_doc(self, doctype, columns, values, parent_doc=None, table_df=None):
		doc = frappe._dict()
		if self.import_type == INSERT:
			# new_doc returns a dict with default values set
			doc = frappe.new_doc(
				doctype,
				parent_doc=parent_doc,
				parentfield=table_df.fieldname if table_df else None,
				as_dict=True,
			)

		# remove standard fields and __islocal
		for key in frappe.model.default_fields + frappe.model.child_table_fields + ("__islocal",):
			doc.pop(key, None)

		for col, value in zip(columns, values, strict=False):
			df = col.df
			if value in INVALID_VALUES:
				value = None

			if value is not None:
				value = self.validate_value(value, col)

			if value is not None:
				doc[df.fieldname] = self.parse_value(value, col)

		is_table = frappe.get_meta(doctype).istable
		is_update = self.import_type in (UPDATE, UPSERT)
		if is_table and is_update:
			# check if the row already exists
			# if yes, fetch the original doc so that it is not updated
			# if no, create a new doc
			id_field = get_id_field(doctype)
			id_value = doc.get(id_field.fieldname)
			if id_value and frappe.db.exists(doctype, id_value):
				existing_doc = frappe.get_doc(doctype, id_value)
				existing_doc.update(doc)
				doc = existing_doc
			else:
				# for table rows being inserted in update
				# create a new doc with defaults set
				new_doc = frappe.new_doc(doctype, as_dict=True)
				new_doc.update(doc)
				doc = new_doc

		return doc

	def validate_value(self, value, col):
		# Apply stored mappings only during import, not while building preview warnings.
		if frappe.flags.in_import:
			from frappe.core.doctype.data_import.value_mapping import resolve_import_value

			value = resolve_import_value(
				value, col.df, self.header.reference_doctype, self.header.value_lookup
			)
		df = col.df
		if df.fieldtype == "Select":
			select_options = get_select_options(df)
			if select_options and cstr(value) not in select_options:
				options_string = ", ".join(select_options)
				msg = _('"{0}" is not valid. Allowed: {1}').format(
					frappe.bold(escape_html(cstr(value))), frappe.bold(options_string)
				)
				self.warnings.append(
					{
						"row": self.row_number,
						"field": df_as_json(df),
						"message": msg,
					}
				)
				return

		elif df.fieldtype == "Link":
			if df.options == self.doctype and _is_same_file_tree_reference(value, self.header):
				return value

			exists = self.link_exists(value, df)
			if not exists:
				msg = _('"{0}" is not a valid {1}').format(
					frappe.bold(escape_html(cstr(value))), frappe.bold(df.label)
				)
				self.warnings.append(
					{
						"row": self.row_number,
						"field": df_as_json(df),
						"message": msg,
					}
				)
				return
		elif df.fieldtype == "Date":
			value = self.get_date(value, col)
			if isinstance(value, str):
				# value was not parsed as datetime object
				self.warnings.append(
					{
						"row": self.row_number,
						"col": col.column_number,
						"field": df_as_json(df),
						"message": _('"{0}" is not a valid date. Use {1}').format(
							frappe.bold(escape_html(cstr(value))),
							frappe.bold(get_user_format(col.date_format)),
						),
					}
				)
				return
		elif df.fieldtype == "Datetime":
			value = self.get_datetime(value, col)
			if isinstance(value, str):
				# value was not parsed as datetime object
				self.warnings.append(
					{
						"row": self.row_number,
						"col": col.column_number,
						"field": df_as_json(df),
						"message": _('"{0}" is not a valid datetime. Use {1}').format(
							frappe.bold(escape_html(cstr(value))),
							frappe.bold(get_user_format(col.date_format)),
						),
					}
				)
				return
		elif df.fieldtype == "Duration":
			if not DURATION_PATTERN.match(value):
				self.warnings.append(
					{
						"row": self.row_number,
						"col": col.column_number,
						"field": df_as_json(df),
						"message": _('"{0}" is not valid. Use duration format: d h m s').format(
							frappe.bold(escape_html(cstr(value)))
						),
					}
				)

		return value

	def link_exists(self, value, df):
		return bool(frappe.db.exists(df.options, value, cache=True))

	def parse_value(self, value, col):
		df = col.df
		if isinstance(value, datetime | date) and df.fieldtype in ["Date", "Datetime"]:
			return value

		value = cstr(value)

		# convert boolean values to 0 or 1
		valid_check_values = ["t", "f", "true", "false", "yes", "no", "y", "n"]
		if df.fieldtype == "Check" and value.lower().strip() in valid_check_values:
			value = value.lower().strip()
			value = 1 if value in ["t", "true", "y", "yes"] else 0

		if df.fieldtype in ["Int", "Check"]:
			value = cint(value)
		elif df.fieldtype in ["Float", "Percent", "Currency"]:
			value = flt(value)
		elif df.fieldtype == "Date":
			value = self.get_date(value, col)
		elif df.fieldtype == "Datetime":
			value = self.get_datetime(value, col)
		elif df.fieldtype == "Duration":
			value = duration_to_seconds(value)

		return value

	def get_date(self, value, column) -> date:
		if isinstance(value, date):
			return value

		date_format = column.date_format
		if date_format:
			try:
				return datetime.strptime(value, date_format).date()
			except ValueError:
				# ignore date values that dont match the format
				# import will break for these values later
				pass
		return value

	def get_datetime(self, value, column) -> datetime:
		if isinstance(value, datetime):
			return value

		date_format = column.date_format
		if date_format:
			try:
				return datetime.strptime(value, date_format)
			except ValueError:
				# ignore date values that dont match the format
				# import will break for these values later
				pass
		return value

	def get_values(self, indexes):
		return [get_item_at_index(self.data, i) for i in indexes]

	def get(self, index):
		return self.data[index]

	def as_list(self):
		return self.data


class Header(Row):
	def __init__(
		self,
		index,
		row,
		doctype,
		raw_data,
		column_to_field_map=None,
		value_lookup=None,
		reference_doctype=None,
	):
		self.index = index
		self.row_number = index + 1
		self.data = row
		self.doctype = doctype
		self.reference_doctype = reference_doctype or doctype
		self.value_lookup = value_lookup or {}
		column_to_field_map = column_to_field_map or frappe._dict()

		self.seen = []
		self.columns = []

		# 1-based sheet row for each data row (row 1 = header); passed into Column validation
		value_row_numbers = [self.index + data_idx + 2 for data_idx in range(len(raw_data))]

		for j, header in enumerate(row):
			column_values = [get_item_at_index(r, j) for r in raw_data]
			map_to_field = column_to_field_map.get(str(j))
			column = Column(
				j,
				header,
				self.doctype,
				column_values,
				map_to_field,
				self.seen,
				value_row_numbers,
			)
			self.seen.append(header)
			self.columns.append(column)

		doctypes = []
		for col in self.columns:
			if not col.df:
				continue
			if col.df.parent == self.doctype:
				doctypes.append((col.df.parent, None))
			else:
				doctypes.append((col.df.parent, col.df.child_table_df))

		self.doctypes = sorted(list(set(doctypes)), key=lambda x: -1 if x[0] == self.doctype else 1)

	def get_column_indexes(self, doctype, tablefield=None):
		def is_table_field(df):
			if tablefield:
				return df.child_table_df.fieldname == tablefield.fieldname
			return True

		return [
			col.index
			for col in self.columns
			if not col.skip_import and col.df and col.df.parent == doctype and is_table_field(col.df)
		]

	def get_columns(self, indexes):
		return [self.columns[i] for i in indexes]


class Column:
	def __init__(
		self,
		index,
		header,
		doctype,
		column_values,
		map_to_field=None,
		seen=None,
		value_row_numbers=None,
	):
		if seen is None:
			seen = []
		self.index = index
		self.column_number = index + 1
		self.doctype = doctype
		self.header_title = header
		self.column_values = column_values
		self.value_row_numbers = value_row_numbers or list(range(2, len(column_values) + 2))
		self.map_to_field = map_to_field
		self.seen = seen
		self.invalid_value_items = None

		self.date_format = None
		self.df = None
		self.skip_import = None
		self.warnings = []

		self.meta = frappe.get_meta(doctype)
		self.parse()
		self.validate_values()

	def parse(self):
		header_title = self.header_title
		column_number = str(self.column_number)
		skip_import = False

		if self.map_to_field and self.map_to_field != "Don't Import":
			df = get_df_for_column_header(self.doctype, self.map_to_field)
			if not df:
				self.warnings.append(
					{
						"message": _("Could not map column {0} to field {1}").format(
							column_number, self.map_to_field
						),
						"type": "info",
					}
				)
		else:
			df = get_df_for_column_header(self.doctype, header_title)
			# df = df_by_labels_and_fieldnames.get(header_title)

		if not df:
			skip_import = True
		else:
			skip_import = False

		if header_title in self.seen:
			self.warnings.append(
				{
					"col": column_number,
					"message": _("Skipping Duplicate Column {0}").format(
						frappe.bold(escape_html(header_title))
					),
					"type": "info",
				}
			)
			df = None
			skip_import = True
		elif self.map_to_field == "Don't Import":
			skip_import = True
			self.warnings.append(
				{
					"col": column_number,
					"message": _("Skipping column {0}").format(frappe.bold(escape_html(header_title))),
					"type": "info",
				}
			)
		elif header_title and not df:
			self.warnings.append(
				{
					"col": column_number,
					"message": _('"{0}" does not match any field — map it in the preview').format(
						frappe.bold(header_title)
					),
					"type": "info",
				}
			)
		elif not header_title and not df:
			self.warnings.append(
				{"col": column_number, "message": _("Skipping Untitled Column"), "type": "info"}
			)

		self.df = df
		self.skip_import = skip_import

	def guess_date_format_for_column(self):
		"""Guesses date format for a column by parsing all the values in the column,
		getting the date format and then returning the one which has the maximum frequency
		"""

		def guess_date_format(d):
			if isinstance(d, datetime | date | time):
				if self.df.fieldtype == "Date":
					return "%Y-%m-%d"
				if self.df.fieldtype == "Datetime":
					return "%Y-%m-%d %H:%M:%S"
				if self.df.fieldtype == "Time":
					return "%H:%M:%S"
			if isinstance(d, str):
				return frappe.utils.guess_date_format(d)

		date_formats = [guess_date_format(d) for d in self.column_values]
		date_formats = [d for d in date_formats if d]
		if not date_formats:
			return

		unique_date_formats = set(date_formats)
		max_occurred_date_format = max(unique_date_formats, key=date_formats.count)

		if len(unique_date_formats) > 1:
			# fmt: off
			message = _("The column {0} has {1} different date formats. Automatically setting {2} as the default format as it is the most common. Please change other values in this column to this format.")
			# fmt: on
			user_date_format = get_user_format(max_occurred_date_format)
			self.warnings.append(
				{
					"col": self.column_number,
					"message": message.format(
						frappe.bold(escape_html(self.header_title)),
						len(unique_date_formats),
						frappe.bold(user_date_format),
					),
					"type": "info",
				}
			)

		return max_occurred_date_format

	def validate_values(self):
		"""Validate all values in the column; append column-level warnings with row numbers."""
		if not self.df:
			return

		if self.skip_import:
			return

		if not any(self.column_values):
			return

		if self.df.fieldtype in ("Link", "Select"):
			from frappe.core.doctype.data_import.value_mapping import warn_invalid_link_select_values

			warn_invalid_link_select_values(self)
		elif self.df.fieldtype in ("Date", "Time", "Datetime"):
			# guess date/time format
			# TODO: add possibility for user, to define the date format explicitly in the Data Import UI
			# for example, if date column in file is in  %d-%m-%y  format -> 23-04-24.
			# The date guesser might fail, as, this can be also parsed as %y-%m-%d, as both 23 and 24 are valid for year & for day
			# This is an issue that cannot be handled automatically, no matter how we try, as it completely depends on the user's input.
			# Defining an explicit value which surely recognizes
			self.date_format = self.guess_date_format_for_column()

			if not self.date_format:
				if self.df.fieldtype == "Time":
					self.date_format = "%H:%M:%S"
					date_format = "HH:mm:ss"
				else:
					self.date_format = "%Y-%m-%d"
					date_format = "yyyy-mm-dd"

				message = _(
					"{0} format could not be determined from the values in this column. Defaulting to {1}."
				)
				self.warnings.append(
					{
						"col": self.column_number,
						"message": message.format(self.df.fieldtype, date_format),
						"type": "info",
					}
				)

	def as_dict(self):
		d = frappe._dict()
		d.index = self.index
		d.column_number = self.column_number
		d.doctype = self.doctype
		d.header_title = self.header_title
		d.map_to_field = self.map_to_field
		d.date_format = self.date_format
		d.df = self.df
		if hasattr(self.df, "is_child_table_field"):
			d.is_child_table_field = self.df.is_child_table_field
			d.child_table_df = self.df.child_table_df
		d.skip_import = self.skip_import
		d.warnings = self.warnings
		return d


def build_fields_dict_for_column_matching(parent_doctype):
	"""
	Build a dict with various keys to match with column headers and value as docfield
	The keys can be label or fieldname
	{
	        'Customer': df1,
	        'customer': df1,
	        'Due Date': df2,
	        'due_date': df2,
	        'Item Code (Sales Invoice Item)': df3,
	        'Sales Invoice Item:item_code': df3,
	}
	"""

	def get_standard_fields(doctype):
		meta = frappe.get_meta(doctype)
		if meta.istable:
			standard_fields = [
				{"label": "Parent", "fieldname": "parent"},
				{"label": "Parent Type", "fieldname": "parenttype"},
				{"label": "Parent Field", "fieldname": "parentfield"},
				{"label": "Row Index", "fieldname": "idx"},
			]
		else:
			standard_fields = [
				{"label": "Owner", "fieldname": "owner"},
				{"label": "Document Status", "fieldname": "docstatus", "fieldtype": "Int"},
			]

		out = []
		for df in standard_fields:
			df = frappe._dict(df)
			df.parent = doctype
			out.append(df)
		return out

	parent_meta = frappe.get_meta(parent_doctype)
	out = {}

	# doctypes and fieldname if it is a child doctype
	doctypes = [(parent_doctype, None)] + [(df.options, df) for df in parent_meta.get_table_fields()]

	for doctype, table_df in doctypes:
		table_ref = (table_df.label or table_df.fieldname) if table_df else None
		translated_table_label = _(table_ref) if table_ref else None

		# name field
		name_df = frappe._dict(
			{
				"fieldtype": "Data",
				"fieldname": "name",
				"label": "ID",
				"reqd": 1,  # self.import_type == UPDATE,
				"parent": doctype,
			}
		)

		if doctype == parent_doctype:
			name_headers = (
				"name",  # fieldname
				"ID",  # label
				_("ID"),  # translated label
			)
		else:
			name_headers = (
				f"{table_df.fieldname}.name",  # fieldname
				f"ID ({table_ref})",  # label
				"{} ({})".format(_("ID"), translated_table_label),  # translated label
			)

			name_df.is_child_table_field = True
			name_df.child_table_df = table_df

		for header in name_headers:
			out[header] = name_df

		fields = get_standard_fields(doctype) + frappe.get_meta(doctype).fields
		for df in fields:
			fieldtype = df.fieldtype or "Data"
			if fieldtype in no_value_fields:
				continue

			label = (df.label or "").strip()
			translated_label = _(label)

			if parent_doctype == doctype:
				# for parent doctypes keys will be
				# Label, fieldname, Label (fieldname)

				for header in (label, translated_label):
					# if Label is already set, don't set it again
					# in case of duplicate column headers
					if header not in out:
						out[header] = df

				for header in (
					df.fieldname,
					f"{label} ({df.fieldname})",
					f"{translated_label} ({df.fieldname})",
				):
					out[header] = df

			else:
				# for child doctypes keys will be
				# Label (Table Field Label)
				# table_field.fieldname

				# create a new df object to avoid mutation problems
				if isinstance(df, dict):
					new_df = frappe._dict(df.copy())
				else:
					new_df = df.as_dict()

				new_df.is_child_table_field = True
				new_df.child_table_df = table_df

				for header in (
					# fieldname
					f"{table_df.fieldname}.{df.fieldname}",
					# label
					f"{label} ({table_ref})",
					# translated label
					f"{translated_label} ({translated_table_label})",
				):
					out[header] = new_df

	# if autoname is based on field
	# add an entry for "ID (Autoname Field)"
	autoname_field = get_autoname_field(parent_doctype)
	if autoname_field:
		for header in (
			f"ID ({autoname_field.label})",  # label
			"{} ({})".format(_("ID"), _(autoname_field.label)),  # translated label
			# ID field should also map to the autoname field
			"ID",
			_("ID"),
			"name",
		):
			out[header] = autoname_field

	return out


def get_df_for_column_header(doctype, header):
	def build_fields_dict_for_doctype():
		return build_fields_dict_for_column_matching(doctype)

	df_by_labels_and_fieldname = frappe.cache.hget(
		"data_import_column_header_map", doctype, generator=build_fields_dict_for_doctype
	)
	return df_by_labels_and_fieldname.get(header)


# utilities


def get_id_field(doctype):
	autoname_field = get_autoname_field(doctype)
	if autoname_field:
		return autoname_field
	return frappe._dict({"label": "ID", "fieldname": "name", "fieldtype": "Data"})


def get_autoname_field(doctype):
	meta = frappe.get_meta(doctype)
	if meta.autoname and meta.autoname.startswith("field:"):
		fieldname = meta.autoname[len("field:") :]
		return meta.get_field(fieldname)


def get_item_at_index(_list, i, default=None):
	try:
		a = _list[i]
	except IndexError:
		a = default
	return a


def get_user_format(date_format):
	return date_format.replace("%Y", "yyyy").replace("%y", "yy").replace("%m", "mm").replace("%d", "dd")


def df_as_json(df):
	return {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": df.label,
		"options": df.options,
		"parent": df.parent,
		"default": df.default,
	}


def get_select_options(df):
	return [d for d in (df.options or "").split("\n") if d]


def create_import_log(data_import, log_index, log_details):
	frappe.get_doc(
		{
			"doctype": "Data Import Log",
			"log_index": log_index,
			"success": log_details.get("success"),
			"data_import": data_import,
			"row_indexes": json.dumps(log_details.get("row_indexes")),
			"docname": log_details.get("docname"),
			"messages": json.dumps(log_details.get("messages", "[]")),
			"exception": log_details.get("exception"),
			"import_action": log_details.get("import_action"),
		}
	).db_insert()
