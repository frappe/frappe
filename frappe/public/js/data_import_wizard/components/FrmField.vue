<!-- Binds desk form fields via make_control — @framework/ui FormLayout fields
     target host apps with frappe-ui; desk needs frm + layout dependency hooks. -->
<script setup>
import { ref, onMounted, onBeforeUnmount, watch, inject, nextTick } from "vue";

const props = defineProps({
	fieldname: { type: String, required: true },
	docname: { type: String, default: "" },
	read_only: { type: Boolean, default: false },
});

const frm = inject("frm");
const el = ref(null);
let control = null;

function destroy_control() {
	if (control?._diw_dropzone_cleanup) {
		control._diw_dropzone_cleanup();
	}
	if (control?._diw_google_sheet_cleanup) {
		control._diw_google_sheet_cleanup();
	}
	control?.$wrapper?.remove();
	control = null;
}

/** Hint under the drop zone; omit size when boot does not expose a limit. */
function get_dropzone_hint_html() {
	const max_bytes = frappe.boot?.max_file_size;
	if (!max_bytes) return "";
	const max_mb = max_bytes / (1024 * 1024);
	return `<div class="diw-file-dropzone-hint text-muted">${__(".csv, .xlsx up to {0} MB", [
		max_mb,
	])}</div>`;
}

/** Basename from an attach value (path or FILENAME,url form). */
function get_import_file_name(file_url) {
	if (!file_url) return "";
	const match = file_url.match(/^([^:]+),(.+):(.+)$/);
	if (match) {
		return decodeURIComponent(match[1]);
	}
	const segment = file_url.split("/").pop() || file_url;
	return decodeURIComponent(segment.split("?")[0]);
}

/** Resolve attach href (plain file URL or FILENAME,DATA_URL form used by Attach). */
function get_import_file_href(file_url) {
	if (!file_url) return "";
	const match = file_url.match(/^([^:]+),(.+):(.+)$/);
	if (match) {
		return `${match[2]}:${match[3]}`;
	}
	return file_url;
}

/** Short type label for the file card meta line. */
function get_import_file_type_label(filename) {
	const ext = (filename.split(".").pop() || "").toLowerCase();
	if (ext === "csv") return "CSV";
	if (ext === "xlsx") return "XLSX";
	if (ext === "xls") return "XLS";
	return ext ? ext.toUpperCase() : __("File");
}

/** Row count from preview or saved payload_count, when available. */
function get_import_file_row_meta(frm) {
	const count =
		frm.doc.payload_count ||
		frm.import_preview?.preview_data?.total_number_of_rows ||
		frm.import_preview?.preview_data?.data?.length;
	if (!count) return null;
	return count === 1 ? __("1 row detected") : __("{0} rows detected", [count]);
}

/** Paint the post-upload file card (replaces default attach row styling). */
function render_import_file_card(control, frm, $mount) {
	if (!$mount?.length || !control.value) return;

	const filename = get_import_file_name(control.value);
	const type_label = get_import_file_type_label(filename);
	const row_meta = get_import_file_row_meta(frm);
	const meta_text = row_meta ? `${type_label} · ${row_meta}` : type_label;
	const file_icon = frappe.utils.icon("file-spreadsheet", "md", "", "", "", true);
	const clear_icon = frappe.utils.icon("x", "xs", "", "", "", true);
	const safe_name = frappe.utils.escape_html(filename);
	const safe_href = frappe.utils.escape_html(get_import_file_href(control.value));
	const is_read_only = control.df?.read_only || control.disp_status === "Read";

	$mount.html(`
		<div class="diw-import-file-card">
			<div class="diw-import-file-card-main">
				<div class="diw-import-file-card-icon">${file_icon}</div>
				<div class="diw-import-file-card-body">
					<a class="diw-import-file-card-name" href="${safe_href}" target="_blank" rel="noopener noreferrer" title="${safe_name}">${safe_name}</a>
					<div class="diw-import-file-card-meta">${meta_text}</div>
				</div>
			</div>
			${
				is_read_only
					? ""
					: `<button type="button" class="btn btn-default btn-sm diw-import-file-clear" data-action="clear_attachment">
				<span class="diw-import-file-clear-icon">${clear_icon}</span>
				${__("Clear")}
			</button>`
			}
		</div>
	`);

	frappe.utils.bind_actions_with_object($mount, control);
}

/** Turn the attach control into a dashed drop zone with drag-and-drop upload. */
function enhance_import_file_dropzone(control) {
	if (!control?.$wrapper || control._diw_dropzone_enhanced) return;

	// Read-only attach skips make_input; set_input would replace the whole wrapper without it.
	if (!control.has_input) {
		control.make_input?.();
	}

	const $input_area = $(control.input_area);
	if (!$input_area.length) return;

	control._diw_dropzone_enhanced = true;

	const $host = control.$wrapper.closest(".diw-frm-field");
	$host.addClass("diw-file-dropzone-host");

	const cloud_icon = frappe.utils.icon("cloud-upload", "md", "", "", "", true);
	const $ui = $(`
		<div class="diw-file-dropzone-ui" aria-hidden="true">
			<div class="diw-file-dropzone-icon">${cloud_icon}</div>
			<div class="diw-file-dropzone-text diw-file-dropzone-text--desktop">
				${__("Drag a CSV or Excel file here, or click to browse")}
			</div>
			<div class="diw-file-dropzone-text diw-file-dropzone-text--mobile">
				${__("Tap to upload a CSV or Excel file")}
			</div>
			${get_dropzone_hint_html()}
		</div>
	`);
	$input_area.addClass("diw-file-dropzone-target");
	$input_area.append($ui);

	const $card_mount = $('<div class="diw-import-file-card-mount hide"></div>');
	$input_area.append($card_mount);

	const original_set_input = control.set_input.bind(control);
	const original_on_upload_complete = control.on_upload_complete.bind(control);

	const is_field_read_only = () => control.df?.read_only || control.disp_status === "Read";

	const open_uploader = (files) => {
		control.set_upload_options?.();
		if (files?.length) {
			control.upload_options = { ...control.upload_options, files };
		}
		control.file_uploader = new frappe.ui.FileUploader(control.upload_options);
	};

	const on_zone_click = (event) => {
		if (
			control.value ||
			is_field_read_only() ||
			$(event.target).closest("[data-action]").length
		) {
			return;
		}
		event.preventDefault();
		control.on_attach_click?.();
	};

	const on_dragover = (event) => {
		if (control.value || is_field_read_only()) return;
		event.preventDefault();
		$host.addClass("is-dragover");
	};

	const on_dragleave = () => {
		$host.removeClass("is-dragover");
	};

	const on_drop = (event) => {
		if (control.value || is_field_read_only()) return;
		event.preventDefault();
		$host.removeClass("is-dragover");
		const files = event.originalEvent?.dataTransfer?.files;
		if (files?.length) {
			open_uploader(files);
		}
	};

	$input_area.on("click.diw_dropzone", on_zone_click);
	$host.on("dragover.diw_dropzone", on_dragover);
	$host.on("dragleave.diw_dropzone", on_dragleave);
	$host.on("drop.diw_dropzone", on_drop);

	control._diw_dropzone_cleanup = () => {
		$host.off(".diw_dropzone");
		$input_area.off(".diw_dropzone");
		$(frm.wrapper).off(
			"form-refresh.diw_import_file_card diw-import-preview-ready.diw_import_file_card"
		);
		$host.removeClass("diw-file-dropzone-host is-dragover has-file is-read-only");
		$input_area.removeClass("diw-file-dropzone-target");
		$ui.remove();
		$card_mount.remove();
		control.on_upload_complete = original_on_upload_complete;
		control.set_input = original_set_input;
		delete control._diw_sync_from_doc;
	};

	const sync_has_file = () => {
		const has_file = Boolean(control.value);
		const is_read_only = is_field_read_only();
		$host.toggleClass("has-file", has_file);
		$host.toggleClass("is-read-only", is_read_only);

		if (has_file) {
			// Read-only attach uses disp_area — swap it for our file card.
			if (is_read_only) {
				$(control.disp_area)?.addClass("hide");
				$(control.input_area)?.removeClass("hide");
			}
			control.$input?.hide();
			control.$value?.hide();
			$card_mount.removeClass("hide");
			render_import_file_card(control, frm, $card_mount);
			return;
		}

		$card_mount.addClass("hide").empty();
		control.$value?.hide();
		if (!is_read_only) {
			control.$input?.show();
		}
	};

	const rerender_card = () => {
		if (control.value) {
			render_import_file_card(control, frm, $card_mount);
		}
	};

	const sync_from_doc = () => {
		const value = frm.doc?.import_file || null;
		if (value === control.value) {
			sync_has_file();
			return;
		}
		control.value = value;
		original_set_input(value);
		sync_has_file();
	};
	control._diw_sync_from_doc = sync_from_doc;

	sync_from_doc();

	$(frm.wrapper).on(
		"form-refresh.diw_import_file_card diw-import-preview-ready.diw_import_file_card",
		() => {
			sync_from_doc();
			rerender_card();
		}
	);

	control.set_input = (value, dataurl) => {
		original_set_input(value, dataurl);
		sync_has_file();
	};

	// Attach skips set_input when the model already has the same URL — force UI sync.
	control.on_upload_complete = async function (attachment) {
		const file_url = attachment?.file_url;
		await original_on_upload_complete.call(this, attachment);
		if (!file_url) return;
		this.value = file_url;
		original_set_input(file_url);
		sync_has_file();
		frm.trigger("import_file");
		frm.trigger("update_primary_action");
		frm.layout?.refresh_dependency();
		$(frm.wrapper).triggerHandler("form-refresh", [frm]);
	};

	const original_refresh_input = control.refresh_input?.bind(control);
	if (original_refresh_input) {
		control.refresh_input = function () {
			original_refresh_input();
			sync_from_doc();
		};
	}
}

/**
 * Saved Google Sheet URL bar (link icon + URL + Clear), same pattern as the file card.
 */
function render_google_sheet_card(control, frm, $mount) {
	const url = frm.doc?.google_sheets_url || control.value;
	if (!$mount?.length || !url) return;

	const link_icon = frappe.utils.icon("link", "sm", "", "", "", true);
	const safe_url = frappe.utils.escape_html(url);
	const safe_href = frappe.utils.escape_html(url);
	const is_read_only = control.df?.read_only || control.disp_status === "Read";

	$mount.html(`
		<div class="diw-google-sheet-card">
			<div class="diw-google-sheet-card-main">
				<span class="diw-google-sheet-card-icon">${link_icon}</span>
				<a class="diw-google-sheet-card-url" href="${safe_href}" target="_blank" rel="noopener noreferrer" title="${safe_url}">${safe_url}</a>
			</div>
			${
				is_read_only
					? ""
					: `<button type="button" class="diw-google-sheet-clear-btn" data-action="clear_google_sheet">${__(
							"Clear"
					  )}</button>`
			}
		</div>
	`);

	frappe.utils.bind_actions_with_object($mount, control);
}

/**
 * Google Sheets URL: editable input until saved, then link bar with Clear (like attach row).
 */
function enhance_google_sheets_url_input(control) {
	if (!control?.$wrapper || control._diw_google_sheet_enhanced) return;

	control.make_input?.();
	const $input_area = $(control.input_area);
	if (!$input_area.length || !control.$input?.length) return;

	control._diw_google_sheet_enhanced = true;

	const $host = control.$wrapper.closest(".diw-frm-field");
	$host.addClass("diw-google-sheet-host");

	const $card_mount = $('<div class="diw-google-sheet-card-mount hide"></div>');
	$input_area.addClass("diw-google-sheet-input-area").append($card_mount);

	const original_set_input = control.set_input.bind(control);

	const is_meta_read_only = () => control.df?.read_only || control.disp_status === "Read";

	const get_sheet_url = () => (frm.doc?.google_sheets_url || control.value || "").trim();

	const is_sheet_locked = () => {
		const url = get_sheet_url();
		if (!url) return false;
		if (is_meta_read_only()) return true;
		if (frm.doc.__islocal) return false;
		return !frm.is_dirty?.();
	};

	const sync_sheet_ui = () => {
		const url = get_sheet_url();
		const has_value = Boolean(url);
		const locked = is_sheet_locked() && has_value;

		$host.toggleClass("is-locked", locked);
		$host.toggleClass("has-value", has_value);

		if (locked) {
			control.$input?.hide();
			control.$value?.hide();
			$(control.disp_area)?.addClass("hide");
			$card_mount.empty();
			render_google_sheet_card(control, frm, $card_mount);
			if ($card_mount.children().length) {
				$card_mount.removeClass("hide");
			} else {
				$card_mount.addClass("hide");
				control.$input?.show().prop("readonly", false);
			}
			return;
		}

		$card_mount.addClass("hide").empty();
		$(control.disp_area)?.addClass("hide");
		control.$value?.hide();
		if (!is_meta_read_only()) {
			control.$input?.show().prop("readonly", false).removeAttr("aria-readonly");
		}
	};

	const sync_from_doc = () => {
		const value = frm.doc?.google_sheets_url || null;
		if (value !== control.value) {
			control.value = value;
			original_set_input(value);
		}
		sync_sheet_ui();
	};

	control.clear_google_sheet = async () => {
		if (!is_sheet_locked() || is_meta_read_only()) return;

		try {
			await frm.set_value("google_sheets_url", "");
			control.value = "";
			original_set_input("");
			sync_sheet_ui();
			frm.trigger("update_primary_action");
			frm.layout?.refresh_dependency();
			if (frm.is_dirty?.()) {
				await frm.save();
			}
			control.$input?.focus();
		} catch (error) {
			console.error("Failed to clear Google Sheets URL", error);
		}
	};

	control.set_input = (value) => {
		original_set_input(value);
		sync_sheet_ui();
	};

	const original_refresh_input = control.refresh_input?.bind(control);
	if (original_refresh_input) {
		control.refresh_input = function () {
			original_refresh_input();
			sync_from_doc();
		};
	}

	control._diw_sync_from_doc = sync_from_doc;
	sync_from_doc();

	// Run after layout refresh_fields — form-refresh fires too early and gets overwritten.
	$(frm.wrapper).on("dirty.diw_google_sheet refresh-fields.diw_google_sheet", sync_from_doc);

	control._diw_google_sheet_cleanup = () => {
		$(frm.wrapper).off(".diw_google_sheet");
		$card_mount.remove();
		$input_area.removeClass("diw-google-sheet-input-area");
		$host.removeClass("diw-google-sheet-host is-locked has-value");
		control.set_input = original_set_input;
		if (original_refresh_input) {
			control.refresh_input = original_refresh_input;
		}
		delete control.clear_google_sheet;
		delete control._diw_sync_from_doc;
		delete control._diw_google_sheet_enhanced;
		delete control._diw_google_sheet_cleanup;
	};
}

function get_df() {
	const field = frm.fields_dict?.[props.fieldname];
	const df = field?.df || frappe.meta.get_docfield(frm.doctype, props.fieldname, frm.doc.name);
	return { ...df };
}

function sync_value() {
	if (!control) return;
	control.refresh?.();
}

/** The control holds a df copy made at mount; depends_on visibility computed by the
 * layout (refresh-fields) can go stale on it — e.g. import_file stays hidden after
 * the first save flips eval:!doc.__islocal. Re-sync the flag and refresh. */
function sync_dependency_visibility() {
	if (!control?.df) return;
	const live_df = frm.fields_dict?.[props.fieldname]?.df;
	if (!live_df) return;
	if (control.df.hidden_due_to_dependency !== live_df.hidden_due_to_dependency) {
		control.df.hidden_due_to_dependency = live_df.hidden_due_to_dependency;
		control.refresh?.();
	}
}

/** Focus the rendered desk control input (used when switching upload tabs). */
function focus_field() {
	if (!control) return;
	if (props.fieldname === "google_sheets_url") {
		const url = frm.doc?.google_sheets_url;
		const is_saved = url && !frm.doc.__islocal && !frm.is_dirty?.();
		if (is_saved) return;
	}
	nextTick(() => {
		requestAnimationFrame(() => {
			const $input = control.$input || control.$wrapper?.find("input, textarea").first();
			const input_el = $input?.get?.(0);
			input_el?.focus?.();
		});
	});
}

function make_control() {
	if (!el.value) return;
	destroy_control();
	el.value.innerHTML = "";
	const df = get_df();
	if (props.fieldname === "import_file") {
		df.options = {
			restrictions: { allowed_file_types: [".csv", ".xls", ".xlsx"] },
		};
	}

	const df_copy = { ...df, hidden: 0 };
	if (props.fieldname === "import_file") {
		df_copy.label = "";
	}

	control = frappe.ui.form.make_control({
		parent: el.value,
		df: {
			...df_copy,
		},
		frm,
		doctype: frm.doctype,
		docname: props.docname || frm.docname,
		doc: frm.doc,
		render_input: true,
	});

	sync_value();

	if (props.fieldname === "import_file") {
		nextTick(() => enhance_import_file_dropzone(control));
	}
	if (props.fieldname === "google_sheets_url") {
		nextTick(() => enhance_google_sheets_url_input(control));
	}
}

onMounted(() => {
	make_control();
	$(frm.wrapper).on(`refresh-fields.diw_field_${props.fieldname}`, sync_dependency_visibility);
});

onBeforeUnmount(() => {
	$(frm.wrapper).off(`refresh-fields.diw_field_${props.fieldname}`, sync_dependency_visibility);
	destroy_control();
});

watch(
	() => frm.doc?.[props.fieldname],
	async (value, previous) => {
		control?._diw_sync_from_doc?.();
		sync_value();

		if (props.fieldname !== "import_file") return;
		if (value === previous) return;
		if (!frm.doc?.name || frm.is_new?.()) return;
		if (!frm.is_dirty?.() || frappe.ui.form.is_saving) return;

		let saved = false;
		try {
			await frm.save();
			saved = true;
		} catch (error) {
			console.error("Auto-save after import file change failed", error);
		}

		if (saved) {
			frm.trigger("import_file");
			frm.trigger("update_primary_action");
			frm.layout?.refresh_dependency();
			$(frm.wrapper).triggerHandler("form-refresh", [frm]);
		}
	}
);

watch(
	() => props.docname,
	() => make_control()
);

defineExpose({ focus: focus_field });
</script>

<template>
	<div ref="el" class="diw-frm-field" :data-fieldname="fieldname" />
</template>
