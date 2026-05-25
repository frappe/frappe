// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

/** Deduplicate template + preview warnings: one per column (longer message wins, often has row numbers). */
function dedupe_import_warnings(warnings) {
	const by_col = {};
	const rows = [];
	const others = [];
	const seen_rows = new Set();

	for (const w of warnings) {
		if (w.row) {
			const key = `${w.row}|${w.field?.fieldname}|${w.message}`;
			if (!seen_rows.has(key)) {
				seen_rows.add(key);
				rows.push(w);
			}
		} else if (w.col) {
			const prev = by_col[w.col];
			if (!prev || (w.message || "").length > (prev.message || "").length) {
				by_col[w.col] = w;
			}
		} else {
			others.push(w);
		}
	}
	return [...rows, ...Object.values(by_col), ...others];
}

frappe.ui.form.on("Data Import", {
	setup(frm) {
		frappe.realtime.on("data_import_refresh", ({ data_import }) => {
			frm.import_in_progress = false;
			if (data_import !== frm.doc.name) return;
			frappe.model.clear_doc("Data Import", frm.doc.name);
			frappe.model.with_doc("Data Import", frm.doc.name).then(() => {
				frm.refresh();
			});
		});
		frappe.realtime.on("data_import_progress", (data) => {
			frm.import_in_progress = true;
			if (data.data_import !== frm.doc.name) {
				return;
			}
			let percent = Math.floor((data.current * 100) / data.total);
			let seconds = Math.floor(data.eta);
			let minutes = Math.floor(data.eta / 60);
			let eta_message =
				// prettier-ignore
				seconds < 60
					? __('About {0} seconds remaining', [seconds])
					: minutes === 1
						? __('About {0} minute remaining', [minutes])
						: __('About {0} minutes remaining', [minutes]);

			let message;
			if (data.success) {
				let message_args = [data.current, data.total, eta_message];
				message =
					frm.doc.import_type === "Insert New Records"
						? __("Importing {0} of {1}, {2}", message_args)
						: __("Updating {0} of {1}, {2}", message_args);
			}
			if (data.skipping) {
				message = __("Skipping {0} of {1}, {2}", [data.current, data.total, eta_message]);
			}
			frm.dashboard.show_progress(__("Import Progress"), percent, message);
			frm.page.set_indicator(__("In Progress"), "orange");
			frm.trigger("update_primary_action");

			frm.trigger("show_cancel_import_btn");
			// hide progress when complete
			if (data.current === data.total) {
				setTimeout(() => {
					frm.dashboard.hide();
					frm.refresh();
				}, 2000);
			}
		});

		frm.set_query("reference_doctype", () => {
			return {
				filters: {
					name: ["in", frappe.boot.user.can_import],
				},
			};
		});

		frm.get_field("import_file").df.options = {
			restrictions: {
				allowed_file_types: [".csv", ".xls", ".xlsx"],
			},
		};

		frm.has_import_file = () => {
			return frm.doc.import_file || frm.doc.google_sheets_url;
		};

		$(frm.wrapper).on("dirty", () => {
			frm.trigger("update_primary_action");
		});
	},

	onload(frm) {
		if (!frm.has_import_file()) {
			frm.events.reset_import_ui_state(frm);
		}
	},

	refresh(frm) {
		frm.page.hide_icon_group();
		frm.trigger("update_indicators");
		frm.trigger("import_file");
		frm.trigger("show_import_log");
		frm.trigger("toggle_submit_after_import");

		if (frm.doc.status != "Pending") frm.trigger("show_import_status");

		frm.trigger("show_report_error_button");

		if (frm.doc.status === "Partial Success") {
			frm.add_custom_button(__("Export Errored Rows"), () =>
				frm.trigger("export_errored_rows")
			);
		}

		if (frm.doc.status.includes("Success")) {
			frm.add_custom_button(__("Go to {0} List", [__(frm.doc.reference_doctype)]), () =>
				frappe.set_route("List", frm.doc.reference_doctype)
			);
		}

		frm.events.setup_value_mappings_grid(frm);
		frm.trigger("update_primary_action");
	},

	onload_post_render(frm) {
		frm.trigger("update_primary_action");
	},

	update_primary_action(frm) {
		if (frm.is_dirty()) {
			frm.enable_save();
			frm.page.set_primary_action(__("Save"), () => {
				frm.save().then(() => {
					if (frm.has_import_file()) {
						frm.trigger("import_file");
					}
				});
			});
			return;
		}
		frm.disable_save();
		if (frm.doc.status !== "Success") {
			if (!frm.is_new() && frm.has_import_file()) {
				let label = frm.doc.status === "Pending" ? __("Start Import") : __("Retry");
				frm.page.set_primary_action(label, () => {
					frm.events.start_import(frm);
					if (label === "Retry") {
						frm.trigger("show_cancel_import_btn");
					}
				});
			} else {
				frm.page.set_primary_action(__("Save"), () => frm.save());
			}
		}
	},

	update_indicators(frm) {
		const indicator = frappe.get_indicator(frm.doc);
		if (indicator) {
			frm.page.set_indicator(indicator[0], indicator[1]);
		} else {
			frm.page.clear_indicator();
		}
	},

	show_import_status(frm) {
		frappe.call({
			method: "frappe.core.doctype.data_import.data_import.get_import_status",
			args: {
				data_import_name: frm.doc.name,
			},
			callback: function (r) {
				let successful_records = cint(r.message.success);
				let failed_records = cint(r.message.failed);
				let total_records = cint(r.message.total_records);

				if (!total_records) {
					return;
				}

				let message;
				if (frm.doc.import_type === "Insert New Records") {
					message = __("Successfully imported {0} out of {1} records.", [
						successful_records,
						total_records,
					]);
				} else {
					message = __("Successfully updated {0} out of {1} records.", [
						successful_records,
						total_records,
					]);
				}

				if (failed_records > 0) {
					message +=
						"<br/>" +
						__(
							"Please click on 'Export Errored Rows', fix the errors and import again."
						);
				}

				// If the job timed out, display an extra hint
				if (r.message.status === "Timed Out") {
					message += "<br/>" + __("Import timed out, please re-try.");
				}

				frm.dashboard.set_headline(message);
			},
		});
	},

	show_cancel_import_btn(frm) {
		frm.add_custom_button(__("Cancel Import"), () => {
			frappe.confirm(
				__(
					"This will terminate the job immediately and might be dangerous, are you sure?"
				),
				() => {
					frappe
						.xcall("frappe.core.doctype.data_import.data_import.stop_data_import", {
							doc_name: frm.doc.name,
						})
						.then((r) => {
							frappe.show_alert(__("Job Stopped Successfully"));
							frm.reload_doc();
						});
				}
			);
		});
	},

	show_report_error_button(frm) {
		if (frm.doc.status === "Error") {
			frappe.db
				.get_list("Error Log", {
					filters: { method: frm.doc.name },
					fields: ["method", "error"],
					order_by: "creation desc",
					limit: 1,
				})
				.then((result) => {
					if (result.length > 0) {
						frm.add_custom_button("Report Error", () => {
							let fake_xhr = {
								responseText: JSON.stringify({
									exc: result[0].error,
								}),
							};
							frappe.request.report_error(fake_xhr, {});
						});
					}
				});
		}
	},

	start_import(frm) {
		frm.call({
			method: "form_start_import",
			args: { data_import: frm.doc.name },
			btn: frm.page.btn_primary,
		}).then((r) => {
			if (r.message === true) {
				frm.disable_save();
			}
		});
	},

	download_template(frm) {
		frappe.require("data_import_tools.bundle.js", () => {
			frm.data_exporter = new frappe.data_import.DataExporter(
				frm.doc.reference_doctype,
				frm.doc.import_type
			);
		});
	},

	reference_doctype(frm) {
		frm.trigger("toggle_submit_after_import");
	},

	toggle_submit_after_import(frm) {
		frm.toggle_display("submit_after_import", false);
		let doctype = frm.doc.reference_doctype;
		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				let meta = frappe.get_meta(doctype);
				frm.toggle_display("submit_after_import", meta.is_submittable);
			});
		}
	},

	google_sheets_url(frm) {
		if (!frm.is_dirty()) {
			frm.trigger("import_file");
		} else {
			frm.trigger("update_primary_action");
		}
	},

	refresh_google_sheet(frm) {
		frm.trigger("import_file");
	},

	reset_import_ui_state(frm) {
		frm.import_preview = null;
		frm.events.toggle_import_issues_ui(frm, false, false);
		frm.toggle_display("section_import_preview", false);
		frm.get_field("import_preview")?.$wrapper.empty();
		frm.get_field("import_warnings")?.$wrapper.html("");
	},

	toggle_import_issues_ui(frm, show_warnings, show_mappings) {
		frm.toggle_display("import_warnings_section", show_warnings || show_mappings);
		frm.toggle_display("value_mappings_section", show_mappings);
		frm.toggle_display("value_mappings", show_mappings);
		if (show_mappings) {
			frm.events.setup_value_mappings_grid(frm);
		}
	},

	setup_value_mappings_grid(frm) {
		const grid = frm.fields_dict.value_mappings?.grid;
		if (!grid) return;

		if (!grid._value_mapping_hooks) {
			grid._value_mapping_hooks = true;
			frm.set_df_property("value_mappings", "cannot_add_rows", true);
			grid.cannot_add_rows = true;
			frm.events.setup_mapping_dropdown_portal(grid);
			const refresh = grid.refresh.bind(grid);
			grid.refresh = () => {
				refresh();
				frm.events.apply_mapping_target_fields(frm);
				frm.events.disable_mapping_row_checks(grid);
			};
		}

		grid.wrapper.find(".grid-buttons, .grid-add-row").hide();
		frm.events.apply_mapping_target_fields(frm);
		frm.events.disable_mapping_row_checks(grid);
	},

	setup_mapping_dropdown_portal(grid) {
		const position_dropdown = (input) => {
			const awesomplete = input.awesomplete;
			if (!awesomplete?.ul) return;
			const rect = input.getBoundingClientRect();
			const $ul = $(awesomplete.ul);
			if ($ul.parent()[0] !== document.body) {
				$ul.appendTo(document.body);
			}
			$ul.css({
				position: "fixed",
				left: rect.left,
				top: rect.bottom,
				minWidth: rect.width,
				zIndex: 1050,
			});
		};

		grid.wrapper.on("awesomplete-open", ".form-grid input", function () {
			position_dropdown(this);
		});
		grid.wrapper.on("input focus", ".form-grid .link-field input", function () {
			if (this.awesomplete?.ul && !$(this.awesomplete.ul).is(":hidden")) {
				position_dropdown(this);
			}
		});
		$(window).on("scroll.data_import_value_mappings", () => {
			grid.wrapper.find(".form-grid input:focus").each(function () {
				if (this.awesomplete?.ul && $(this.awesomplete.ul).is(":visible")) {
					position_dropdown(this);
				}
			});
		});
	},

	disable_mapping_row_checks(grid) {
		grid.wrapper.find(".grid-row-check input[type=checkbox]").prop("disabled", true);
	},

	apply_mapping_target_fields(frm) {
		const grid = frm.fields_dict.value_mappings?.grid;
		(grid?.grid_rows || []).forEach((grid_row) => {
			frm.events.configure_mapping_target_field(grid_row);
		});
	},

	configure_mapping_target_field(grid_row) {
		const column = grid_row.columns?.target_value;
		if (!column || !grid_row.doc) return;

		const base_df = frappe.meta.get_docfield(
			grid_row.doc.doctype,
			"target_value",
			grid_row.parent_doc?.name
		);
		column.df = { ...base_df };

		const { fieldtype, link_doctype, select_options } = grid_row.doc;
		if (fieldtype === "Link" && link_doctype) {
			Object.assign(column.df, { fieldtype: "Link", options: link_doctype });
		} else if (fieldtype === "Select" && select_options) {
			Object.assign(column.df, { fieldtype: "Select", options: select_options });
		}

		if (column.field) {
			column.field_area?.empty();
			column.field = null;
			grid_row.make_control(column);
		}
	},

	import_file(frm) {
		frm.toggle_display("section_import_preview", frm.has_import_file());
		if (!frm.has_import_file()) {
			frm.events.reset_import_ui_state(frm);
			return;
		} else {
			frm.trigger("update_primary_action");
		}

		// load import preview
		frm.get_field("import_preview").$wrapper.empty();
		$('<span class="text-muted">')
			.html(__("Loading import file..."))
			.appendTo(frm.get_field("import_preview").$wrapper);

		frm.call({
			method: "get_preview_from_template",
			args: {
				data_import: frm.doc.name,
				import_file: frm.doc.import_file,
				google_sheets_url: frm.doc.google_sheets_url,
			},
			error_handlers: {
				TimestampMismatchError() {
					// ignore this error
				},
			},
		}).then((r) => {
			let preview_data = r.message;
			frm.events.show_import_preview(frm, preview_data);
			frm.events.show_import_warnings(frm, preview_data);
		});
	},

	show_import_preview(frm, preview_data) {
		let import_log = preview_data.import_log;

		if (
			frm.doc.name &&
			frm.import_preview &&
			frm.import_preview.doctype === frm.doc.reference_doctype &&
			frm.import_preview.data_import_name === frm.doc.name
		) {
			frm.import_preview.preview_data = preview_data;
			frm.import_preview.import_log = import_log;
			frm.import_preview.refresh();
			return;
		}

		frappe.require("data_import_tools.bundle.js", () => {
			frm.import_preview = new frappe.data_import.ImportPreview({
				wrapper: frm.get_field("import_preview").$wrapper,
				doctype: frm.doc.reference_doctype,
				preview_data,
				import_log,
				frm,
				events: {
					remap_column(changed_map) {
						let template_options = JSON.parse(frm.doc.template_options || "{}");
						template_options.column_to_field_map =
							template_options.column_to_field_map || {};
						Object.assign(template_options.column_to_field_map, changed_map);
						frm.set_value("template_options", JSON.stringify(template_options));
						frm.save().then(() => frm.trigger("import_file"));
					},
				},
			});
			frm.import_preview.data_import_name = frm.doc.name;
		});
	},

	export_errored_rows(frm) {
		open_url_post(
			"/api/method/frappe.core.doctype.data_import.data_import.download_errored_template",
			{
				data_import_name: frm.doc.name,
			}
		);
	},

	export_import_log(frm) {
		open_url_post(
			"/api/method/frappe.core.doctype.data_import.data_import.download_import_log",
			{
				data_import_name: frm.doc.name,
			}
		);
	},

	/** Render import warnings; dedupe when preview and ``template_warnings`` overlap. */
	show_import_warnings(frm, preview_data) {
		if (!frm.has_import_file()) {
			frm.events.reset_import_ui_state(frm);
			return;
		}

		if (["Success", "Partial Success"].includes(frm.doc.status)) {
			frm.events.toggle_import_issues_ui(frm, false, false);
			frm.get_field("import_warnings")?.$wrapper.html("");
			return;
		}

		if (!preview_data && frm.import_preview?.data_import_name === frm.doc.name) {
			preview_data = frm.import_preview.preview_data;
		}
		let columns = preview_data?.columns;

		// template_warnings: saved when Start Import is blocked; preview: from file parse on upload
		let template_warnings = JSON.parse(frm.doc.template_warnings || "[]");
		let preview_warnings = preview_data?.warnings || [];
		let warnings = dedupe_import_warnings(template_warnings.concat(preview_warnings));

		const has_mapping_hints = Object.keys(preview_data?.mapping_hints || {}).length > 0;
		frm.events.toggle_import_issues_ui(frm, warnings.length > 0, has_mapping_hints);
		if (!warnings.length && !has_mapping_hints) {
			frm.get_field("import_warnings").$wrapper.html("");
			return;
		}
		if (!warnings.length) {
			frm.get_field("import_warnings").$wrapper.html("");
		}

		// group warnings by row
		let warnings_by_row = {};
		let other_warnings = [];
		for (let warning of warnings) {
			if (warning.row) {
				warnings_by_row[warning.row] = warnings_by_row[warning.row] || [];
				warnings_by_row[warning.row].push(warning);
			} else {
				other_warnings.push(warning);
			}
		}

		let html = "";
		html += Object.keys(warnings_by_row)
			.map((row_number) => {
				let message = warnings_by_row[row_number]
					.map((w) => {
						if (w.field) {
							let label =
								w.field.label +
								(w.field.parent !== frm.doc.reference_doctype
									? ` (${w.field.parent})`
									: "");
							return `<li>${label}: ${w.message}</li>`;
						}
						return `<li>${w.message}</li>`;
					})
					.join("");
				return `
				<div class="warning" data-row="${row_number}">
					<h5 class="text-uppercase">${__("Row {0}", [row_number])}</h5>
					<div class="body"><ul>${message}</ul></div>
				</div>
			`;
			})
			.join("");

		html += other_warnings
			.map((warning) => {
				let header = "";
				if (columns && warning.col) {
					let column_number = `<span class="text-uppercase">${__("Column {0}", [
						warning.col,
					])}</span>`;
					let column_header = columns[warning.col].header_title;
					header = `${column_number} (${column_header})`;
				}
				return `
					<div class="warning" data-col="${warning.col}">
						<h5>${header}</h5>
						<div class="body">${warning.message}</div>
					</div>
				`;
			})
			.join("");
		if (warnings.length) {
			frm.get_field("import_warnings").$wrapper.html(`
				<div class="row">
					<div class="col-sm-10 warnings">${html}</div>
				</div>
			`);
		}
		if (has_mapping_hints && !["Success", "Partial Success"].includes(frm.doc.status)) {
			frm.events.sync_value_mappings_table(frm, preview_data, columns);
		}
	},

	mapping_row_key(row) {
		return `${row.column}|${row.fieldname}|${row.parent_field || ""}|${row.source_value}`;
	},

	rows_display(rows) {
		if (!rows?.length) return "";
		if (rows.length <= 6) return rows.join(", ");
		return `${rows.slice(0, 6).join(", ")}, ... ${rows[rows.length - 1]}`;
	},

	child_row_from_hint(item, columns) {
		return {
			column: item.column,
			column_label: columns?.[item.column]?.header_title || __("Column {0}", [item.column]),
			fieldname: item.fieldname,
			parent_field: item.parent_field || "",
			fieldtype: item.fieldtype,
			link_doctype: item.link_doctype,
			select_options: (item.select_options || []).join("\n"),
			source_value: item.source_value,
			target_value: item.target_value || "",
			row_numbers: JSON.stringify(item.rows || []),
		};
	},

	sync_value_mappings_table(frm, preview_data, columns) {
		const items = Object.values(preview_data?.mapping_hints || {}).flat();
		if (!items.length) return;

		const existing = Object.fromEntries(
			(frm.doc.value_mappings || []).map((row) => [frm.events.mapping_row_key(row), row])
		);
		const seen = new Set();
		let changed = false;

		for (const item of items) {
			const key = frm.events.mapping_row_key(item);
			seen.add(key);
			const data = {
				...frm.events.child_row_from_hint(item, columns),
				rows_display: frm.events.rows_display(item.rows),
			};
			if (existing[key]) {
				const target_value = existing[key].target_value;
				Object.assign(existing[key], data);
				// Keep in-progress user edits; only fill target from saved lookup when empty.
				existing[key].target_value = target_value || data.target_value;
				continue;
			}
			frm.add_child("value_mappings", data);
			changed = true;
		}

		for (const row of [...(frm.doc.value_mappings || [])]) {
			if (!seen.has(frm.events.mapping_row_key(row))) {
				frappe.model.clear_doc(row.doctype, row.name);
				changed = true;
			}
		}

		frm.refresh_field("value_mappings");
		frm.events.setup_value_mappings_grid(frm);
		if (changed) {
			frm.dirty();
			frm.trigger("update_primary_action");
		}
	},

	show_failed_logs(frm) {
		frm.trigger("show_import_log");
	},

	render_import_log(frm) {
		frappe.call({
			method: "frappe.core.doctype.data_import.data_import.get_import_logs",
			args: {
				data_import: frm.doc.name,
			},
			callback: function (r) {
				let logs = r.message;

				if (logs.length === 0) return;

				frm.toggle_display("import_log_section", true);

				let rows = logs
					.map((log) => {
						let html = "";
						if (log.success) {
							if (frm.doc.import_type === "Insert New Records") {
								html = __("Successfully imported {0}", [
									`<span class="underline">${frappe.utils.get_form_link(
										frm.doc.reference_doctype,
										log.docname,
										true
									)}<span>`,
								]);
							} else {
								html = __("Successfully updated {0}", [
									`<span class="underline">${frappe.utils.get_form_link(
										frm.doc.reference_doctype,
										log.docname,
										true
									)}<span>`,
								]);
							}
						} else {
							let messages = JSON.parse(log.messages || "[]")
								.map((m) => {
									let title = m.title ? `<strong>${m.title}</strong>` : "";
									let message = m.message ? `<div>${m.message}</div>` : "";
									return title + message;
								})
								.join("");
							let id = frappe.dom.get_unique_id();
							html = `${messages}
								<button class="btn btn-default btn-xs" type="button" data-toggle="collapse" data-target="#${id}" aria-expanded="false" aria-controls="${id}" style="margin-top: 15px;">
									${__("Show Traceback")}
								</button>
								<div class="collapse" id="${id}" style="margin-top: 15px;">
									<div class="well">
										<pre>${log.exception}</pre>
									</div>
								</div>`;
						}
						let indicator_color = log.success ? "green" : "red";
						let title = log.success ? __("Success") : __("Failure");

						if (frm.doc.show_failed_logs && log.success) {
							return "";
						}

						return `<tr>
							<td>${JSON.parse(log.row_indexes).join(", ")}</td>
							<td>
								<div class="indicator ${indicator_color}">${title}</div>
							</td>
							<td>
								${html}
							</td>
						</tr>`;
					})
					.join("");

				if (!rows && frm.doc.show_failed_logs) {
					rows = `<tr><td class="text-center text-muted" colspan=3>
						${__("No failed logs")}
					</td></tr>`;
				}

				frm.get_field("import_log_preview").$wrapper.html(`
					<table class="table table-bordered">
						<tr class="text-muted">
							<th width="10%">${__("Row Number")}</th>
							<th width="10%">${__("Status")}</th>
							<th width="80%">${__("Message")}</th>
						</tr>
						${rows}
					</table>
				`);
			},
		});
	},

	show_import_log(frm) {
		frm.toggle_display("import_log_section", false);

		if (frm.is_new() || frm.import_in_progress) {
			return;
		}

		frappe.call({
			method: "frappe.client.get_count",
			args: {
				doctype: "Data Import Log",
				filters: {
					data_import: frm.doc.name,
				},
			},
			callback: function (r) {
				let count = r.message;
				if (count < 5000) {
					frm.trigger("render_import_log");
				} else {
					frm.toggle_display("import_log_section", false);
					frm.add_custom_button(__("Export Import Log"), () =>
						frm.trigger("export_import_log")
					);
				}
			},
		});
	},
});

frappe.ui.form.on("Data Import Value Mapping", {
	form_render(frm) {
		if (frm.doc.fieldtype === "Link" && frm.doc.link_doctype) {
			frm.set_df_property("target_value", "fieldtype", "Link");
			frm.set_df_property("target_value", "options", frm.doc.link_doctype);
		} else if (frm.doc.fieldtype === "Select" && frm.doc.select_options) {
			frm.set_df_property("target_value", "fieldtype", "Select");
			frm.set_df_property("target_value", "options", frm.doc.select_options);
		}
	},
});
