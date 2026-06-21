// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

const UPSERT_IMPORT_TYPE = "Insert or Update Records";
const UPDATE_IMPORT_TYPE = "Update Existing Records";
const IMPORT_ACTION_UPDATE = "Update";

function is_upsert_import_type(import_type) {
	return import_type === UPSERT_IMPORT_TYPE;
}

/** Progress headline shown while an import job is running. */
function get_import_progress_message(import_type, current, total, eta_message) {
	const args = [current, total, eta_message];
	if (import_type === UPDATE_IMPORT_TYPE) {
		return __("Updating {0} of {1}, {2}", args);
	}
	if (is_upsert_import_type(import_type)) {
		return __("Importing or updating {0} of {1}, {2}", args);
	}
	return __("Importing {0} of {1}, {2}", args);
}

/** Summary headline after import completes. */
function get_import_status_message(import_type, inserted, updated, total) {
	if (import_type === UPDATE_IMPORT_TYPE) {
		return __("Successfully updated {0} out of {1} records.", [inserted, total]);
	}
	if (is_upsert_import_type(import_type)) {
		return __("Successfully inserted {0} and updated {1} out of {2} records.", [
			inserted,
			updated,
			total,
		]);
	}
	return __("Successfully imported {0} out of {1} records.", [inserted, total]);
}

/** Success message for a single import log row. */
function get_import_log_html(import_type, import_action, doc_link) {
	if (is_upsert_import_type(import_type)) {
		return import_action === IMPORT_ACTION_UPDATE
			? __("Successfully updated {0}", [doc_link])
			: __("Successfully inserted {0}", [doc_link]);
	}
	if (import_type === UPDATE_IMPORT_TYPE) {
		return __("Successfully updated {0}", [doc_link]);
	}
	return __("Successfully imported {0}", [doc_link]);
}

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

/** 1-based sheet row numbers marked to skip on the Data Import form. */
function get_skipped_row_set(frm) {
	return new Set((frm.doc.skipped_rows || []).map((row) => cint(row.row_number)));
}

/** Show a muted (count) badge on a collapsible section header, before the chevron. */
function update_section_count(frm, section_fieldname, count, count_class) {
	const section = frm.layout?.sections_dict?.[section_fieldname];
	if (!section?.head) return;

	let $count = section.head.find(`.${count_class}`);
	if (!count) {
		$count.remove();
		return;
	}

	if (!$count.length) {
		$count = $(`<span class="text-muted ${count_class}"></span>`);
		section.head.find(".collapse-indicator").before($count);
	}
	$count.text(`(${count})`);
}

function get_preview_row_count(preview_data) {
	if (!preview_data) return 0;
	return preview_data.total_number_of_rows ?? preview_data.data?.length ?? 0;
}

function get_tree_preview_node_count(preview_data) {
	if (!preview_data?.tree_preview) return 0;
	return preview_data.tree_preview.total_nodes ?? preview_data.tree_preview.nodes?.length ?? 0;
}

/** Hide tree structure warnings after a finished import; keep the tree for reference. */
function strip_tree_preview_warnings(preview_data) {
	if (!preview_data?.tree_preview) {
		return preview_data;
	}

	const nodes = (preview_data.tree_preview.nodes || []).map((node) => ({
		...node,
		warnings: [],
	}));

	return {
		...preview_data,
		tree_preview: {
			...preview_data.tree_preview,
			tree_warnings: [],
			nodes,
		},
	};
}

/** Keep Tree Preview collapsed by default (unlike Preview, which expands when a file is attached). */
function collapse_import_tree_section(frm, hide = true) {
	const section = frm.layout?.sections_dict?.section_import_tree_preview;
	if (section) {
		section.collapse(hide);
	}
}

/** Docfield for Map To: Link/Select per mapping row (child meta defaults to Data). */
function get_mapping_target_df(grid_row) {
	const doc = grid_row.doc;
	const base_df = frappe.meta.get_docfield(
		doc.doctype,
		"target_value",
		grid_row.parent_doc?.name
	);
	const df = { ...base_df };
	const { fieldtype, link_doctype, select_options } = doc;
	if (fieldtype === "Link" && link_doctype) {
		Object.assign(df, { fieldtype: "Link", options: link_doctype });
	} else if (fieldtype === "Select" && select_options) {
		Object.assign(df, { fieldtype: "Select", options: select_options });
	}
	return df;
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
		frappe.realtime.on("data_import_blocked", ({ data_import }) => {
			if (data_import !== frm.doc.name) return;
			frappe.show_alert({
				message: __(
					"Import could not start. Please resolve the errors in the import file."
				),
				indicator: "red",
			});
			frm.scroll_to_field("import_warnings_section");
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
				message = get_import_progress_message(
					frm.doc.import_type,
					data.current,
					data.total,
					eta_message
				);
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

		frm.events.setup_skip_row_handlers(frm);
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

		if (frm.doc.status.includes("Success")) {
			frm.add_custom_button(__("Go to {0} List", [__(frm.doc.reference_doctype)]), () =>
				frappe.set_route("List", frm.doc.reference_doctype)
			);
		}

		frm.events.setup_value_mappings_grid(frm);
		frm.events.setup_preview_section_collapse_handler(frm);
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

				const is_upsert = is_upsert_import_type(frm.doc.import_type);
				let message = get_import_status_message(
					frm.doc.import_type,
					is_upsert ? cint(r.message.inserted) : successful_records,
					is_upsert ? cint(r.message.updated) : 0,
					total_records
				);

				if (failed_records > 0) {
					message +=
						"<br/>" +
						__(
							"Please click on 'Export Errored Rows', fix the errors and import again."
						);
					frm.add_custom_button(__("Export Errored Rows"), () =>
						frm.trigger("export_errored_rows")
					);
				}

				if ((frm.doc.skipped_rows || []).length) {
					message +=
						"<br/>" +
						__(
							"Please click on 'Download Skipped Rows' to export rows that were skipped during import."
						);
					frm.add_custom_button(__("Download Skipped Rows"), () =>
						frm.trigger("download_skipped_rows")
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
		$(window).off("scroll.data_import_value_mappings");
		frm.import_preview = null;
		frm.import_tree_preview = null;
		frm.events.toggle_import_issues_ui(frm, false, false);
		frm.events.toggle_import_log_ui(frm, false);
		frm.toggle_display("section_import_tree_preview", false);
		frm.toggle_display("section_import_preview", false);
		frm.get_field("import_tree_preview")?.$wrapper.empty();
		frm.get_field("import_preview")?.$wrapper.empty();
		frm.get_field("import_warnings")?.$wrapper.html("");
		frm.get_field("import_log_preview")?.$wrapper.empty();
		update_section_count(frm, "import_warnings_section", 0, "import-warnings-count");
		update_section_count(frm, "value_mappings_section", 0, "value-mappings-count");
		update_section_count(frm, "section_import_tree_preview", 0, "import-tree-preview-count");
		update_section_count(frm, "section_import_preview", 0, "import-preview-count");
	},

	toggle_import_log_ui(frm, show) {
		for (const fieldname of ["import_log_heading", "show_failed_logs", "import_log_preview"]) {
			frm.toggle_display(fieldname, show);
		}
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

		frm.set_df_property("value_mappings", "cannot_add_rows", true);
		frm.set_df_property("value_mappings", "cannot_delete_rows", true);
		grid.cannot_add_rows = true;

		if (!grid._value_mapping_hooks) {
			grid._value_mapping_hooks = true;
			frm.events.setup_mapping_dropdown_portal(grid);
			const refresh = grid.refresh.bind(grid);
			grid.refresh = () => {
				refresh();
				frm.events.apply_mapping_target_fields(frm);
			};
		}

		grid.setup_toolbar?.();
		grid.refresh_remove_rows_button?.();
		frm.events.apply_mapping_target_fields(frm);
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

	apply_mapping_target_fields(frm) {
		const grid = frm.fields_dict.value_mappings?.grid;
		(grid?.grid_rows || []).forEach((grid_row) => {
			frm.events.configure_mapping_target_field(grid_row);
		});
	},

	configure_mapping_target_field(grid_row) {
		if (!grid_row?.doc) return;

		const target_df = get_mapping_target_df(grid_row);

		const column = grid_row.columns?.target_value;
		if (column) {
			column.df = target_df;
			if (column.field) {
				column.field_area?.empty();
				column.field = null;
				grid_row.make_control(column);
			}
		}

		const form_field = grid_row.grid_form?.fields_dict?.target_value;
		if (!form_field) return;

		const fieldtype_changed = form_field.df.fieldtype !== target_df.fieldtype;
		const options_changed = form_field.df.options !== target_df.options;
		if (!fieldtype_changed && !options_changed) {
			form_field.df = target_df;
			form_field.refresh();
			return;
		}

		const parent = form_field.$wrapper.parent();
		form_field.$wrapper.remove();
		const field = frappe.ui.form.make_control({
			df: target_df,
			parent,
			doc: grid_row.doc,
			doctype: grid_row.doc.doctype,
			docname: grid_row.doc.name,
			frm: grid_row.frm,
			grid: grid_row.grid,
			grid_row,
			grid_row_form: grid_row.grid_form,
			layout: grid_row.grid_form.layout,
		});
		grid_row.grid_form.fields_dict.target_value = field;
		const field_idx = grid_row.grid_form.fields.indexOf(form_field);
		if (field_idx >= 0) {
			grid_row.grid_form.fields[field_idx] = field;
		}
		if (grid_row.grid_form.layout?.fields_dict) {
			grid_row.grid_form.layout.fields_dict.target_value = field;
		}
		field.refresh();
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
			frm.events.show_import_tree_preview(frm, preview_data);
			frm.events.show_import_preview(frm, preview_data);
			frm.events.show_import_warnings(frm, preview_data);
		});
	},

	show_import_tree_preview(frm, preview_data) {
		if (["Success", "Partial Success"].includes(frm.doc.status)) {
			preview_data = strip_tree_preview_warnings(preview_data);
		}

		const show_tree = Boolean(preview_data?.tree_preview);
		frm.toggle_display("section_import_tree_preview", show_tree);
		frm.toggle_display("import_tree_preview", show_tree);

		if (!show_tree) {
			frm.import_tree_preview = null;
			frm.get_field("import_tree_preview")?.$wrapper.empty();
			update_section_count(
				frm,
				"section_import_tree_preview",
				0,
				"import-tree-preview-count"
			);
			return;
		}

		update_section_count(
			frm,
			"section_import_tree_preview",
			get_tree_preview_node_count(preview_data),
			"import-tree-preview-count"
		);

		const render_tree_preview = () => {
			const wrapper = frm.get_field("import_tree_preview").$wrapper;
			const on_row_click = (row_number) => {
				frm.layout?.sections_dict?.section_import_preview?.collapse(false);
				frm.import_preview?.highlight_table_row(row_number);
			};

			if (
				frm.doc.name &&
				frm.import_tree_preview &&
				frm.import_tree_preview.data_import_name === frm.doc.name
			) {
				frm.import_tree_preview.preview_data = preview_data;
				frm.import_tree_preview.on_row_click = on_row_click;
				frm.import_tree_preview.refresh();
			} else {
				frm.import_tree_preview = new frappe.data_import.ImportTreePreview({
					wrapper,
					doctype: frm.doc.reference_doctype,
					preview_data,
					on_row_click,
				});
				frm.import_tree_preview.data_import_name = frm.doc.name;
			}

			// After layout refresh_section_collapse (Preview uses depends_on to expand).
			setTimeout(() => collapse_import_tree_section(frm, true), 0);
		};

		frappe.require("data_import_tools.bundle.js", render_tree_preview);
	},

	show_import_preview(frm, preview_data) {
		let import_log = preview_data.import_log;
		frm.layout?.sections_dict?.section_import_preview?.collapse(false);
		update_section_count(
			frm,
			"section_import_preview",
			get_preview_row_count(preview_data),
			"import-preview-count"
		);

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

	download_skipped_rows(frm) {
		open_url_post(
			"/api/method/frappe.core.doctype.data_import.data_import.download_skipped_rows",
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
			update_section_count(frm, "import_warnings_section", 0, "import-warnings-count");
			update_section_count(frm, "value_mappings_section", 0, "value-mappings-count");
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
		const has_saved_mappings = (frm.doc.value_mappings || []).length > 0;
		const show_mappings = has_mapping_hints && has_saved_mappings;
		frm.events.toggle_import_issues_ui(frm, warnings.length > 0, show_mappings);
		update_section_count(
			frm,
			"value_mappings_section",
			show_mappings ? (frm.doc.value_mappings || []).length : 0,
			"value-mappings-count"
		);
		if (!warnings.length && !has_mapping_hints) {
			frm.get_field("import_warnings").$wrapper.html("");
			update_section_count(frm, "import_warnings_section", 0, "import-warnings-count");
			return;
		}
		if (!warnings.length) {
			frm.get_field("import_warnings").$wrapper.html("");
			update_section_count(frm, "import_warnings_section", 0, "import-warnings-count");
		}

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
		const skipped_rows = get_skipped_row_set(frm);
		html += Object.keys(warnings_by_row)
			.sort((a, b) => cint(a) - cint(b))
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
				let is_skipped = skipped_rows.has(cint(row_number));
				let skip_btn = `<button type="button" class="btn btn-xs btn-default skip-row-btn" data-row="${row_number}">
					${is_skipped ? __("Undo Skip") : __("Skip Row")}
				</button>`;
				return `
				<div class="warning${is_skipped ? " skipped" : ""}" data-row="${row_number}">
					<h5 class="text-uppercase warning-row-header">
						<span>${__("Row {0}", [row_number])}</span>
						${skip_btn}
					</h5>
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
					let column_header = frappe.utils.escape_html(
						columns[warning.col].header_title
					);
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
			update_section_count(
				frm,
				"import_warnings_section",
				warnings.length,
				"import-warnings-count"
			);
		}
		if (has_mapping_hints && has_saved_mappings) {
			frm.events.setup_value_mappings_grid(frm);
		}
	},

	setup_skip_row_handlers(frm) {
		if (frm._skip_row_handlers) return;
		frm._skip_row_handlers = true;
		frm.get_field("import_warnings").$wrapper.on("click", ".skip-row-btn", (e) => {
			e.preventDefault();
			frm.events.toggle_skip_row(frm, $(e.currentTarget).data("row"));
		});
	},

	/** Re-render datatable when the preview section is expanded after collapse. */
	setup_preview_section_collapse_handler(frm) {
		const section = frm.layout?.sections_dict?.section_import_preview;
		if (!section || section._preview_collapse_hook) return;
		section._preview_collapse_hook = true;

		const collapse = section.collapse.bind(section);
		section.collapse = (hide) => {
			const was_collapsed = section.is_collapsed();
			collapse(hide);
			const preview = frm.import_preview;
			if (was_collapsed && !section.is_collapsed() && preview?.datatable) {
				requestAnimationFrame(() => {
					preview.render_datatable();
					preview.setup_styles();
				});
			}
		};
	},

	toggle_skip_row(frm, row_number) {
		row_number = cint(row_number);
		const skipped = (frm.doc.skipped_rows || []).find(
			(row) => cint(row.row_number) === row_number
		);

		if (skipped) {
			frappe.model.clear_doc(skipped.doctype, skipped.name);
		} else {
			const preview_row = frm.import_preview?.preview_data?.data?.find(
				(row) => cint(row[0]) === row_number
			);
			frm.add_child("skipped_rows", {
				row_number,
				row_data: JSON.stringify(preview_row ? preview_row.slice(1) : []),
			});
		}

		frm.dirty();
		frm.trigger("update_primary_action");
		frm.events.show_import_warnings(frm);
	},

	show_failed_logs(frm) {
		frm.trigger("show_import_log");
	},

	render_import_log(frm) {
		const is_upsert = is_upsert_import_type(frm.doc.import_type);

		const render_logs = (logs, inserted_count = 0, updated_count = 0) => {
			if (logs.length === 0) return;

			frm.events.toggle_import_log_ui(frm, true);

			let rows = logs
				.map((log) => {
					let html = "";
					if (log.success) {
						const doc_link = `<span class="underline">${frappe.utils.get_form_link(
							frm.doc.reference_doctype,
							log.docname,
							true
						)}<span>`;
						html = get_import_log_html(
							frm.doc.import_type,
							log.import_action,
							doc_link
						);
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

			let upsert_summary = "";
			if (is_upsert) {
				upsert_summary = `<div class="text-muted small mb-2">${__(
					"Inserted {0}, Updated {1}",
					[inserted_count, updated_count]
				)}</div>`;
			}

			frm.get_field("import_log_preview").$wrapper.html(`
					${upsert_summary}
					<table class="table table-bordered">
						<tr class="text-muted">
							<th width="10%">${__("Row Number")}</th>
							<th width="10%">${__("Status")}</th>
							<th width="80%">${__("Message")}</th>
						</tr>
						${rows}
					</table>
				`);
		};

		const fetch_logs = (inserted_count = 0, updated_count = 0) => {
			frappe.call({
				method: "frappe.core.doctype.data_import.data_import.get_import_logs",
				args: {
					data_import: frm.doc.name,
				},
				callback: function (r) {
					render_logs(r.message, inserted_count, updated_count);
				},
			});
		};

		if (is_upsert) {
			frappe.call({
				method: "frappe.core.doctype.data_import.data_import.get_import_status",
				args: {
					data_import_name: frm.doc.name,
				},
				callback: function (r) {
					fetch_logs(cint(r.message.inserted), cint(r.message.updated));
				},
				error: function () {
					fetch_logs();
				},
			});
		} else {
			fetch_logs();
		}
	},

	show_import_log(frm) {
		frm.events.toggle_import_log_ui(frm, false);

		if (frm.is_new() || frm.import_in_progress) {
			return;
		}

		frappe.call({
			method: "frappe.core.doctype.data_import.data_import.get_import_log_count",
			type: "GET",
			args: {
				data_import: frm.doc.name,
			},
			callback: function (r) {
				let count = r.message;
				if (count < 5000) {
					frm.trigger("render_import_log");
				} else {
					frm.events.toggle_import_log_ui(frm, false);
					frm.add_custom_button(__("Export Import Log"), () =>
						frm.trigger("export_import_log")
					);
				}
			},
		});
	},
});

frappe.ui.form.on("Data Import Value Mapping", {
	form_render(frm, cdt, cdn) {
		const grid_row = frm.fields_dict.value_mappings?.grid?.grid_rows_by_docname?.[cdn];
		if (grid_row) {
			frm.events.configure_mapping_target_field(grid_row);
		}
	},
});
