// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

const UPSERT_IMPORT_TYPE = "Insert or Update Records";
const UPDATE_IMPORT_TYPE = "Update Existing Records";
const IMPORT_ACTION_INSERT = "Insert";
const IMPORT_ACTION_UPDATE = "Update";
const IMPORT_LOG_PREVIEW_LIMIT = 1000;

/** Tab badge text: `1000 of 5000` when truncated, else plain count. */
function format_import_log_tab_count(total) {
	const n = cint(total);
	if (n > IMPORT_LOG_PREVIEW_LIMIT) {
		return __("{0} of {1}", [IMPORT_LOG_PREVIEW_LIMIT, n]);
	}
	return String(n);
}

const WIZARD_STEP_COUNT = 4;

/** Import step fields reparented by the wizard (Config / Preview / Fix Issues have dedicated mounts). */
const IMPORT_STEP_FIELDS = ["import_log_heading", "import_log_preview"];

function is_import_complete(status) {
	return ["Success", "Partial Success"].includes(status);
}

function parse_template_warnings(frm) {
	try {
		return JSON.parse(frm.doc.template_warnings || "[]") || [];
	} catch (_e) {
		return [];
	}
}

function is_tree_reference_doctype(frm) {
	const doctype = frm.doc?.reference_doctype;
	return Boolean(doctype && frappe.get_meta(doctype)?.is_tree);
}

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
	const seen_others = new Map(); // Use Map to store the warning, not just seen status

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
			const key = `${w.code || ""}|${w.title || ""}|${w.message || ""}`;
			const existing = seen_others.get(key);
			// Prefer warning with more metadata (e.g., type, rows) for better UI rendering
			if (!existing || (w.type && !existing.type)) {
				seen_others.set(key, w);
			}
		}
	}
	return [...rows, ...Object.values(by_col), ...Array.from(seen_others.values())];
}

/** Warnings that can typically be solved through Value Mappings. */
function is_mapping_warning(warning) {
	return warning?.type === "value_mapping";
}

/** Horizontal preview table (header + one data row) for the Row errors hover card. */
function build_import_row_preview_table(preview_data, row_number) {
	const columns = preview_data?.columns || [];
	const row = (preview_data?.data || []).find((r) => cint(r[0]) === cint(row_number));
	const $wrap = $(`<div class="diw-row-preview-popover overflow-x-auto"></div>`);
	if (!row) {
		$wrap.append(
			`<div class="text-sm text-muted">${__("No preview data for this row")}</div>`
		);
		return $wrap;
	}

	const cell_style =
		"padding:6px 10px;border:1px solid var(--border-color);text-align:left;white-space:nowrap";
	const th_style = `${cell_style};background:var(--control-bg);color:var(--heading-color);font-weight:600`;

	const header_cells = columns
		.map((col, i) => {
			const label = col.header_title || col.df?.label || __("Column {0}", [i]);
			return `<th style="${th_style}">${frappe.utils.escape_html(label)}</th>`;
		})
		.join("");

	const data_cells = columns
		.map((_, i) => {
			const raw = row[i];
			const value = raw == null || raw === "" ? "—" : cstr(raw);
			const escaped = frappe.utils.escape_html(value);
			return `<td style="${cell_style}" title="${escaped}">${escaped}</td>`;
		})
		.join("");

	$wrap.html(`
		<table style="border-collapse:collapse;font-size:var(--text-sm)">
			<thead><tr>${header_cells}</tr></thead>
			<tbody><tr>${data_cells}</tr></tbody>
		</table>
	`);
	return $wrap;
}

/** Attach hover cards on "Row N" labels so the sheet row can be previewed. */
function setup_row_warning_hover_cards(frm, preview_data) {
	const $wrapper = frm.get_field("import_warnings")?.$wrapper;
	if (!$wrapper?.length) return;

	$wrapper.find(".diw-row-warning-label").each((_, el) => {
		const $el = $(el);
		$el.data("es-hover-card")?.destroy?.();
		$el.removeData("es-hover-card");
		const row_number = cint(el.getAttribute("data-row"));
		frappe.ui.hover_card($el, {
			side: "bottom",
			align: "start",
			open_delay: 250,
			close_delay: 150,
			css_class: "diw-row-preview-hover-card",
			content: () => build_import_row_preview_table(preview_data, row_number),
		});
	});
}

/** 1-based sheet row numbers marked to skip on the Data Import form. */
function get_skipped_row_set(frm) {
	return new Set((frm.doc.skipped_rows || []).map((row) => cint(row.row_number)));
}

/** Single source of truth for "does this import currently have warnings" — used both to
 *  render them and to decide whether the Fix Issues panel should show the section. */
function get_current_import_warnings(frm, preview_data) {
	preview_data = get_fix_issues_preview_data(frm, preview_data);
	const template_warnings = parse_template_warnings(frm);
	const preview_warnings = preview_data?.warnings || [];
	return dedupe_import_warnings(template_warnings.concat(preview_warnings));
}

function get_fix_issues_preview_data(frm, preview_data) {
	if (preview_data) return preview_data;
	const source_key = get_import_preview_source_key(frm);
	if (frm.import_preview?.data_import_name === frm.doc.name) {
		return frm.import_preview.preview_data;
	}
	// Preview fetch can finish before ImportPreview is constructed (async bundle load).
	if (frm._import_preview_data && frm._import_preview_source_key === source_key) {
		return frm._import_preview_data;
	}
	return null;
}

/** Authoritative Fix Issues panel state — shared by mount logic and the empty state. */
function get_fix_issues_state(frm, preview_data) {
	preview_data = get_fix_issues_preview_data(frm, preview_data);
	const warnings = get_current_import_warnings(frm, preview_data);
	const value_mappings_count = (frm.doc.value_mappings || []).length;
	const skipped_rows_count = (frm.doc.skipped_rows || []).length;
	const is_complete = is_import_complete(frm.doc.status);
	const has_issues =
		!is_complete &&
		(warnings.length > 0 || value_mappings_count > 0 || skipped_rows_count > 0);

	return {
		preview_data,
		warnings,
		warnings_count: warnings.length,
		value_mappings_count,
		skipped_rows_count,
		has_warnings: warnings.length > 0,
		has_mappings: value_mappings_count > 0,
		has_issues,
		is_complete,
	};
}

/** Wait until preview data (and warnings) are available before showing Fix Issues. */
async function ensure_import_preview_ready(frm) {
	if (!frm.has_import_file?.()) {
		return null;
	}

	const source_key = get_import_preview_source_key(frm);
	if (is_import_preview_ready_for_source(frm, source_key)) {
		return get_fix_issues_preview_data(frm);
	}

	if (has_failed_import_preview(frm, source_key)) {
		return null;
	}

	if (frm._import_preview_promise) {
		try {
			return await frm._import_preview_promise;
		} catch (_error) {
			return null;
		}
	}

	try {
		return await frm.events.import_file(frm);
	} catch (_error) {
		return null;
	}
}

/** Sync warnings HTML + issue field visibility before mounting the Fix Issues step. */
function prepare_fix_issues_step(frm, preview_data) {
	const state = get_fix_issues_state(frm, preview_data);
	if (!frm.has_import_file?.() || state.is_complete) {
		frm.events.toggle_import_issues_ui(frm, false, false);
		if (state.is_complete) {
			frm.get_field("import_warnings")?.$wrapper.html("");
		}
		return state;
	}

	frm.events.render_import_warnings(frm, state.preview_data);
	return state;
}

/** Detach reparented field wrappers so jQuery .empty() doesn't destroy their event handlers. */
function detach_fix_issues_fields(frm) {
	for (const fieldname of ["import_warnings", "value_mappings"]) {
		frm.fields_dict[fieldname]?.$wrapper?.detach();
	}
}

/** Mount warnings into the Fix Issues step; Value Mappings sits under Mapping warnings. */
function mount_fix_issues_step(frm, container) {
	const state = prepare_fix_issues_step(frm);
	detach_fix_issues_fields(frm);
	const $content = $(container).empty();

	if (!state.has_issues) {
		return state;
	}

	const $step = $('<div class="diw-fix-issues-step flex flex-col gap-5"></div>');

	// No top "Issues" heading — group headlines live inside the warnings HTML.
	const warnings_field = frm.fields_dict.import_warnings;
	if (warnings_field?.$wrapper?.length && (state.has_warnings || state.has_mappings)) {
		frm.toggle_display("import_warnings", true);
		$step.append(warnings_field.$wrapper);
	}

	if (!$step.children().length) {
		return state;
	}

	$content.append($step);
	place_value_mappings_in_mapping_section(frm, $step);
	return state;
}

/** Move the Value Mappings grid under the Mapping warnings helper text. */
function place_value_mappings_in_mapping_section(frm, $root) {
	const field = frm.fields_dict.value_mappings;
	if (!field?.$wrapper?.length) return;

	const $host = ($root || $(document)).find(".diw-mapping-grid-host").first();
	const has_mappings = (frm.doc.value_mappings || []).length > 0;
	if (!has_mappings || !$host.length) {
		field.$wrapper.detach();
		frm.toggle_display("value_mappings", false);
		return;
	}

	frm.toggle_display("value_mappings", true);
	$host.empty().append(field.$wrapper);
	field.$wrapper.find("> .tooltip-content").remove();
	frm.events.setup_value_mappings_grid(frm);
	field.grid?.refresh?.();
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

function has_import_started(frm) {
	const status = frm.doc?.status;
	return Boolean(frm.import_in_progress || (status && status !== "Pending"));
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

/** Parse ``_server_messages`` into message objects with title + message. */
function parse_server_message_objects(server_messages) {
	if (!server_messages) {
		return [];
	}
	try {
		const raw_messages =
			typeof server_messages === "string" ? JSON.parse(server_messages) : server_messages;
		return raw_messages
			.map((raw) => {
				try {
					return JSON.parse(raw);
				} catch (_e) {
					return { message: raw };
				}
			})
			.filter((entry) => entry?.message);
	} catch (_e) {
		return [];
	}
}

function get_import_preview_error_response(error) {
	return error?.responseJSON || error || frappe.last_response || {};
}

/** User-facing message from a failed preview fetch (Google Sheets, CSV parse, etc.). */
function get_import_preview_error_message(error) {
	const response = get_import_preview_error_response(error);
	const messages = parse_server_message_objects(response?._server_messages);
	if (messages.length) {
		return messages.map((entry) => entry.message).join(" ");
	}

	if (response?._error_message) {
		return response._error_message;
	}

	if (error?.message && typeof error.message === "string") {
		return error.message;
	}

	return __("Failed to load import file");
}

/** Show one modal for preview load failures — no inline duplicate in the upload section. */
function show_import_preview_error(frm, error, source_key) {
	if (frm._import_preview_error_key === source_key) {
		return;
	}
	frm._import_preview_error_key = source_key;

	const response = get_import_preview_error_response(error);
	const messages = parse_server_message_objects(response?._server_messages);
	const first_message = messages[0];
	const message =
		first_message?.message ||
		[...new Set(messages.map((entry) => entry.message).filter(Boolean))][0] ||
		get_import_preview_error_message(error);

	frappe.msgprint({
		title: first_message?.title || __("Could not load import file"),
		message,
		indicator: "red",
		clear: true,
	});
}

function has_failed_import_preview(frm, source_key = get_import_preview_source_key(frm)) {
	return frm._import_preview_failed_source === source_key;
}

function is_failed_import_preview_response(response) {
	return Boolean(response?.exc || response?.exc_type);
}

function get_import_preview_source_key(frm) {
	return [
		frm.doc.import_file || "",
		frm.doc.google_sheets_url || "",
		cint(frm.doc.use_csv_sniffer),
		cint(frm.doc.custom_delimiters),
		frm.doc.delimiter_options || "",
	].join("|");
}

/**
 * Clear snapshotted blocked-import warnings when the import source changes.
 * Otherwise the wizard keeps routing to Fix Issues from the previous file
 * until the next successful save.
 */
function clear_stale_template_warnings_for_source(frm) {
	const source_key = get_import_preview_source_key(frm);
	const prev = frm._diw_template_warnings_source_key;
	if (prev != null && prev !== source_key && frm.doc.template_warnings) {
		frm.doc.template_warnings = "";
	}
	frm._diw_template_warnings_source_key = source_key;
}

function is_import_preview_ready_for_source(frm, source_key = get_import_preview_source_key(frm)) {
	return Boolean(frm._import_preview_ready && frm._import_preview_source_key === source_key);
}

/** Whether refresh / field triggers should auto-fetch the import preview. */
function should_auto_import_preview(frm, source_key = get_import_preview_source_key(frm)) {
	// get_preview_from_template needs a real doc name — never call it on unsaved docs.
	if (frm.is_new?.()) {
		return false;
	}
	if (!frm.has_import_file?.()) {
		return false;
	}
	if (should_defer_auto_import_preview(frm)) {
		return false;
	}
	if (has_failed_import_preview(frm, source_key)) {
		return false;
	}
	return !is_import_preview_ready_for_source(frm, source_key);
}

/** Block background preview fetches while Save/Next is driving navigation. */
function should_defer_auto_import_preview(frm) {
	return Boolean(frm._skip_refresh_import_file || frm._wizard_navigation_in_progress);
}

/**
 * Save a dirty/new Data Import before wizard navigation.
 * Returns false on failure so the caller must not advance — frm.save() swallows
 * rejections, so we also treat still-dirty / still-new as failure.
 */
async function save_wizard_form_if_needed(frm) {
	if (!frm.is_dirty() && !frm.is_new()) {
		return true;
	}

	let failed = false;
	try {
		await frm.save(
			null,
			(r) => {
				if (r?.exc) {
					failed = true;
				}
			},
			null,
			() => {
				failed = true;
			}
		);
	} catch (_error) {
		failed = true;
	}

	if (failed || frm.is_dirty() || frm.is_new()) {
		return false;
	}
	return true;
}

function table_preview_has_rendered_content(wrapper_el) {
	if (!wrapper_el) return false;
	return Boolean(wrapper_el.querySelector(".dt-scrollable, .datatable"));
}

function tree_preview_has_rendered_content(wrapper_el) {
	if (!wrapper_el) return false;
	return Boolean(wrapper_el.querySelector(".import-tree-box, .tree-node, .tree-link"));
}

function get_import_log_skeleton_html() {
	const sk = (width, height = "14px", css_class = "rounded") =>
		frappe.ui.skeleton.html({ width, height, css_class });
	return `<div class="flex flex-col gap-3 w-full" aria-busy="true" aria-label="${frappe.utils.escape_html(
		__("Loading import log")
	)}">
		<div class="diw-import-log-metrics mb-3 w-full border rounded-md overflow-hidden bg-surface-base" role="list">
			${[0, 0, 0]
				.map(
					() =>
						`<div class="diw-import-log-metric flex flex-col items-center justify-center text-center gap-1 min-w-0 min-h-20 px-3 py-3">${sk(
							"48px",
							"28px"
						)}${sk("72px", "13px")}</div>`
				)
				.join("")}
		</div>
		<div class="flex gap-2">${sk("72px", "28px", "rounded-full")}${sk(
		"96px",
		"28px",
		"rounded-full"
	)}${sk("80px", "28px", "rounded-full")}</div>
		<div class="border rounded overflow-hidden p-2 flex flex-col gap-2">
			${Array.from({ length: 8 }, () => sk("100%", "32px")).join("")}
		</div>
	</div>`;
}

function get_table_preview_skeleton_html() {
	const sk = (width, height = "14px") =>
		frappe.ui.skeleton.html({ width, height, css_class: "rounded" });
	const row = () => sk("100%", "32px");
	return `<div class="flex flex-col gap-2 w-full" data-fallback-skeleton="table" role="status" aria-busy="true" aria-label="${frappe.utils.escape_html(
		__("Loading import preview...")
	)}">
		<div class="flex items-center justify-between gap-2">
			${sk("128px", "30px")}${sk("170px", "16px")}
		</div>
		<div class="border rounded overflow-hidden p-2 flex flex-col gap-2">
			${sk("100%", "28px")}${Array.from({ length: 8 }, row).join("")}
		</div>
	</div>`;
}

function get_tree_preview_skeleton_html() {
	const sk = (width, height = "14px", extra = "") =>
		frappe.ui.skeleton.html({ width, height, css_class: `rounded ${extra}`.trim() });
	return `<div class="flex flex-col gap-3 w-full" data-fallback-skeleton="tree" role="status" aria-busy="true" aria-label="${frappe.utils.escape_html(
		__("Loading tree preview...")
	)}">
		<div class="flex gap-2">${sk("148px", "24px")}${sk("96px", "24px")}</div>
		${sk("88%")}${sk("78%", "14px", "ms-4")}${sk("68%", "14px", "ms-8")}${sk("78%", "14px", "ms-4")}
	</div>`;
}

function update_preview_loading_skeleton(frm, loading) {
	const table_wrapper = frm.get_field("import_preview")?.$wrapper?.get(0);
	const tree_wrapper = frm.get_field("import_tree_preview")?.$wrapper?.get(0);

	if (!table_wrapper && !tree_wrapper) return;

	if (!loading) {
		table_wrapper
			?.querySelectorAll("[data-fallback-skeleton='table']")
			?.forEach((el) => el.remove());
		tree_wrapper
			?.querySelectorAll("[data-fallback-skeleton='tree']")
			?.forEach((el) => el.remove());
		return;
	}

	if (table_wrapper && !table_preview_has_rendered_content(table_wrapper)) {
		if (!table_wrapper.querySelector("[data-fallback-skeleton='table']")) {
			table_wrapper.insertAdjacentHTML("beforeend", get_table_preview_skeleton_html());
		}
	}

	const is_tree_doctype = is_tree_reference_doctype(frm);
	if (is_tree_doctype && tree_wrapper && !tree_preview_has_rendered_content(tree_wrapper)) {
		// Field stays hidden until tree_preview arrives; force it visible so the Tree tab
		// shows a skeleton instead of an empty pane while the preview fetch is in flight.
		frm.toggle_display("import_tree_preview", true);
		frm.toggle_display("section_import_tree_preview", true);
		if (!tree_wrapper.querySelector("[data-fallback-skeleton='tree']")) {
			tree_wrapper.insertAdjacentHTML("beforeend", get_tree_preview_skeleton_html());
		}
	}
}

/** Sync desk + wizard loading state for the import preview fetch. */
function set_import_preview_loading(frm, loading) {
	const is_loading = Boolean(loading);
	frm._import_preview_loading = is_loading;
	update_preview_loading_skeleton(frm, is_loading);
	frm._data_import_wizard?.set_preview_loading?.(is_loading);
}

/** True when preview data includes tree preview payload for a tree DocType. */
function is_tree_import_preview(frm, preview_data) {
	if (!is_tree_reference_doctype(frm)) {
		return false;
	}
	return Boolean(preview_data?.tree_preview);
}

/** Mount preview fields into a pane; skip when already mounted to avoid table reflow. */
function append_preview_pane_fields(frm, parent_el, fieldnames, shell_class = "") {
	if (!parent_el) return { mounted: false, reparented: false };

	const first_field = frm.fields_dict[fieldnames[0]];
	const wrapper_el = first_field?.$wrapper?.get(0);
	const existing_shell = parent_el.querySelector(`.diw-preview-field-shell.${shell_class}`);
	if (wrapper_el && existing_shell?.contains(wrapper_el)) {
		return { mounted: true, reparented: false };
	}

	const $parent = $(parent_el).empty();
	const $shell = $(`
		<div class="form-section diw-preview-field-shell ${shell_class}">
			<div class="section-body">
				<div class="form-column col-sm-12"></div>
			</div>
		</div>
	`);
	const $column = $shell.find(".form-column");
	let appended = false;
	for (const fieldname of fieldnames) {
		const field = frm.fields_dict[fieldname];
		if (field?.$wrapper?.length) {
			// Reparented fields must be visible — wizard panes own layout, not desk hide-control.
			frm.toggle_display(fieldname, true);
			$column.append(field.$wrapper);
			appended = true;
		}
	}
	if (appended) {
		$parent.append($shell);
	}
	return { mounted: appended, reparented: appended };
}

/** Re-render table preview after wizard reparents fields into the visible pane. */
function refresh_wizard_table_preview(frm, { force = false } = {}) {
	const preview = frm.import_preview;
	if (!preview?.preview_data) return;

	frm._wizard_table_preview_dirty = true;
	frm._wizard_table_preview_force = frm._wizard_table_preview_force || force;
	if (frm._wizard_table_preview_raf) return;

	// Double rAF: wait for reparented pane layout before measuring column widths.
	frm._wizard_table_preview_raf = requestAnimationFrame(() => {
		frm._wizard_table_preview_raf = requestAnimationFrame(() => {
			frm._wizard_table_preview_raf = null;
			if (!frm._wizard_table_preview_dirty) return;
			const should_force = frm._wizard_table_preview_force;
			frm._wizard_table_preview_dirty = false;
			frm._wizard_table_preview_force = false;
			if (!preview.preview_data || !preview.$table_preview?.length) return;
			preview.render_datatable_if_needed?.(should_force);
		});
	});
}

frappe.ui.form.on("Data Import", {
	setup(frm) {
		frappe.realtime.on("data_import_refresh", ({ data_import }) => {
			if (data_import !== frm.doc.name) return;
			frm.import_in_progress = false;
			frm._wizard_import_progress = null;
			frappe.model.clear_doc("Data Import", frm.doc.name);
			frappe.model.with_doc("Data Import", frm.doc.name).then(() => {
				frm.refresh();
			});
		});
		frappe.realtime.on("data_import_blocked", ({ data_import }) => {
			if (data_import !== frm.doc.name) return;
			frm.import_in_progress = false;
			frm._wizard_import_progress = null;
			frappe.show_alert({
				message: __(
					"Import could not start. Please resolve the errors in the import file."
				),
				indicator: "red",
			});
			frm.dashboard?.hide_progress?.();
			// The blocked attempt stores fresh warnings in template_warnings via db_set —
			// reload so they render without a manual refresh, then land on Fix Issues.
			frm.reload_doc().then(() => {
				frm.events.go_to_wizard_step(frm, 2);
				frm.trigger("update_primary_action");
			});
		});
		frappe.realtime.on("data_import_progress", (data) => {
			// Guard first: the desk reuses one frm across documents, so an event for a
			// different import must not mark this one as running.
			if (data.data_import !== frm.doc.name) {
				return;
			}
			frm.import_in_progress = true;
			const prev_progress = frm._wizard_import_progress || {};
			let percent = Math.floor((data.current * 100) / data.total);
			let eta_seconds = Number.isFinite(Number(data.eta))
				? Math.max(Math.floor(data.eta), 0)
				: 0;
			let seconds = eta_seconds;
			let minutes = Math.floor(eta_seconds / 60);
			let eta_message =
				// prettier-ignore
				seconds < 60
					? __('About {0} seconds remaining', [seconds])
					: minutes === 1
						? __('About {0} minute remaining', [minutes])
						: __('About {0} minutes remaining', [minutes]);

			const prev_activity = Array.isArray(prev_progress.recent_activity)
				? prev_progress.recent_activity
				: [];
			const incoming_activity = data.activity?.text
				? {
						kind: data.activity.kind || "info",
						text: data.activity.text,
						is_html: Boolean(data.activity.is_html),
						row: cint(data.row_indexes?.[0]) || null,
				  }
				: null;
			let recent_activity = prev_activity;
			if (incoming_activity) {
				const latest = prev_activity[0];
				const is_duplicate_latest =
					latest &&
					latest.kind === incoming_activity.kind &&
					latest.text === incoming_activity.text &&
					Boolean(latest.is_html) === Boolean(incoming_activity.is_html);
				recent_activity = is_duplicate_latest
					? prev_activity.slice(0, 5)
					: [incoming_activity].concat(prev_activity).slice(0, 5);
			}

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
			frm._wizard_import_progress = {
				title: __("Importing your data"),
				subtitle: __(
					"You can continue other work while this runs. Progress updates will appear here."
				),
				percent,
				message,
				current: cint(data.current),
				total: cint(data.total),
				eta_message,
				status_line:
					cint(data.current) >= cint(data.total) ? __("Finishing up...") : eta_message,
				inserted: Number.isFinite(Number(data.inserted))
					? cint(data.inserted)
					: cint(prev_progress.inserted),
				updated: Number.isFinite(Number(data.updated))
					? cint(data.updated)
					: cint(prev_progress.updated),
				failed: Number.isFinite(Number(data.failed))
					? cint(data.failed)
					: cint(prev_progress.failed),
				recent_activity,
			};
			// A large import emits one event per row (thousands of them). Repainting the
			// dashboard, stepper, footer and progress hero on each one saturates the main
			// thread and the wizard stops responding to clicks — so coalesce the DOM work
			// onto the next frame and paint from the latest state instead of every event.
			frm._diw_pending_progress = { percent, message };
			if (!frm._diw_progress_raf) {
				frm._diw_progress_raf = requestAnimationFrame(() => {
					frm._diw_progress_raf = null;
					const pending = frm._diw_pending_progress;
					if (!pending || !frm.import_in_progress) return;

					frm.dashboard.show_progress(
						__("Import Progress"),
						pending.percent,
						pending.message
					);
					frm.page.set_indicator(__("In Progress"), "orange");
					frm.trigger("update_primary_action");
					if (cint(frm.wizard_step) === 3) {
						frm.trigger("show_import_log");
					}
					frm.events.refresh_wizard_ui?.(frm);
				});
			}
			// Completion transition is handled by data_import_refresh realtime event.
		});

		frm.set_query("reference_doctype", () => {
			return {
				filters: {
					name: ["in", frappe.boot.user.can_import],
				},
			};
		});

		// Build upload notes with max size from system settings
		const max_bytes = frappe.boot?.max_file_size;
		const max_mb = max_bytes ? Math.round(max_bytes / (1024 * 1024)) : null;

		frm.get_field("import_file").df.options = {
			restrictions: {
				allowed_file_types: [".csv", ".xls", ".xlsx"],
			},
			upload_notes: max_mb ? __(".csv, .xlsx up to {0} MB", [max_mb]) : __(".csv, .xlsx"),
		};

		frm.has_import_file = () => {
			return frm.doc.import_file || frm.doc.google_sheets_url;
		};

		frm.has_import_started = () => has_import_started(frm);
		frm.is_tree_doctype = () => is_tree_reference_doctype(frm);

		$(frm.wrapper).on("dirty", () => {
			frm.trigger("update_primary_action");
		});

		frm.events.setup_skip_row_handlers(frm);
		if (!frm._custom_ui_hooks) {
			frm._custom_ui_hooks = true;
			frm.events.hook_wizard_dashboard(frm);
		}
		frappe.require("data_import_wizard.bundle.js");
	},

	onload(frm) {
		set_import_preview_loading(frm, false);
		frm._import_preview_promise = null;
		if (!frm.has_import_file()) {
			frm.events.reset_import_ui_state(frm);
		}
	},

	/** The desk reuses a single frm across documents, and `onload` only fires the first
	 *  time each doc is opened (frappe caches them in `opendocs`) — so switching docs, or
	 *  returning to an earlier one, would otherwise keep the previous document's preview
	 *  state: its cached rows and rendered table (showing doc A's data under doc B), and
	 *  its in-flight `_import_preview_promise`, which the new doc would adopt and then
	 *  discard as stale — leaving the preview stuck on the loading skeleton forever.
	 *  Detect the switch here (refresh runs on every one) and drop that state; the
	 *  `should_auto_import_preview` check below then re-fetches for this document. */
	reset_stale_document_state(frm) {
		const docname = frm.doc?.name || null;
		const prev = frm._diw_loaded_docname;
		if (prev === docname) return;

		// First save renames new-* → real name on the same form — not a doc switch.
		const is_first_save_rename =
			prev &&
			String(prev).startsWith("new-") &&
			docname &&
			!String(docname).startsWith("new-");

		frm._diw_loaded_docname = docname;
		if (is_first_save_rename) {
			return;
		}

		frm.events.reset_import_ui_state(frm);
		frm._wizard_import_progress = null;
		frm._import_log_filter = null;
		frm._import_log_total_count = null;
		frm._diw_template_warnings_source_key = null;
		// Let the wizard recompute the landing step for this document.
		frm.wizard_step = null;
	},

	after_save(frm) {
		clear_stale_template_warnings_for_source(frm);
		if (cint(frm.wizard_step) === 2) {
			frm._data_import_wizard?.refresh_fix_issues?.();
		}
		// Column remap only dirties template_options; refresh preview after Save.
		if (frm._diw_column_map_dirty) {
			frm._diw_column_map_dirty = false;
			frm.events.import_file(frm, { force: true });
			return;
		}
		// File may have been attached while the doc was still new — preview was deferred.
		if (should_auto_import_preview(frm)) {
			frm.trigger("import_file");
		}
	},

	refresh(frm) {
		// Must run before anything reads/derives preview state below.
		frm.events.reset_stale_document_state(frm);
		frm.page.hide_icon_group();
		frm.trigger("update_indicators");
		// Status is db_set in the worker — the client doc stays Pending until reload.
		// Keep a client-started run alive across refresh so the navbar and Import step
		// do not briefly treat the job as idle.
		const status_running = frm.doc.status === "In Progress";
		const client_starting = Boolean(frm.import_in_progress && frm.doc.status === "Pending");
		const is_import_running = status_running || client_starting;
		frm.import_in_progress = is_import_running;
		if (is_import_running) {
			frm._wizard_import_progress = frm._wizard_import_progress || {
				title: __("Importing your data"),
				subtitle: __(
					"You can continue other work while this runs. Progress updates will appear here."
				),
				percent: null,
				message: __("Import is running. Progress updates will appear shortly."),
				status_line: __("Fetching latest status..."),
				inserted: 0,
				updated: 0,
				failed: 0,
			};
			frm.events.refresh_import_progress_counts(frm);
			frm.events.refresh_wizard_ui?.(frm);
		} else {
			frm._wizard_import_progress = null;
		}
		const source_key = get_import_preview_source_key(frm);
		if (!frm._skip_refresh_import_file && should_auto_import_preview(frm, source_key)) {
			frm.trigger("import_file");
		}
		frm.trigger("show_import_log");
		frm.trigger("toggle_submit_after_import");

		if (frm.doc.status != "Pending") frm.trigger("show_import_status");

		// Footer Cancel / Report Error / Retry are refreshed via refresh_wizard_ui.
		frm.events.refresh_wizard_ui?.(frm);

		// "Go to List" moved onto the Total rows metric in the import log (see render_import_log).

		frm.trigger("render_custom_ui");
		frm.trigger("update_primary_action");
		// Preview is often already cached after import, so import_file is skipped —
		// refresh Map columns visibility from the new status without a re-fetch.
		if (is_import_complete(frm.doc.status)) {
			frm.import_preview?.add_actions?.();
		}
	},

	/** Mount the wizard on the form view; std layout stays hidden for field logic. */
	render_custom_ui(frm) {
		if (!frm.page?.main?.length) return;

		const $main = frm.page.main;
		$main.addClass("data-import-custom-page flex flex-col flex-1");
		// Tag the page shell (which also holds .page-actions) so the SCSS can hide the
		// standard navbar Save button here — every action lives in the wizard footer /
		// import-log metrics, and Ctrl/Cmd+S still saves via page.save_action.
		frm.page.wrapper?.addClass?.("data-import-custom-shell");
		$main.closest(".layout-main-section-wrapper").addClass("data-import-custom-wrapper");

		const hide_std_form = () => {
			frm.form_wrapper?.addClass("data-import-std-form").hide();
			frm.layout?.wrapper?.hide();
		};
		const show_std_form = () => {
			frm.form_wrapper?.removeClass("data-import-std-form").show();
			frm.layout?.wrapper?.show();
		};

		let $mount = $main.find(".data-import-wizard-root");
		if (!$mount.length) {
			$mount = $(
				'<div class="data-import-wizard-root flex flex-1 w-full min-h-0"></div>'
			).prependTo($main);
		}

		const mount_wizard = () => {
			try {
				if (frm._data_import_wizard?.frm === frm) {
					frm._data_import_wizard.refresh_from_frm();
				} else {
					frm._data_import_wizard?.unmount?.();
					frm._data_import_wizard = new frappe.ui.DataImportWizard({
						wrapper: $mount[0],
						frm,
					});
					frm._data_import_wizard.frm = frm;
				}
				hide_std_form();
			} catch (error) {
				console.error("Data Import wizard mount failed", error);
				show_std_form();
				frappe.show_alert({
					message: __(
						"Failed to load the import wizard. Please hard-refresh and try again."
					),
					indicator: "red",
				});
			}
		};

		// The wizard reads is_tree off the reference DocType meta to choose the tree vs
		// flat preview. That meta isn't loaded by the doc itself, so load it before
		// mounting — otherwise a tree import first paints the flat table-only layout and
		// the Tree/Table tabs pop in a couple seconds later on the next re-render.
		// with_doctype calls back synchronously once the meta is cached, so there's no
		// delay after the first load.
		const mount_wizard_with_meta = () => {
			const ref_dt = frm.doc?.reference_doctype;
			if (ref_dt) {
				frappe.model.with_doctype(ref_dt, mount_wizard);
			} else {
				mount_wizard();
			}
		};

		if (frappe.ui.DataImportWizard) {
			mount_wizard_with_meta();
		} else {
			frappe.require("data_import_wizard.bundle.js", () => {
				if (!frappe.ui.DataImportWizard) {
					frappe.show_alert({
						message: __("Failed to load the import wizard bundle."),
						indicator: "red",
					});
					return;
				}
				mount_wizard_with_meta();
			});
		}
	},

	/** Mount Preview step panels (tree + table); tree tab only for tree DocTypes. */
	mount_preview_step(frm, { tree_el, table_el }) {
		const is_tree_doctype = is_tree_reference_doctype(frm);

		// import_preview is declared before section_import_preview in the DocType, so mount
		// fields directly — section wrappers are often empty or contain the wrong fields.
		if (is_tree_doctype) {
			const { reparented: tree_reparented } = append_preview_pane_fields(
				frm,
				tree_el,
				["import_tree_preview"],
				"data-import-tree-preview-section"
			);
			const preview_data =
				frm._import_preview_data ||
				frm.import_tree_preview?.preview_data ||
				frm.import_preview?.preview_data;
			if (tree_reparented && preview_data?.tree_preview) {
				if (frm.import_tree_preview?.refresh) {
					frm.import_tree_preview.refresh();
				} else {
					frm.events.show_import_tree_preview(frm, preview_data);
				}
			}
		} else if (tree_el) {
			$(tree_el).empty();
		}

		const { reparented: table_reparented } = append_preview_pane_fields(
			frm,
			table_el,
			["import_preview"],
			"data-import-preview-section"
		);

		frm.layout?.sections_dict?.section_import_tree_preview?.collapse(false);
		frm.layout?.sections_dict?.section_import_preview?.collapse(false);

		if (frm.has_import_file?.()) {
			refresh_wizard_table_preview(frm, { force: table_reparented });
			// Preview DOM is reused across steps; refresh actions so Map columns hides
			// after Success / Partial Success without a full page reload.
			frm.import_preview?.add_actions?.();
		}

		// Re-apply after remount — loading may have started while fields were still in
		// the hidden form layout, or the Tree tab may have been empty on first paint.
		if (frm._import_preview_loading) {
			update_preview_loading_skeleton(frm, true);
		}
	},

	refresh_wizard_table_preview(frm) {
		refresh_wizard_table_preview(frm);
	},

	/** Reparent import-log fields into the Import step container. */
	mount_import_step(frm, container) {
		const $content = $(container).empty();
		for (const fieldname of IMPORT_STEP_FIELDS) {
			const field = frm.fields_dict[fieldname];
			if (field?.$wrapper?.length) {
				$content.append(field.$wrapper);
			}
		}
	},

	async ensure_import_preview_ready(frm) {
		return ensure_import_preview_ready(frm);
	},

	mount_fix_issues_step(frm, container) {
		return mount_fix_issues_step(frm, container);
	},

	hook_wizard_dashboard(frm) {
		const dashboard = frm.dashboard;
		if (!dashboard || dashboard._wizard_hooks) return;
		dashboard._wizard_hooks = true;

		const sync = () => frm.events.refresh_wizard_ui(frm);

		const show_progress = dashboard.show_progress.bind(dashboard);
		dashboard.show_progress = (...args) => {
			show_progress(...args);
			sync();
		};

		const hide = dashboard.hide.bind(dashboard);
		dashboard.hide = (...args) => {
			hide(...args);
			sync();
		};

		const set_headline = dashboard.set_headline.bind(dashboard);
		dashboard.set_headline = (...args) => {
			set_headline(...args);
			sync();
		};
	},

	async handle_wizard_go_to_step(frm, target_step, from_step = frm.wizard_step) {
		target_step = cint(target_step);
		from_step = cint(from_step);
		if (!Number.isFinite(target_step) || !Number.isFinite(from_step)) {
			return false;
		}

		if (target_step <= from_step) {
			frm.events.go_to_wizard_step(frm, target_step);
			return true;
		}

		try {
			frm._skip_refresh_import_file = true;
			frm._wizard_navigation_in_progress = true;

			// Save-if-dirty before advancing; stay put when save fails or validation errors.
			if (!(await save_wizard_form_if_needed(frm))) {
				return false;
			}

			if (target_step >= 1) {
				if (!frm.doc.reference_doctype || !frm.doc.import_type) {
					frappe.msgprint(__("Please select Document Type and Import Type."));
					return false;
				}
			}

			if (from_step === 0 && target_step >= 1 && !frm.has_import_file?.()) {
				frappe.msgprint(
					__("Please attach an import file or provide a Google Sheets URL.")
				);
				return false;
			}

			if (from_step <= 1 && target_step >= 2 && !frm.has_import_file?.()) {
				frappe.msgprint(
					__("Please attach an import file or provide a Google Sheets URL.")
				);
				return false;
			}

			const should_navigate_before_preview_fetch =
				from_step === 0 && target_step === 1 && frm.has_import_file?.();

			if (should_navigate_before_preview_fetch) {
				frm.events.go_to_wizard_step(frm, target_step);
			}

			if (target_step >= 1 && frm.has_import_file?.()) {
				const source_key = get_import_preview_source_key(frm);
				const preview_ready = is_import_preview_ready_for_source(frm, source_key);

				if (!preview_ready) {
					if (has_failed_import_preview(frm, source_key)) {
						show_import_preview_error(frm, frm._import_preview_last_error, source_key);
						return false;
					}
					try {
						await frm.events.import_file(frm, { force: true });
					} catch (_error) {
						return false;
					}
				}

				if (!is_import_preview_ready_for_source(frm, source_key)) {
					if (has_failed_import_preview(frm, source_key)) {
						show_import_preview_error(frm, frm._import_preview_last_error, source_key);
					}
					return false;
				}
			}

			if (target_step === 3 && !has_import_started(frm)) {
				frappe.show_alert({
					message: __("Start the import before opening the Import step."),
					indicator: "orange",
				});
				return false;
			}

			if (!should_navigate_before_preview_fetch) {
				frm.events.go_to_wizard_step(frm, target_step);
			}

			// Step transition + async preview mount can race in new docs; force one
			// extra render pass so table rows appear without manual refresh.
			if (target_step === 1 && frm.has_import_file?.()) {
				setTimeout(() => {
					refresh_wizard_table_preview(frm, { force: true });
				}, 0);
			}
			return true;
		} catch (_error) {
			return false;
		} finally {
			frm._skip_refresh_import_file = false;
			frm._wizard_navigation_in_progress = false;
		}
	},

	async handle_wizard_apply(frm) {
		if (frm.is_dirty()) {
			frappe.show_alert({
				message: __("Save your changes before importing."),
				indicator: "orange",
			});
			return false;
		}
		// Navigate before start_import settles. When the job runs inline rather than on a
		// worker (developer_mode, or an inactive scheduler), the call only returns once every
		// row is imported — gating navigation on it pinned the wizard on Fix Issues, looking
		// frozen, for the whole run. A run stopped by prechecks is corrected by the
		// `data_import_blocked` handler, which resets this state and returns to Fix Issues.
		frm.events.begin_import(frm);
		return true;
	},

	/** Fix Issues footer Save — persist dirty changes; do not start the import. */
	async handle_wizard_save(frm) {
		const ok = await save_wizard_form_if_needed(frm);
		if (!ok) {
			return false;
		}
		if (frm.has_import_file?.()) {
			frm.trigger("import_file");
		}
		return true;
	},

	/**
	 * Mark the import as started, paint progress UI, open the Import step, then enqueue.
	 * Shared by the wizard footer Import and the navbar Start Import / Retry actions.
	 */
	begin_import(frm) {
		frm.import_in_progress = true;
		frm._wizard_import_progress = {
			title: __("Importing your data"),
			subtitle: __(
				"You can continue other work while this runs. Progress updates will appear here."
			),
			percent: 0,
			message: __("Starting import..."),
			status_line: __("Preparing import..."),
			inserted: 0,
			updated: 0,
			failed: 0,
		};
		frm.dashboard?.show_progress?.(__("Import Progress"), 0, __("Starting import..."));
		// Paint progress into the log field before the wizard reparents it on step 3,
		// so we never flash the empty after-import log that refresh may have left there.
		frm.events.render_import_progress_state(frm);
		frm.page.clear_primary_action();
		frm.page.set_indicator(__("In Progress"), "orange");
		frm.events.go_to_wizard_step(frm, 3);
		frm.events.refresh_wizard_ui?.(frm);
		frm.trigger("update_primary_action");
		frm.events.start_import(frm);
	},

	go_to_wizard_step(frm, step) {
		step = cint(step);
		if (!Number.isFinite(step)) {
			step = 0;
		}
		step = Math.max(0, Math.min(step, WIZARD_STEP_COUNT - 1));
		frm.wizard_step = step;
		if (step === 2 && frm.has_import_file?.()) {
			prepare_fix_issues_step(frm);
		}
		frm._data_import_wizard?.set_step?.(step);
		if (step === 1) {
			refresh_wizard_table_preview(frm);
		}
	},

	refresh_wizard_ui(frm) {
		frm._data_import_wizard?.bump_ui?.();
		const step = frm.wizard_step;
		const can_import =
			!frm.is_new() && frm.has_import_file?.() && frm.doc.status !== "Success";
		if (step === 2 && can_import && !frm.is_dirty()) {
			frm.page.clear_primary_action();
		}
	},

	onload_post_render(frm) {
		frm.trigger("render_custom_ui");
		if (frm.wizard_step === 0) {
			frm.layout?.refresh_dependency();
			frm._data_import_wizard?.refresh_from_frm?.();
		}
		frm.trigger("update_primary_action");
	},

	update_primary_action(frm) {
		// The navbar stays clean (only Search). Every action lives in the wizard footer
		// (Back / Next / Save / Import / Cancel / Retry / Report Error) or on the import-log
		// metrics. We only keep Ctrl/Cmd+S saving by routing frappe.app's primary-action
		// shortcut to a Save handler via page.save_action (btn_primary is intentionally
		// cleared, so trigger_primary_action falls through to save_action).
		frm.page.clear_primary_action();
		// Ctrl/Cmd+S → frappe.app.trigger_primary_action(), which (with no visible primary
		// button) falls back to `frappe.container.page.save_action`. That property lives on
		// the page DOM element — NOT frm.page (the frappe.ui.Page instance) — so set it there.
		if (frappe.container?.page) {
			frappe.container.page.save_action = () =>
				frm.save().then(() => {
					// Re-fetch the preview only while still editing (before the import starts).
					if (frm.has_import_file?.() && !has_import_started(frm)) {
						frm.trigger("import_file");
					}
				});
		}

		const importing = frm.doc.status === "In Progress" || frm.import_in_progress;
		if (importing || frm.doc.status === "Success") {
			frm.disable_save();
		} else {
			frm.enable_save();
		}

		frm.events.refresh_wizard_ui?.(frm);
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

				// Export Errored / Download Skipped now live on the Failed / Skipped metrics
				// in the import log (see render_import_log), not on the navbar.
				if (failed_records > 0) {
					message +=
						"<br/>" +
						__(
							"Use 'Export Errored Rows' on the Failed metric, fix the errors and import again."
						);
				}

				if ((frm.doc.skipped_rows || []).length) {
					message +=
						"<br/>" +
						__(
							"Use 'Download Skipped Rows' on the Skipped metric to export the skipped rows."
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

	// Cancel Import lives in the wizard footer (Import step). The action is `cancel_import`.
	cancel_import(frm) {
		frappe.confirm(
			__("This will terminate the job immediately and might be dangerous, are you sure?"),
			() => {
				frappe
					.xcall("frappe.core.doctype.data_import.data_import.stop_data_import", {
						doc_name: frm.doc.name,
					})
					.then((response) => {
						if (response?.status === "not_running") {
							// Job already finished or worker crashed — server still
							// transitioned orphaned "In Progress" to "Error".
							frappe.show_alert({
								message: __("Job was not running; status updated."),
								indicator: "orange",
							});
						} else {
							frappe.show_alert(__("Job Stopped Successfully"));
						}
						// Always reload to show the updated status from the server.
						frm.reload_doc();
					});
			}
		);
	},

	// Report Error lives in the wizard footer when status === "Error".
	report_error_now(frm) {
		frappe.db
			.get_list("Error Log", {
				filters: { method: frm.doc.name },
				fields: ["method", "error"],
				order_by: "creation desc",
				limit: 1,
			})
			.then((result) => {
				if (result.length > 0) {
					const fake_xhr = {
						responseText: JSON.stringify({ exc: result[0].error }),
					};
					frappe.request.report_error(fake_xhr, {});
				} else {
					frappe.show_alert(__("No error log found for this import."));
				}
			});
	},

	start_import(frm) {
		return frm
			.call({
				method: "form_start_import",
				args: { data_import: frm.doc.name },
				btn: frm.page.btn_primary,
			})
			.then((r) => {
				const started = r.message === true;
				if (started) {
					frm.disable_save();
				}
				return started;
			})
			.catch(() => false);
	},

	get_import_provider_schema(frm) {
		const doctype = frm.doc.reference_doctype;
		if (!doctype) {
			return Promise.resolve(null);
		}

		if (frm._data_import_provider_schema_doctype === doctype) {
			if (Object.prototype.hasOwnProperty.call(frm, "_data_import_provider_schema")) {
				return Promise.resolve(frm._data_import_provider_schema || null);
			}
			if (frm._data_import_provider_schema_promise) {
				return frm._data_import_provider_schema_promise;
			}
		}

		frm._data_import_provider_schema_doctype = doctype;
		const schema_request = Promise.resolve(
			frappe.call({
				method: "frappe.core.doctype.data_import.data_import.get_import_fields",
				args: { doctype },
			})
		);

		frm._data_import_provider_schema_promise = schema_request
			.then((r) => {
				frm._data_import_provider_schema = r.message || null;
				return frm._data_import_provider_schema;
			})
			.catch(() => {
				frm._data_import_provider_schema = null;
				return null;
			})
			.then((result) => {
				frm._data_import_provider_schema_promise = null;
				return result;
			});

		return frm._data_import_provider_schema_promise;
	},

	download_template(frm) {
		frappe.require("data_import_tools.bundle.js", () => {
			const create_exporter = (provider_schema = null) => {
				frm.data_exporter = new frappe.data_import.DataExporter(
					frm.doc.reference_doctype,
					frm.doc.import_type,
					"CSV",
					false,
					provider_schema
				);
			};

			frm.events.get_import_provider_schema(frm).then((provider_schema) => {
				create_exporter(provider_schema);
			});
		});
	},

	reference_doctype(frm) {
		frm.trigger("toggle_submit_after_import");
		// Remount Config so the upload dropzone appears once Doc Type is set.
		if (cint(frm.wizard_step) === 0) {
			frm._data_import_wizard?.set_step?.(0, { force: true });
		}
	},

	import_type(frm) {
		if (cint(frm.wizard_step) === 0) {
			frm._data_import_wizard?.set_step?.(0, { force: true });
		}
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
		const source_key = get_import_preview_source_key(frm);
		const source_changed = frm._diw_google_sheets_preview_source !== source_key;

		// Save / re-render can re-fire this handler for the same URL — don't wipe error
		// state or start a second preview fetch (that produced duplicate modals).
		if (source_changed) {
			clear_stale_template_warnings_for_source(frm);
			frm._diw_google_sheets_preview_source = source_key;
			frm._import_preview_error = null;
			frm._import_preview_error_key = null;
			frm._import_preview_request_source = null;
			frm._import_preview_failed_source = null;
			frm._import_preview_last_error = null;
			frm._import_preview_ready = false;
			frm._import_preview_source_key = null;
		}
		frm._data_import_wizard?.bump_ui?.();

		if (!frm.is_dirty() && should_auto_import_preview(frm, source_key)) {
			frm.trigger("import_file");
		} else {
			frm.trigger("update_primary_action");
		}
	},

	custom_delimiters(frm) {
		frm.layout?.refresh_dependency();
		$(frm.wrapper).trigger("refresh-fields");
		frm._data_import_wizard?.bump_ui?.();
	},

	refresh_google_sheet(frm) {
		// Sheet data can change without a URL change — drop blocked-import snapshots.
		if (frm.doc.template_warnings) {
			frm.doc.template_warnings = "";
		}
		frm._import_preview_failed_source = null;
		frm._import_preview_last_error = null;
		frm._import_preview_error_key = null;
		frm._import_preview_force_reload = true;
		frm.trigger("import_file");
	},

	reset_import_ui_state(frm) {
		// Invalidate any in-flight preview fetch so stale async responses are ignored.
		frm._import_preview_request_id = (frm._import_preview_request_id || 0) + 1;
		frm._import_preview_promise = null;
		frm._import_preview_error = null;
		frm._import_preview_error_key = null;
		frm._import_preview_request_source = null;
		frm._import_preview_failed_source = null;
		frm._import_preview_last_error = null;
		frm._import_preview_ready = false;
		frm._import_preview_source_key = null;
		frm._import_preview_data = null;
		set_import_preview_loading(frm, false);
		frm._diw_google_sheets_preview_source = null;
		frm.import_preview = null;
		frm.import_tree_preview = null;
		const grid = frm.fields_dict.value_mappings?.grid;
		if (grid?._value_mapping_scroll_handler) {
			document.removeEventListener("scroll", grid._value_mapping_scroll_handler, true);
			delete grid._value_mapping_scroll_handler;
		}
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
		for (const fieldname of ["import_log_heading", "import_log_preview"]) {
			frm.toggle_display(fieldname, show);
		}
	},

	set_import_log_heading(frm, title, is_skeleton = false) {
		const $wrapper = frm.get_field("import_log_heading")?.$wrapper;
		if (!$wrapper?.length) return;
		if (!title) {
			$wrapper.hide();
			return;
		}
		$wrapper.show();
		const $heading = $wrapper.find(".section-head.import-log-title, .section-head").first();
		if ($heading?.length) {
			if (is_skeleton) {
				$heading.html(frappe.ui.skeleton.html({ width: "160px", height: "24px" }));
			} else {
				$heading.text(title);
			}
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
		if (!grid?.grid_pagination) return;

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
				frm.events.apply_value_mappings_mobile_layout(frm);
			};
		}

		grid.setup_toolbar?.();
		grid.refresh_remove_rows_button?.();
		frm.events.apply_mapping_target_fields(frm);
		frm.events.apply_value_mappings_mobile_layout(frm);
	},

	apply_value_mappings_mobile_layout(frm) {
		const grid = frm.fields_dict.value_mappings?.grid;
		const $wrapper = grid?.wrapper;
		if (!$wrapper?.length) return;

		const in_fix_issues_wizard = Boolean($wrapper.closest(".diw-fix-issues-step").length);
		const is_mobile = window.matchMedia("(max-width: 768px)").matches;
		const $container = $wrapper.find(".form-grid-container").first();
		if (!$container.length) return;

		const reset_cell = (el) => {
			if (!el?.style) return;
			el.style.removeProperty("position");
			el.style.removeProperty("left");
			el.style.removeProperty("right");
			el.style.removeProperty("z-index");
		};

		const sticky_cells = $wrapper.find(
			".row-check, .row-index, .grid-row > .row .col:last-child"
		);

		if (!(in_fix_issues_wizard && is_mobile)) {
			$container.get(0)?.style?.removeProperty("overflow-x");
			$container.get(0)?.style?.removeProperty("overflow-y");
			sticky_cells.each((_, el) => reset_cell(el));
			return;
		}

		const container = $container.get(0);
		container.style.setProperty("overflow-x", "auto", "important");
		container.style.setProperty("overflow-y", "hidden", "important");

		sticky_cells.each((_, el) => {
			if (!el?.style) return;
			el.style.setProperty("position", "static", "important");
			el.style.setProperty("left", "auto", "important");
			el.style.setProperty("right", "auto", "important");
			el.style.setProperty("z-index", "auto", "important");
		});
	},

	setup_mapping_dropdown_portal(grid) {
		// Awesomplete instances live on the frappe control, not the input element,
		// so find the dropdown via the DOM instead of input.awesomplete.
		const get_dropdown = (input) => $(input).closest(".awesomplete").children("ul").get(0);

		if (grid._value_mapping_scroll_handler) {
			document.removeEventListener("scroll", grid._value_mapping_scroll_handler, true);
			delete grid._value_mapping_scroll_handler;
		}

		const position_dropdown = (input) => {
			// The row-edit modal (.form-in-grid) is transformed, which would make
			// fixed coords relative to it — and its own overflow handles the list fine.
			if (input.closest(".form-in-grid")) return;
			const ul = get_dropdown(input);
			if (!ul) return;
			const rect = input.getBoundingClientRect();
			// Fixed positioning escapes the scrollable wizard panel that clips the inline list.
			// Explicit width: the stylesheet's `width: 100%` would span the viewport when fixed.
			$(ul).css({
				position: "fixed",
				left: rect.left,
				top: rect.bottom,
				width: Math.max(rect.width, 250),
				zIndex: 1050,
			});
		};

		grid.wrapper.on("awesomplete-open", ".form-grid input", function () {
			position_dropdown(this);
		});
		grid.wrapper.on("input focus", ".form-grid .link-field input", function () {
			const ul = get_dropdown(this);
			if (ul && !$(ul).is(":hidden")) {
				position_dropdown(this);
			}
		});
		// Capture phase so scrolls inside the wizard panel (not just window) reposition it.
		const reposition_open_dropdowns = () => {
			grid.wrapper.find(".form-grid input:focus").each(function () {
				const ul = get_dropdown(this);
				if (ul && $(ul).is(":visible")) {
					position_dropdown(this);
				}
			});
		};
		document.addEventListener("scroll", reposition_open_dropdowns, true);
		grid._value_mapping_scroll_handler = reposition_open_dropdowns;
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
				const fieldtype_changed = column.field.df.fieldtype !== target_df.fieldtype;
				const options_changed = column.field.df.options !== target_df.options;
				if (fieldtype_changed || options_changed) {
					column.field_area?.empty();
					column.field = null;
					delete grid_row.on_grid_fields_dict?.[target_df.fieldname];
					grid_row.on_grid_fields = (grid_row.on_grid_fields || []).filter(
						(field) => field?.df?.fieldname !== target_df.fieldname
					);
					grid_row.make_control(column);
				} else {
					column.field.df = target_df;
					column.field.refresh();
				}
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

	import_file(frm, { force = false } = {}) {
		if (!frm.has_import_file()) {
			frm.events.reset_import_ui_state(frm);
			return Promise.resolve(null);
		}

		// Setting import_file on a new doc fires this handler before save.
		// Skip until the doc exists so we never call get_preview_from_template
		// with a temporary new-* name.
		if (frm.is_new()) {
			return Promise.resolve(null);
		}

		clear_stale_template_warnings_for_source(frm);
		const request_source_key = get_import_preview_source_key(frm);
		const force_reload = force || frm._import_preview_force_reload;
		if (has_failed_import_preview(frm, request_source_key) && !force_reload) {
			return Promise.reject(
				frm._import_preview_last_error || {
					message: frm._import_preview_error || __("Failed to load import file"),
				}
			);
		}

		if (frm._import_preview_promise) {
			if (!force_reload) {
				return frm._import_preview_promise;
			}
			// Navigation (Save/Next) needs a fresh fetch — drop stale in-flight work.
			frm._import_preview_request_id = (frm._import_preview_request_id || 0) + 1;
			frm._import_preview_promise = null;
			frm._import_preview_failed_source = null;
			frm._import_preview_last_error = null;
		}

		// Reserve the in-flight lock before the async call so parallel triggers share one fetch.
		let resolve_preview;
		let reject_preview;
		const preview_promise = new Promise((resolve, reject) => {
			resolve_preview = resolve;
			reject_preview = reject;
		});
		frm._import_preview_promise = preview_promise;

		const request_id = (frm._import_preview_request_id || 0) + 1;
		frm._import_preview_request_id = request_id;
		const request_docname = frm.doc.name;
		const request_import_file = frm.doc.import_file;
		const request_google_sheets_url = frm.doc.google_sheets_url;
		const request_use_csv_sniffer = cint(frm.doc.use_csv_sniffer);
		const request_custom_delimiters = cint(frm.doc.custom_delimiters);
		const request_delimiter_options = frm.doc.delimiter_options || "";
		const is_stale_request = () =>
			frm._import_preview_request_id !== request_id ||
			frm.doc.name !== request_docname ||
			frm.doc.import_file !== request_import_file ||
			frm.doc.google_sheets_url !== request_google_sheets_url ||
			cint(frm.doc.use_csv_sniffer) !== request_use_csv_sniffer ||
			cint(frm.doc.custom_delimiters) !== request_custom_delimiters ||
			(frm.doc.delimiter_options || "") !== request_delimiter_options;

		frm.toggle_display("section_import_preview", true);
		frm.trigger("update_primary_action");

		if (frm._import_preview_request_source !== request_source_key) {
			frm._import_preview_error_key = null;
			frm._import_preview_request_source = request_source_key;
		}
		const has_rendered_preview_for_source = Boolean(
			is_import_preview_ready_for_source(frm, request_source_key) &&
				(frm.import_preview?.preview_data || frm.import_tree_preview?.preview_data)
		);
		frm._import_preview_error = null;
		if (!has_rendered_preview_for_source) {
			frm._import_preview_ready = false;
		}
		set_import_preview_loading(frm, true);

		const finish_preview_fetch = () => {
			frm._import_preview_promise = null;
			frm._import_preview_force_reload = false;
			set_import_preview_loading(frm, false);
		};

		try {
			const call_promise = Promise.resolve(
				frm.call({
					method: "get_preview_from_template",
					args: {
						data_import: request_docname,
						import_file: request_import_file,
						google_sheets_url: request_google_sheets_url,
					},
					silent: true,
					error_handlers: {
						TimestampMismatchError() {
							// ignore this error
						},
					},
				})
			)
				.then((r) => {
					if (is_stale_request()) {
						return null;
					}

					if (is_failed_import_preview_response(r)) {
						throw r;
					}

					const preview_data = r.message;
					if (!preview_data) {
						throw r || { message: __("Failed to load import file") };
					}

					frm._import_preview_error = null;
					frm._import_preview_error_key = null;
					frm._import_preview_failed_source = null;
					frm._import_preview_last_error = null;
					frm._import_preview_ready = true;
					frm._import_preview_source_key = request_source_key;
					frm._import_preview_data = preview_data;
					frm.events.show_import_tree_preview(frm, preview_data);
					frm.events.show_import_preview(frm, preview_data);
					frm.events.show_import_warnings(frm, preview_data);
					frm._data_import_wizard?.bump_ui?.();
					return preview_data;
				})
				.then((preview_data) => {
					resolve_preview(preview_data);
					return preview_data;
				})
				.catch((error) => {
					if (is_stale_request()) {
						resolve_preview(null);
						return null;
					}

					frm._import_preview_error = get_import_preview_error_message(error);
					frm._import_preview_ready = false;
					frm._import_preview_source_key = null;
					frm._import_preview_data = null;
					frm._import_preview_failed_source = request_source_key;
					frm._import_preview_last_error = error;
					show_import_preview_error(frm, error, request_source_key);
					frm._data_import_wizard?.bump_ui?.();
					reject_preview(error);
				})
				.finally(() => {
					finish_preview_fetch();
					frm._data_import_wizard?.bump_ui?.();
				});

			call_promise.catch(() => {
				// Handled above; avoid unhandled rejection on the desk call chain.
			});
		} catch (error) {
			finish_preview_fetch();
			reject_preview(error);
			throw error;
		}

		return preview_promise;
	},

	show_import_tree_preview(frm, preview_data) {
		if (is_import_complete(frm.doc.status)) {
			preview_data = strip_tree_preview_warnings(preview_data);
		}

		const show_tree = is_tree_import_preview(frm, preview_data);
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
				frm.import_preview?.highlight_table_row(row_number);
			};
			// Persist per-row move / group edits into the hidden JSON field and mark the
			// form dirty. It is saved when the user clicks Next (Save + Next), which also
			// re-fetches the preview so tree warnings recompute against the new arrangement.
			const events = {
				on_change: (overrides) => {
					const value = Object.keys(overrides).length ? JSON.stringify(overrides) : "";
					if ((frm.doc.tree_parent_overrides || "") === value) return;
					frm.doc.tree_parent_overrides = value;
					frm.dirty();
					frm.trigger("update_primary_action");
				},
			};

			const readonly = is_import_complete(frm.doc.status);

			if (
				frm.doc.name &&
				frm.import_tree_preview &&
				frm.import_tree_preview.data_import_name === frm.doc.name
			) {
				frm.import_tree_preview.preview_data = preview_data;
				frm.import_tree_preview.on_row_click = on_row_click;
				frm.import_tree_preview.events = events;
				frm.import_tree_preview.readonly = readonly;
				frm.import_tree_preview.refresh();
			} else {
				frm.import_tree_preview = new frappe.data_import.ImportTreePreview({
					wrapper,
					doctype: frm.doc.reference_doctype,
					preview_data,
					on_row_click,
					events,
					readonly,
				});
				frm.import_tree_preview.data_import_name = frm.doc.name;
			}

			// Reparented into the wizard Preview step — keep section bodies expanded.
			setTimeout(() => {
				frm.layout?.sections_dict?.section_import_tree_preview?.collapse(false);
				$(frm.wrapper).trigger("diw-import-preview-ready");
			}, 0);
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

		frm.events.get_import_provider_schema(frm).then((provider_schema) => {
			if (
				frm.doc.name &&
				frm.import_preview &&
				frm.import_preview.doctype === frm.doc.reference_doctype &&
				frm.import_preview.data_import_name === frm.doc.name
			) {
				frm.import_preview.preview_data = preview_data;
				frm.import_preview.import_log = import_log;
				frm.import_preview.provider_schema = provider_schema || null;
				frm.import_preview.refresh();
				refresh_wizard_table_preview(frm, { force: true });
				$(frm.wrapper).trigger("diw-import-preview-ready");
				return;
			}

			frappe.require("data_import_tools.bundle.js", () => {
				frm.import_preview = new frappe.data_import.ImportPreview({
					wrapper: frm.get_field("import_preview").$wrapper,
					doctype: frm.doc.reference_doctype,
					preview_data,
					import_log,
					provider_schema,
					frm,
					events: {
						remap_column(changed_map) {
							let template_options = JSON.parse(frm.doc.template_options || "{}");
							template_options.column_to_field_map =
								template_options.column_to_field_map || {};
							const next_changes = Object.fromEntries(
								Object.entries(changed_map || {}).filter(
									([index, value]) =>
										template_options.column_to_field_map[index] !== value
								)
							);
							if (!Object.keys(next_changes).length) {
								return;
							}
							Object.assign(template_options.column_to_field_map, next_changes);
							frm.set_value("template_options", JSON.stringify(template_options));
							frm._diw_column_map_dirty = true;
						},
						set_column_date_format(index, date_format) {
							let template_options = JSON.parse(frm.doc.template_options || "{}");
							template_options.column_to_date_format_map =
								template_options.column_to_date_format_map || {};
							if (template_options.column_to_date_format_map[index] === date_format)
								return;
							template_options.column_to_date_format_map[index] = date_format;
							frm.set_value("template_options", JSON.stringify(template_options));
							frm._diw_column_map_dirty = true;
						},
					},
					on_ready() {
						setTimeout(() => {
							if (frm.import_preview) {
								frm.import_preview.data_import_name = frm.doc.name;
							}
							refresh_wizard_table_preview(frm, { force: true });
							$(frm.wrapper).trigger("diw-import-preview-ready");
						}, 0);
					},
				});
			});
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

	show_import_warnings(frm, preview_data) {
		frm.events.render_import_warnings(frm, preview_data);
		frm._data_import_wizard?.bump_ui?.();
		if (cint(frm.wizard_step) === 2) {
			frm._data_import_wizard?.refresh_fix_issues?.();
		}
	},

	/** Render import warnings; dedupe when preview and ``template_warnings`` overlap. */
	render_import_warnings(frm, preview_data) {
		if (!frm.has_import_file()) {
			frm.events.reset_import_ui_state(frm);
			return;
		}

		if (is_import_complete(frm.doc.status)) {
			frm.events.toggle_import_issues_ui(frm, false, false);
			frm.get_field("import_warnings")?.$wrapper.html("");
			update_section_count(frm, "import_warnings_section", 0, "import-warnings-count");
			update_section_count(frm, "value_mappings_section", 0, "value-mappings-count");
			return;
		}

		if (!preview_data) {
			preview_data = get_fix_issues_preview_data(frm, preview_data);
		}
		let columns = preview_data?.columns;
		let warnings = get_current_import_warnings(frm, preview_data);

		// Saved value mappings are explicit user decisions — show and set them up
		// whenever they exist, regardless of whether this preview run redetects hints
		// for them (that signal is timing-dependent on the async preview fetch).
		const has_saved_mappings = (frm.doc.value_mappings || []).length > 0;
		frm.events.toggle_import_issues_ui(frm, warnings.length > 0, has_saved_mappings);
		update_section_count(
			frm,
			"value_mappings_section",
			has_saved_mappings ? (frm.doc.value_mappings || []).length : 0,
			"value-mappings-count"
		);

		if (!warnings.length && !has_saved_mappings) {
			frm.get_field("import_warnings").$wrapper.html("");
			update_section_count(frm, "import_warnings_section", 0, "import-warnings-count");
			return;
		}

		let warnings_by_row = {};
		let column_warnings = [];
		let mapping_warnings = [];
		let generic_warnings = [];
		for (let warning of warnings) {
			if (warning.row) {
				warnings_by_row[warning.row] = warnings_by_row[warning.row] || [];
				warnings_by_row[warning.row].push(warning);
			} else if (warning.col) {
				if (is_mapping_warning(warning)) {
					mapping_warnings.push(warning);
				} else {
					column_warnings.push(warning);
				}
			} else {
				generic_warnings.push(warning);
			}
		}

		let row_error_html = "";
		const skipped_rows = get_skipped_row_set(frm);
		row_error_html += Object.keys(warnings_by_row)
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
				let skip_btn = frappe.ui.button.html({
					label: is_skipped ? __("Undo Skip") : __("Skip Row"),
					size: "xs",
					variant: "outline",
					css_class: "skip-row-btn shrink-0",
					attrs: { "data-row": String(row_number) },
				});
				return `
				<div class="warning relative m-0 p-0 border-0 bg-transparent${
					is_skipped ? " skipped" : ""
				}" data-row="${row_number}">
					<div class="warning-row-header flex items-center justify-between gap-3 mb-1">
						<button type="button" class="diw-row-warning-label text-base-semibold text-ink-gray-9 underline p-0 border-0 bg-transparent cursor-pointer" data-row="${row_number}">
							${__("Row {0}", [row_number])}
						</button>
						${skip_btn}
					</div>
					<div class="body"><ul class="list-none m-0 p-0 flex flex-col gap-1">${message}</ul></div>
				</div>
			`;
			})
			.join("");
		if (row_error_html) {
			row_error_html = `<div class="flex flex-col gap-3">${row_error_html}</div>`;
		}

		const show_mapping_section = mapping_warnings.length > 0 || has_saved_mappings;
		let mapping_warning_html = "";
		if (show_mapping_section) {
			let helper = "";
			if (mapping_warnings.length) {
				const affected_columns = [
					...new Set(
						mapping_warnings
							.map(
								(warning) =>
									columns?.[warning.col]?.header_title ||
									__("Column {0}", [warning.col])
							)
							.filter(Boolean)
					),
				];
				const column_labels = affected_columns
					.map((label) => `<strong>${frappe.utils.escape_html(label)}</strong>`)
					.join(", ");
				helper = `
					<div class="body mb-3">
						${__("Some columns have invalid values. Map them to valid values below. Affected columns: {0}.", [
							column_labels,
						])}
					</div>
				`;
			}
			mapping_warning_html = `
				<div class="warning-mapping m-0 p-0">
					${helper}
					<div class="diw-mapping-grid-host"></div>
				</div>
			`;
		}

		let column_warning_html = column_warnings
			.map((warning) => {
				let column_number = __("Column {0}", [warning.col]);
				let header = column_number;
				if (columns && warning.col) {
					let column_header = columns[warning.col]?.header_title
						? frappe.utils.escape_html(columns[warning.col].header_title)
						: "";
					header = column_header ? `${column_header} (${column_number})` : header;
				}
				return `
					<div class="warning relative m-0 p-0 border-0 bg-transparent" data-col="${warning.col}">
						<h5 class="warning-row-header warning-col-header flex items-center gap-3 mb-1 text-base-semibold">
							<span>${header}</span>
						</h5>
						<div class="body">${warning.message}</div>
					</div>
				`;
			})
			.join("");
		if (column_warning_html) {
			column_warning_html = `<div class="flex flex-col gap-3">${column_warning_html}</div>`;
		}

		let generic_issue_html = generic_warnings
			.map((warning) => {
				// For duplicate ID warnings, show a "Keep First, Skip Rest" button
				if (warning.type === "duplicate_id" && warning.rows && warning.rows.length > 1) {
					const rows_to_skip = warning.rows.slice(1); // Skip all but the first row
					const all_skipped = rows_to_skip.every((row) => skipped_rows.has(cint(row)));
					const skip_btn = frappe.ui.button.html({
						label: all_skipped
							? __("Undo Skip Duplicates")
							: __("Keep Row {0}, Skip Rest", [warning.rows[0]]),
						size: "xs",
						variant: "outline",
						css_class: "skip-duplicate-rows-btn shrink-0",
						attrs: {
							"data-rows-to-skip": JSON.stringify(rows_to_skip),
							"data-keep-row": String(warning.rows[0]),
						},
					});
					return `
						<div class="warning warning-generic warning-duplicate-id m-0 p-0 border-0 bg-transparent flex items-start justify-between gap-3${
							all_skipped ? " skipped" : ""
						}" data-col="generic">
							<div class="body">${warning.message}</div>
							${skip_btn}
						</div>
					`;
				}
				return `
					<div class="warning warning-generic m-0 p-0 border-0 bg-transparent" data-col="generic">
						<div class="body">${warning.message}</div>
					</div>
				`;
			})
			.join("");
		if (generic_issue_html) {
			generic_issue_html = `<div class="flex flex-col gap-3">${generic_issue_html}</div>`;
		}

		let html = "";
		let group_index = 0;
		const warning_group = (title, body) => {
			const spacing = group_index++ ? " mt-4 pt-4 border-t" : "";
			return `
				<div class="diw-warning-group${spacing}">
					<div class="diw-warning-group-title text-base-semibold text-ink-gray-9 mb-2">${title}</div>
					${body}
				</div>
			`;
		};
		if (row_error_html) {
			html += warning_group(__("Row errors"), row_error_html);
		}

		if (mapping_warning_html) {
			html += warning_group(__("Mapping warnings"), mapping_warning_html);
		}

		if (column_warning_html) {
			html += warning_group(__("Column warnings"), column_warning_html);
		}

		if (generic_issue_html) {
			html += warning_group(__("Issues"), generic_issue_html);
		}

		frm.get_field("import_warnings").$wrapper.html(
			html ? `<div class="warnings w-full m-0 p-0 flex flex-col gap-3">${html}</div>` : ""
		);
		update_section_count(
			frm,
			"import_warnings_section",
			warnings.length,
			"import-warnings-count"
		);

		// Re-attach grid under Mapping warnings after HTML refresh (e.g. Skip Row).
		const $step = frm.get_field("import_warnings")?.$wrapper?.closest(".diw-fix-issues-step");
		if ($step?.length) {
			place_value_mappings_in_mapping_section(frm, $step);
		}
		setup_row_warning_hover_cards(frm, preview_data || get_fix_issues_preview_data(frm));
	},

	setup_skip_row_handlers(frm) {
		if (frm._skip_row_handlers) return;
		frm._skip_row_handlers = true;
		frm.get_field("import_warnings").$wrapper.on("click", ".skip-row-btn", (e) => {
			e.preventDefault();
			frm.events.toggle_skip_row(frm, $(e.currentTarget).data("row"));
		});
		// Handler for "Keep First, Skip Rest" button on duplicate ID warnings
		frm.get_field("import_warnings").$wrapper.on("click", ".skip-duplicate-rows-btn", (e) => {
			e.preventDefault();
			const $btn = $(e.currentTarget);
			const rows_to_skip = JSON.parse($btn.attr("data-rows-to-skip") || "[]");
			frm.events.toggle_skip_duplicate_rows(frm, rows_to_skip);
		});
	},

	/** Toggle skip state for duplicate rows - skip all except the first occurrence */
	toggle_skip_duplicate_rows(frm, rows_to_skip) {
		const skipped_set = new Set((frm.doc.skipped_rows || []).map((r) => cint(r.row_number)));
		const all_already_skipped = rows_to_skip.every((row) => skipped_set.has(cint(row)));

		if (all_already_skipped) {
			// Undo skip - remove all these rows from skipped_rows
			for (const row_number of rows_to_skip) {
				const skipped = (frm.doc.skipped_rows || []).find(
					(r) => cint(r.row_number) === cint(row_number)
				);
				if (skipped) {
					frappe.model.clear_doc(skipped.doctype, skipped.name);
				}
			}
		} else {
			// Skip all duplicate rows (except the first one which isn't in rows_to_skip)
			const preview_data = get_fix_issues_preview_data(frm);
			for (const row_number of rows_to_skip) {
				if (skipped_set.has(cint(row_number))) continue; // Already skipped
				const preview_row = preview_data?.data?.find(
					(row) => cint(row[0]) === cint(row_number)
				);
				frm.add_child("skipped_rows", {
					row_number: cint(row_number),
					row_data: JSON.stringify(preview_row ? preview_row.slice(1) : []),
				});
			}
		}

		frm.dirty();
		frm.trigger("update_primary_action");
		frm.events.show_import_warnings(frm);
	},

	toggle_skip_row(frm, row_number) {
		row_number = cint(row_number);
		const skipped = (frm.doc.skipped_rows || []).find(
			(row) => cint(row.row_number) === row_number
		);

		if (skipped) {
			frappe.model.clear_doc(skipped.doctype, skipped.name);
		} else {
			// Fix Issues can render its Skip Row buttons from cached preview data before
			// ImportPreview exists, so resolve through the same helper the step mounts with —
			// reading frm.import_preview alone would silently store an empty row_data.
			const preview_row = get_fix_issues_preview_data(frm)?.data?.find(
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

	render_import_log(frm) {
		const is_upsert = is_upsert_import_type(frm.doc.import_type);
		const normalize_import_log_text = (value) =>
			(value || "").replace(/\s+/g, " ").trim().toLowerCase();
		const active_filter = frm._import_log_filter || "all";

		// Renders even with zero logs (e.g. every row skipped => Success with no log rows);
		// returning early here would leave the loading skeleton on screen forever.
		const render_logs = (logs, status_summary = {}) => {
			frm.events.toggle_import_log_ui(frm, true);

			const parse_row_indexes = (log) => {
				try {
					const indexes = JSON.parse(log.row_indexes || "[]") || [];
					return indexes.map((row) => cint(row)).filter(Boolean);
				} catch (_e) {
					return [];
				}
			};

			const parse_messages = (log) => {
				try {
					return JSON.parse(log.messages || "[]") || [];
				} catch (_e) {
					return [];
				}
			};

			const get_row_count = (log) => Math.max(parse_row_indexes(log).length, 1);

			const status_total_rows = cint(status_summary.total_records);
			const status_success_rows = cint(status_summary.success);
			const status_failed_rows = cint(status_summary.failed);
			const has_status_counts =
				status_total_rows > 0 || status_success_rows > 0 || status_failed_rows > 0;

			const success_rows = has_status_counts
				? status_success_rows
				: logs.reduce((acc, log) => acc + (log.success ? get_row_count(log) : 0), 0);
			const failed_rows = has_status_counts
				? status_failed_rows
				: logs.reduce((acc, log) => acc + (log.success ? 0 : get_row_count(log)), 0);
			const total_rows = has_status_counts
				? status_success_rows + status_failed_rows
				: success_rows + failed_rows;
			const skipped_rows_count = (frm.doc.skipped_rows || []).length;
			const total_rows_in_file = has_status_counts
				? Math.max(status_total_rows, total_rows + skipped_rows_count)
				: total_rows + skipped_rows_count;

			// Tab badges already show "1000 of N" when a bucket is capped; no separate banner.
			const show_export =
				total_rows > IMPORT_LOG_PREVIEW_LIMIT ||
				success_rows > IMPORT_LOG_PREVIEW_LIMIT ||
				failed_rows > IMPORT_LOG_PREVIEW_LIMIT;

			let inserted_rows = cint(status_summary.inserted);
			let updated_rows = cint(status_summary.updated);

			if (!is_upsert) {
				inserted_rows = frm.doc.import_type === "Insert New Records" ? success_rows : 0;
				updated_rows =
					frm.doc.import_type === "Update Existing Records" ? success_rows : 0;
			} else if (!inserted_rows && !updated_rows) {
				inserted_rows = logs.reduce((acc, log) => {
					if (!log.success || log.import_action !== IMPORT_ACTION_INSERT) return acc;
					return acc + get_row_count(log);
				}, 0);
				updated_rows = logs.reduce((acc, log) => {
					if (!log.success || log.import_action !== IMPORT_ACTION_UPDATE) return acc;
					return acc + get_row_count(log);
				}, 0);
			}

			// Server already filtered by tab — do not re-filter client-side.
			const has_rows = logs.length > 0;
			let rows = logs
				.map((log) => {
					let html = "";
					let row_indexes = parse_row_indexes(log);
					const row_number_label = row_indexes.length ? row_indexes.join(", ") : __("-");
					if (log.success) {
						const doc_link = `<span class="underline">${frappe.utils.get_form_link(
							frm.doc.reference_doctype,
							log.docname,
							true
						)}</span>`;
						html = `<div class="diw-import-log-message">${get_import_log_html(
							frm.doc.import_type,
							log.import_action,
							doc_link
						)}</div>`;
					} else {
						const messages = parse_messages(log);
						// m.message is server-sanitized HTML (frappe.msgprint runs it through
						// nh3 clean_html) so it's safe to render directly; m.title bypasses
						// that sanitization, so it must still be escaped.
						const summary_text =
							messages[0]?.message || messages[0]?.title || __("Import failed");
						const normalized_summary = normalize_import_log_text(summary_text);
						const summary = messages[0]?.message
							? messages[0].message
							: messages[0]?.title
							? frappe.utils.escape_html(messages[0].title)
							: __("Import failed");
						const message_details = messages
							.filter((m) => {
								const normalized_message = normalize_import_log_text(
									m.message || m.title
								);
								return (
									normalized_message && normalized_message !== normalized_summary
								);
							})
							.map((m) => {
								const title = m.title
									? `<div><strong>${frappe.utils.escape_html(
											m.title
									  )}</strong></div>`
									: "";
								const message = m.message ? `<div>${m.message}</div>` : "";
								return `${title}${message}`;
							})
							.join("");
						const detail_list = message_details ? `<div>${message_details}</div>` : "";
						const traceback = (log.exception || "").trim();
						const traceback_html = traceback
							? `<pre class="diw-import-log-error-trace m-0 mt-2 p-2 overflow-auto text-sm whitespace-pre-wrap break-words">${frappe.utils.escape_html(
									traceback
							  )}</pre>`
							: "";
						const is_expandable = Boolean(detail_list || traceback_html);
						let id = frappe.dom.get_unique_id();
						// Chevron expands extra messages + traceback directly.
						html = `<div class="diw-import-log-message">
							<div class="flex items-start justify-between gap-2">
								<div>${summary}</div>
								${
									is_expandable
										? frappe.ui.button.html({
												icon: "chevron-down",
												size: "sm",
												variant: "ghost",
												css_class: "diw-import-log-expand-btn",
												title: __("Toggle error details"),
												attrs: {
													"data-toggle": "collapse",
													"data-target": `#${id}`,
													"aria-expanded": "false",
													"aria-controls": id,
												},
										  })
										: ""
								}
							</div>
							${
								is_expandable
									? `<div class="collapse diw-import-log-details mt-1" id="${id}">
										${detail_list}
										${traceback_html}
									</div>`
									: ""
							}
						</div>`;
					}
					const status_badge = frappe.ui.badge.html({
						label: log.success ? __("Success") : __("Failure"),
						theme: log.success ? "green" : "red",
					});

					return `<tr>
							<td class="diw-import-log-cell-row whitespace-nowrap text-sm text-end align-top border-b py-2 px-4" style="width:72px">${row_number_label}</td>
							<td class="text-sm align-top border-b py-2 px-4">${status_badge}</td>
							<td class="text-sm align-top border-b py-2 px-4">
								${html}
							</td>
						</tr>`;
				})
				.join("");

			const empty_message =
				active_filter === "failed"
					? __("No failed log entries")
					: active_filter === "success"
					? __("No successful log entries")
					: __("No rows were imported");
			const empty_state_html = frappe.ui.empty_state.html({
				icon: "inbox",
				title: empty_message,
				css_class: "min-h-32",
			});

			// Summary rows support optional inline header actions on the left cell.
			const kv_row = (label, value_html, action_html = "") =>
				`<tr class="diw-log-kv-row">
					<td class="diw-log-kv-key text-sm text-muted">
						<div class="diw-log-kv-key-inner flex items-center${action_html ? " gap-2" : ""}">
							<span>${frappe.utils.escape_html(label)}</span>
							${action_html}
						</div>
					</td>
					<td class="diw-log-kv-val text-sm text-ink-gray-8 text-end">
						<div class="diw-log-kv-val-inner flex items-center justify-end">${value_html}</div>
					</td>
				</tr>`;

			// Counts read bold; audit values stay regular weight.
			const num = (value, extra = "") =>
				`<span class="text-sm-semibold ${extra}">${frappe.utils.escape_html(
					String(value)
				)}</span>`;

			const total_rows_action = is_import_complete(frm.doc.status)
				? frappe.ui.button.html({
						label: __("Go to list"),
						variant: "ghost",
						size: "xs",
						icon_left: "external-link",
						attrs: { "data-action": "go_to_list" },
				  })
				: "";
			const skipped_rows_action =
				skipped_rows_count > 0
					? frappe.ui.button.html({
							variant: "ghost",
							size: "xs",
							icon: "download",
							attrs: {
								"data-action": "download_skipped_rows",
								title: __("Download Skipped Rows"),
							},
					  })
					: "";
			const failed_rows_action =
				failed_rows > 0
					? frappe.ui.button.html({
							variant: "ghost",
							size: "xs",
							icon: "download",
							attrs: {
								"data-action": "export_errored_rows",
								title: __("Download Failed Rows"),
							},
					  })
					: "";

			const result_rows = [
				kv_row(__("Total rows"), num(total_rows_in_file), total_rows_action),
			];
			if (is_upsert || frm.doc.import_type === "Insert New Records") {
				result_rows.push(kv_row(__("Inserted"), num(inserted_rows)));
			}
			if (is_upsert || frm.doc.import_type === "Update Existing Records") {
				result_rows.push(kv_row(__("Updated"), num(updated_rows)));
			}
			result_rows.push(kv_row(__("Skipped"), num(skipped_rows_count), skipped_rows_action));
			result_rows.push(
				kv_row(__("Failed"), num(failed_rows, "text-danger"), failed_rows_action)
			);

			// Show exact user-formatted date/time (instead of relative values like "yesterday").
			const fmt_dt = (value) => (value ? frappe.datetime.str_to_user(value) : "-");
			const fmt_user = (value) =>
				value ? frappe.utils.escape_html(frappe.user.full_name(value) || value) : "-";
			const detail_rows = [
				kv_row(__("Started by"), fmt_user(frm.doc.owner)),
				kv_row(__("Started on"), fmt_dt(frm.doc.creation)),
				kv_row(__("Last modified by"), fmt_user(frm.doc.modified_by)),
				kv_row(__("Last modified on"), fmt_dt(frm.doc.modified)),
			];

			// Summary lives directly under the existing "Import Log" heading.
			// Result-row actions (Go to list / downloads) are mounted inline per row.
			const summary_html = `
				<div class="diw-import-log-summary mb-4">
					<div class="diw-import-log-summary-grid flex gap-8">
						<div class="diw-log-kv-col flex-1 min-w-0">
							<div class="diw-log-kv-caption text-xs text-muted mb-1">${__("Result")}</div>
							<table class="diw-log-kv-table w-full">${result_rows.join("")}</table>
						</div>
						<div class="diw-log-kv-col flex-1 min-w-0">
							<div class="diw-log-kv-caption text-xs text-muted mb-1">${__("Details")}</div>
							<table class="diw-log-kv-table w-full">${detail_rows.join("")}</table>
						</div>
					</div>
				</div>`;

			const wrapper = frm.get_field("import_log_preview").$wrapper;
			wrapper.html(`
				${summary_html}
				<div class="diw-import-log-filter-row mt-3 mb-3 flex items-center justify-between gap-2">
					<div class="diw-import-log-filter-tabs"></div>
					<div class="diw-import-log-filter-actions inline-flex items-center ms-auto"></div>
				</div>
				${
					has_rows
						? `<table class="diw-import-log-table w-full">
							<thead>
								<tr class="text-muted">
										<th class="text-sm-semibold text-end border-b py-2 px-4" width="10%">${__("Row")}</th>
									<th class="text-sm-semibold border-b py-2 px-4" width="14%">${__("Status")}</th>
									<th class="text-sm-semibold border-b py-2 px-4" width="76%">${__("Message")}</th>
								</tr>
							</thead>
							<tbody>
								${rows}
							</tbody>
						</table>`
						: `<div class="diw-import-log-empty-state">${empty_state_html}</div>`
				}
			`);

			const log_filter = new frappe.ui.TabButtons({
				label: __("Filter import log"),
				value: active_filter,
				options: [
					{
						label: __("All ({0})", [format_import_log_tab_count(total_rows)]),
						value: "all",
					},
					{
						label: __("Success ({0})", [format_import_log_tab_count(success_rows)]),
						value: "success",
					},
					{
						label: __("Failed ({0})", [format_import_log_tab_count(failed_rows)]),
						value: "failed",
					},
				],
				on_change: (value) => {
					if (frm._import_log_filter === value) return;
					frm._import_log_filter = value;
					frm.events.render_import_log(frm);
				},
			});
			wrapper.find(".diw-import-log-filter-tabs").empty().append(log_filter.el);

			wrapper.find(".diw-import-log-filter-actions").empty();
			frappe.utils.bind_actions_with_object(wrapper, {
				go_to_list: () => frappe.set_route("List", frm.doc.reference_doctype),
				download_skipped_rows: () => frm.trigger("download_skipped_rows"),
				export_errored_rows: () => frm.trigger("export_errored_rows"),
			});

			if (show_export) {
				const export_button = frappe.ui.button({
					label: __("Export Import Log"),
					variant: "outline",
					size: "sm",
					icon_left: "download",
					onclick: () => frm.trigger("export_import_log"),
				});
				wrapper.find(".diw-import-log-filter-actions").append(export_button);
			}
		};

		const fetch_logs = (status_summary = {}) => {
			frappe.call({
				method: "frappe.core.doctype.data_import.data_import.get_import_logs",
				args: {
					data_import: frm.doc.name,
					status: active_filter,
				},
				callback: function (r) {
					render_logs(r.message || [], status_summary);
				},
			});
		};

		frappe.call({
			method: "frappe.core.doctype.data_import.data_import.get_import_status",
			args: {
				data_import_name: frm.doc.name,
			},
			callback: function (r) {
				const m = r.message || {};
				frm._import_log_status_summary = {
					total_records: cint(m.total_records),
					success: cint(m.success),
					failed: cint(m.failed),
					inserted: cint(m.inserted),
					updated: cint(m.updated),
				};
				frm._import_log_total_count =
					cint(m.success) + cint(m.failed) || frm._import_log_total_count;
				fetch_logs(frm._import_log_status_summary);
			},
			error: function () {
				fetch_logs(frm._import_log_status_summary || {});
			},
		});
	},

	render_import_progress_state(frm) {
		frm.events.toggle_import_log_ui(frm, true);
		frm.events.set_import_log_heading(frm, "");
		const progress = frm._wizard_import_progress || {};
		const title = frappe.utils.escape_html(progress.title || __("Importing your data"));
		const subtitle = frappe.utils.escape_html(
			progress.subtitle ||
				__(
					"You can continue other work while this runs. Progress updates will appear here."
				)
		);
		const message = frappe.utils.escape_html(
			progress.message || __("Import is running. Progress updates will appear shortly.")
		);
		const status_line = frappe.utils.escape_html(progress.status_line || "");
		const raw_percent = Number(progress.percent);
		const has_percent = Number.isFinite(raw_percent);
		const percent = has_percent ? Math.max(0, Math.min(100, Math.floor(raw_percent))) : 100;
		const current = cint(progress.current);
		const total = cint(progress.total);
		const row_progress =
			current && total ? __("Importing row {0} of {1}", [current, total]) : message;
		const linear_progress = frappe.ui.progress.html({
			value: has_percent ? percent : 0,
			size: "lg",
			label: row_progress,
			hint: (value) => `${Math.round(value)}%`,
			css_class: "diw-import-progress-standard",
		});
		const import_type = frm.doc.import_type;
		const show_inserted =
			is_upsert_import_type(import_type) || import_type === "Insert New Records";
		const show_updated =
			is_upsert_import_type(import_type) || import_type === "Update Existing Records";
		const inserted = cint(progress.inserted);
		const updated = cint(progress.updated);
		const failed = cint(progress.failed);
		const skipped = cint((progress.skipped ?? frm.doc.skipped_rows?.length) || 0);
		const stat_cards = [];
		if (show_inserted) {
			stat_cards.push(`
				<div class="diw-import-progress-stat flex flex-col items-center justify-center text-center gap-0.5 min-w-0" role="listitem">
					<div class="value text-2xl-semibold">${inserted}</div>
					<div class="label text-sm text-muted">${__("Inserted")}</div>
				</div>
			`);
		}
		if (show_updated) {
			stat_cards.push(`
				<div class="diw-import-progress-stat flex flex-col items-center justify-center text-center gap-0.5 min-w-0" role="listitem">
					<div class="value text-2xl-semibold">${updated}</div>
					<div class="label text-sm text-muted">${__("Updated")}</div>
				</div>
			`);
		}
		stat_cards.push(`
			<div class="diw-import-progress-stat flex flex-col items-center justify-center text-center gap-0.5 min-w-0" role="listitem">
				<div class="value text-2xl-semibold">${skipped}</div>
				<div class="label text-sm text-muted">${__("Skipped")}</div>
			</div>
		`);
		stat_cards.push(`
			<div class="diw-import-progress-stat flex flex-col items-center justify-center text-center gap-0.5 min-w-0" role="listitem">
				<div class="value text-2xl-semibold text-ink-red-8">${failed}</div>
				<div class="label text-sm text-muted">${__("Failed")}</div>
			</div>
		`);
		const recent = Array.isArray(progress.recent_activity)
			? progress.recent_activity.slice(0, 5)
			: [];
		const recent_html = recent.length
			? recent
					.map((item, index) => {
						const kind = item?.kind || "info";
						const icon_name =
							kind === "success"
								? "circle-check"
								: kind === "error"
								? "circle-alert"
								: "circle-minus";
						const icon_color =
							kind === "success"
								? "text-ink-green-8"
								: kind === "error"
								? "text-ink-red-8"
								: "text-muted";
						const text = item?.is_html
							? item.text || ""
							: frappe.utils.escape_html(item?.text || "");
						const row = cint(item?.row);
						const row_label = row
							? `<span class="shrink-0 text-xs text-muted whitespace-nowrap">${__(
									"Row {0}",
									[row]
							  )}</span>`
							: "";
						// Hairline between updates; the newest (index 0) sits flush under the header.
						const divider = index === 0 ? "" : " border-t";
						return `<li class="flex items-center gap-2 py-1${divider}">
							<span class="inline-flex shrink-0 ${icon_color}">${frappe.utils.icon(icon_name, "sm")}</span>
							<span class="flex-1 min-w-0 truncate text-sm">${text}</span>
							${row_label}
						</li>`;
					})
					.join("")
			: `<li class="py-1 text-sm text-muted">${frappe.utils.escape_html(
					__("Live activity updates will appear here.")
			  )}</li>`;

		frm.get_field("import_log_preview")?.$wrapper?.html(`
			<div class="diw-import-progress-hero flex flex-col text-center gap-1 pt-1">
				<h3 class="text-base-medium mb-0">${title}</h3>
				<p class="text-sm text-muted mb-0">${subtitle}</p>
				<div class="diw-import-progress-bar-wrap w-full my-1">${linear_progress}</div>
				${
					status_line
						? `<div class="diw-import-progress-status self-end text-right text-sm text-muted mb-2">${status_line}</div>`
						: ""
				}

				<div class="diw-import-progress-stats grid items-stretch w-full gap-5" role="list" aria-label="${frappe.utils.escape_html(
					__("Progress summary")
				)}" style="--diw-import-progress-stat-count: ${Math.max(stat_cards.length, 1)};">
					${stat_cards.join("")}
				</div>

				<div class="diw-import-progress-activity w-full max-w-6xl border rounded-md text-left bg-surface-base mt-2 px-3 py-2">
					<div class="flex items-center gap-1 mb-1">
						<span class="text-sm-semibold text-muted">${__("Recent activity")}</span>
						<span class="inline-flex text-ink-green-8">${frappe.utils.icon("dot", "sm")}</span>
					</div>
					<ul class="list-none m-0 p-0 flex flex-col">${recent_html}</ul>
				</div>
			</div>
		`);
	},

	refresh_import_progress_counts(frm) {
		if (!frm.import_in_progress && frm.doc?.status !== "In Progress") return;
		const now = Date.now();
		if (frm._wizard_progress_counts_inflight) return;
		if (
			frm._wizard_progress_counts_last_fetch &&
			now - frm._wizard_progress_counts_last_fetch < 2000
		) {
			return;
		}
		frm._wizard_progress_counts_last_fetch = now;
		frm._wizard_progress_counts_inflight = true;
		frappe.call({
			method: "frappe.core.doctype.data_import.data_import.get_import_status",
			args: {
				data_import_name: frm.doc.name,
			},
			callback: function (r) {
				const m = r.message || {};
				const previous = frm._wizard_import_progress || {};
				frm._wizard_import_progress = {
					...previous,
					current: cint(m.processed_records || previous.current),
					total: cint(m.total_records || previous.total),
					inserted: cint(
						is_upsert_import_type(frm.doc.import_type)
							? m.inserted ?? 0
							: m.inserted ?? m.success
					),
					updated: cint(m.updated),
					failed: cint(m.failed),
				};
				if (
					cint(frm.wizard_step) === 3 &&
					(frm.import_in_progress || frm.doc?.status === "In Progress")
				) {
					frm.events.render_import_progress_state(frm);
				}
			},
			always: function () {
				frm._wizard_progress_counts_inflight = false;
			},
		});
	},

	show_import_log(frm) {
		frm.events.toggle_import_log_ui(frm, false);
		const is_import_running = Boolean(
			frm.import_in_progress || frm.doc?.status === "In Progress"
		);

		if (frm.is_new()) {
			return;
		}

		if (is_import_running) {
			frm.events.render_import_progress_state(frm);
			return;
		}

		// Pending: do not paint the empty after-import log into hidden fields —
		// reparenting them on step 3 would flash that empty UI before progress.
		if (frm.doc.status === "Pending") {
			frm.events.set_import_log_heading(frm, "");
			frm.get_field("import_log_preview")?.$wrapper?.empty();
			return;
		}

		frm.events.toggle_import_log_ui(frm, true);
		frm.events.set_import_log_heading(frm, __("Import log"), true);
		frm.get_field("import_log_preview")?.$wrapper?.html(get_import_log_skeleton_html());
		frm.trigger("render_import_log");
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
