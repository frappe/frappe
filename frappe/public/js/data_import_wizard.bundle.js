// Data Import stepper wizard — plain JS view built on standard frappe.ui/desk
// components (make_control field wrappers, frappe.ui.button/progress/empty_state,
// frappe.utils.icon).
// The orchestration lives in data_import.js; this class is only the view layer
// behind the `frm._data_import_wizard` interface (set_step / bump_ui / …).

const WIZARD_STEPS = [
	{ id: "config", label: __("Config") },
	{ id: "preview", label: __("Preview") },
	{ id: "fix_issues", label: __("Fix issues") },
	{ id: "import", label: __("Import") },
];

const STEP_COUNT = WIZARD_STEPS.length;

/** Reparented field wrappers — detached (not removed) on unmount to keep handlers. */
const REPARENTED_FIELDS = [
	"reference_doctype",
	"import_type",
	"mute_emails",
	"submit_after_import",
	"use_csv_sniffer",
	"custom_delimiters",
	"delimiter_options",
	"import_file",
	"google_sheets_url",
	"refresh_google_sheet",
	"import_preview",
	"import_tree_preview",
	"import_warnings",
	"value_mappings",
	"import_log_heading",
	"import_log_preview",
];

/** Landing step when the form loads (mirrors the saved state of the import). */
function get_wizard_initial_step(frm) {
	const doc = frm.doc;
	if (!doc) return 0;
	if (doc.status && doc.status !== "Pending") return 3;
	if (frm.has_import_file?.()) {
		const has_fix_issue_state =
			(doc.skipped_rows || []).length > 0 ||
			(doc.value_mappings || []).length > 0 ||
			parse_template_warnings(frm).length > 0;
		return has_fix_issue_state ? 2 : 1;
	}
	return 0;
}

function parse_template_warnings(frm) {
	try {
		return JSON.parse(frm.doc.template_warnings || "[]") || [];
	} catch (_e) {
		return [];
	}
}

function is_import_complete(status) {
	return ["Success", "Partial Success"].includes(status);
}

/** Whether a stepper marker can be jumped to from the current step. */
function can_go_to_wizard_step(frm, step, current_step) {
	if (step <= current_step) return true;
	if (step === 1) {
		return (
			Boolean(frm.doc.reference_doctype && frm.doc.import_type) &&
			!frm.doc.__islocal &&
			frm.has_import_file?.()
		);
	}
	if (step === 2) {
		return !frm.doc.__islocal && frm.has_import_file?.();
	}
	if (step === 3) {
		return !frm.doc.__islocal && frm.has_import_file?.() && frm.has_import_started?.();
	}
	return false;
}

function is_sr_no_column(col) {
	return col?.header_title === "Sr. No" || col?.header_title === __("Sr. No");
}

// ---- Config-step upload helpers (dropzone + file/sheet cards) --------------

/** Hint under the drop zone; omit size when boot does not expose a limit. */
function get_dropzone_hint_html() {
	const max_bytes = frappe.boot?.max_file_size;
	if (!max_bytes) return "";
	const max_mb = Math.round(max_bytes / (1024 * 1024));
	return `<div class="text-xs text-ink-gray-5">${__(".csv, .xlsx up to {0} MB", [
		max_mb,
	])}</div>`;
}

/** Basename from an attach value (plain path or FILENAME,url form). */
function get_import_file_name(file_url) {
	if (!file_url) return "";
	const match = file_url.match(/^([^:]+),(.+):(.+)$/);
	if (match) return decodeURIComponent(match[1]);
	const segment = file_url.split("/").pop() || file_url;
	return decodeURIComponent(segment.split("?")[0]);
}

/** Resolve the href for an attach value (plain URL or FILENAME,DATA_URL form). */
function get_import_file_href(file_url) {
	if (!file_url) return "";
	const match = file_url.match(/^([^:]+),(.+):(.+)$/);
	if (match) return `${match[2]}:${match[3]}`;
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
	return count === 1 ? __("1 row") : __("{0} rows", [count]);
}

/** Paint the post-upload file card (replaces default attach row styling). */
function render_import_file_card(control, frm, $mount) {
	if (!$mount?.length || !control.value) return;
	const filename = get_import_file_name(control.value);
	const type_label = get_import_file_type_label(filename);
	const row_meta = get_import_file_row_meta(frm);
	const meta_text = row_meta ? `${type_label} · ${row_meta}` : type_label;
	const safe_name = frappe.utils.escape_html(filename);
	const safe_href = frappe.utils.escape_html(get_import_file_href(control.value));
	const is_read_only = control.df?.read_only || control.disp_status === "Read";

	$mount.html(`
		<div class="diw-import-file-card flex items-center justify-between gap-3 w-full border rounded-lg mt-4 px-4 py-3 text-sm bg-surface-base">
			<div class="flex items-center gap-2 min-w-0 flex-1">
				<div class="diw-card-icon-well flex items-center justify-center shrink-0 size-10 rounded bg-surface-gray-2 text-ink-gray-7">${frappe.utils.icon(
					"file-spreadsheet",
					"md",
					"",
					"",
					"",
					true
				)}</div>
				<div class="min-w-0">
					<a class="diw-import-file-card-name block truncate text-base-semibold text-ink-gray-9" href="${safe_href}" target="_blank" rel="noopener noreferrer" title="${safe_name}">${safe_name}</a>
					<div class="text-sm text-muted">${frappe.utils.escape_html(meta_text)}</div>
				</div>
			</div>
			${
				is_read_only
					? ""
					: frappe.ui.button.html({
							label: __("Clear"),
							variant: "outline",
							css_class: "diw-import-file-clear",
							attrs: { "data-action": "clear_attachment" },
					  })
			}
		</div>
	`);
	frappe.utils.bind_actions_with_object($mount, control);
}

/** Saved Google Sheet URL bar (link icon + URL + Clear), like the attach card. */
function render_google_sheet_card(control, frm, $mount) {
	const url = frm.doc?.google_sheets_url || control.value;
	if (!$mount?.length || !url) return;
	const safe_url = frappe.utils.escape_html(url);
	const is_read_only = control.df?.read_only || control.disp_status === "Read";
	$mount.html(`
		<div class="diw-google-sheet-card flex items-center justify-between gap-2 w-full rounded p-2 text-sm bg-surface-gray-2">
			<div class="flex items-center gap-2 min-w-0 flex-1">
				<span class="inline-flex shrink-0 text-muted">${frappe.utils.icon(
					"link",
					"sm",
					"",
					"",
					"",
					true
				)}</span>
				<a class="diw-google-sheet-card-url min-w-0 truncate text-ink-base" href="${safe_url}" target="_blank" rel="noopener noreferrer" title="${safe_url}">${safe_url}</a>
			</div>
			${
				is_read_only
					? ""
					: frappe.ui.button.html({
							label: __("Clear"),
							size: "xs",
							variant: "outline",
							attrs: { "data-action": "clear_google_sheet" },
					  })
			}
		</div>
	`);
	frappe.utils.bind_actions_with_object($mount, control);
}

frappe.provide("frappe.ui");

frappe.ui.DataImportWizard = class DataImportWizard {
	constructor({ wrapper, frm }) {
		this.wrapper = wrapper;
		this.frm = frm;
		this._docname = frm.doc?.name || null;
		this.current_step = cint(frm.wizard_step ?? get_wizard_initial_step(frm));
		this._preview_loading = Boolean(frm._import_preview_loading);
		this._step_initialized = false;
		// Guards against a superseded Fix Issues preview-wait resolving after navigation.
		this._fix_issues_token = 0;
		this.build();
		this.refresh_from_frm();
	}

	// ---- lifecycle ---------------------------------------------------------

	build() {
		this.$root = $(`
			<div class="data-import-custom-ui flex justify-center w-full">
				<div class="diw-shell flex flex-col w-full min-w-0 gap-5">
					<div class="diw-stepper-wrap shrink-0 w-full"></div>
					<div class="diw-card flex flex-col w-full min-w-0 overflow-hidden rounded-lg shadow-sm border bg-surface-base">
						<div class="diw-mobile-step-header shrink-0 pt-4 px-4"></div>
						<div class="flex flex-col flex-1 min-h-0 min-w-0 w-full"><div class="diw-panels flex flex-col flex-1 min-h-0 min-w-0 w-full"></div></div>
						<div class="diw-status-area shrink-0 px-5 pb-4"></div>
						<div class="diw-footer flex items-center justify-between shrink-0 w-full border-t mt-auto py-4 px-5">
							<div class="diw-footer-left"></div>
							<div class="diw-footer-right flex items-center gap-2"></div>
						</div>
					</div>
				</div>
			</div>
		`);
		$(this.wrapper).empty().append(this.$root);

		this.$card = this.$root.find(".diw-card");
		this.$stepper_wrap = this.$root.find(".diw-stepper-wrap");
		this.$mobile_header = this.$root.find(".diw-mobile-step-header");
		this.$panels = this.$root.find(".diw-panels");
		this.$status = this.$root.find(".diw-status-area");
		this.$footer_left = this.$root.find(".diw-footer-left");
		this.$footer_right = this.$root.find(".diw-footer-right");

		// One card height for every step — sized to the viewport, not step content —
		// so all steps are uniform and long content scrolls inside .diw-step-content.
		this._on_resize = () => {
			if (this._resize_raf) cancelAnimationFrame(this._resize_raf);
			this._resize_raf = requestAnimationFrame(() => this.update_card_height());
		};
		window.addEventListener("resize", this._on_resize, { passive: true });
		this.update_card_height();

		// The preview fetch resolves asynchronously, so the data often lands *after* the
		// Preview step is mounted — and if the pane wasn't laid out yet, the datatable
		// gives up retrying (~40 frames) and never builds, leaving the step stuck on its
		// skeleton until a full page reload. Re-mount the step when the data arrives so
		// the table is built against a visible, measured pane.
		this._on_preview_ready = () => {
			if (this.current_step === 1) this.render_panel();
		};
		$(this.frm.wrapper).on("diw-import-preview-ready.diw_wizard", this._on_preview_ready);
	}

	unmount() {
		if (this._resize_raf) cancelAnimationFrame(this._resize_raf);
		if (this._on_resize) window.removeEventListener("resize", this._on_resize);
		$(this.frm.wrapper).off(".diw_wizard");
		this.detach_reparented_fields();
		this.$root?.remove();
	}

	/** Fixed card height from the viewport; desktop pins height, mobile keeps a floor. */
	update_card_height() {
		if (!this.$card?.length) return;
		// innerWidth/innerHeight can be 0 in some embedded/headless contexts —
		// fall back to the document/screen so we don't collapse to the mobile path.
		const doc_el = document.documentElement;
		const vw = window.innerWidth || doc_el.clientWidth || screen.width || 1024;
		const vh = window.innerHeight || doc_el.clientHeight || screen.height || 768;
		const is_mobile = vw <= 768;
		const reserved = is_mobile ? 145 : 205;
		const floor = is_mobile ? 480 : 620;
		const ceiling = 820;
		const height = Math.max(floor, Math.min(ceiling, vh - reserved));
		this.$card.css({
			"min-height": `${height}px`,
			height: `${height}px`,
			"max-height": `${height}px`,
		});
	}

	/** Detach (not remove) reparented control wrappers so their handlers survive. */
	detach_reparented_fields() {
		for (const fieldname of REPARENTED_FIELDS) {
			this.frm.fields_dict?.[fieldname]?.$wrapper?.detach();
		}
	}

	refresh_from_frm() {
		const frm = this.frm;
		const current_docname = frm.doc?.name || null;
		const prev_docname = this._docname;
		const doc_changed = current_docname !== prev_docname;
		if (doc_changed) {
			// First save renames new-* → DI-xxx on the same form session — keep the
			// user's current step (Config). Only recompute the landing step when
			// opening a different document.
			const is_first_save_rename =
				prev_docname &&
				String(prev_docname).startsWith("new-") &&
				current_docname &&
				!String(current_docname).startsWith("new-");

			this._docname = current_docname;
			if (!is_first_save_rename) {
				this._step_initialized = false;
				this._upload_source = null;
				this._preview_panes = null;
				// Re-read from the frm: a leftover `true` here would keep Next disabled and
				// the preview stuck on its loading skeleton for the new document.
				this._preview_loading = Boolean(frm._import_preview_loading);
			}
		}
		let target;
		if (!this._step_initialized) {
			target = get_wizard_initial_step(frm);
			this._step_initialized = true;
		} else {
			target = cint(frm.wizard_step ?? this.current_step);
		}
		frm.wizard_step = target;
		this.set_step(target);
	}

	// ---- public interface used by data_import.js ---------------------------

	set_step(step) {
		step = Math.max(0, Math.min(cint(step), STEP_COUNT - 1));
		this.current_step = step;
		this.frm.wizard_step = step;
		this.render_stepper();
		this.render_mobile_header();
		this.render_panel();
		this.render_status();
		this.render_footer();
	}

	bump_ui() {
		this.render_stepper();
		this.render_footer();
		this.render_status();
	}

	refresh_fix_issues() {
		if (this.current_step === 2) {
			this.render_panel();
			this.render_footer();
		}
	}

	set_preview_loading(loading) {
		this._preview_loading = Boolean(loading);
		this.render_footer();
	}

	// ---- stepper -----------------------------------------------------------

	render_stepper() {
		if (!this.stepper) {
			this.stepper = new frappe.ui.Stepper({
				steps: WIZARD_STEPS.map((step) => ({ label: step.label })),
				current: this.current_step,
				label: __("Import steps"),
				// re-checked on every render, so lock state follows the wizard
				is_locked: (index) => !can_go_to_wizard_step(this.frm, index, this.current_step),
				// completion is factual, so checks survive navigating back:
				// config/preview/fix are done once the import has started,
				// the import step once it finished
				is_completed: (index) => {
					if (index < this.current_step) return true;
					if (index <= 2) return Boolean(this.frm.has_import_started?.());
					return is_import_complete(this.frm.doc?.status);
				},
				on_step_click: (index) => this.on_step_click(index),
				// locked clicks route to the same handler — its can_go check
				// fails and shows the "complete the earlier steps" alert
				on_locked_click: (index) => this.on_step_click(index),
			});
			this.$stepper_wrap.append(this.stepper.$el);
			return;
		}
		this.stepper.set_current(this.current_step);
	}

	render_mobile_header() {
		// the stepper's compact mode: segmented progress + "Step 2 of 4"
		if (!this.mobile_stepper) {
			this.mobile_stepper = new frappe.ui.Stepper({
				steps: WIZARD_STEPS.map((step) => ({ label: step.label })),
				current: this.current_step,
				compact: true,
				label: __("Import steps"),
			});
			this.$mobile_header.append(this.mobile_stepper.$el);
			return;
		}
		this.mobile_stepper.set_current(this.current_step);
	}

	// ---- panels ------------------------------------------------------------

	render_panel() {
		const step = this.current_step;
		this._preview_panes = null;
		// Detach (not remove) reparented control wrappers before emptying — jQuery
		// .empty() would otherwise strip their event handlers (e.g. the dropzone click).
		this.detach_reparented_fields();
		this.$panels.empty();
		const $panel = $(
			`<section class="diw-step-panel flex flex-col flex-1 min-h-0 min-w-0 w-full" data-step="${step}"></section>`
		);
		const $content = $(
			'<div class="diw-step-content flex-1 min-h-0 min-w-0 w-full overflow-auto py-4 px-5"></div>'
		).appendTo($panel);
		this.$panels.append($panel);

		if (step === 0) {
			this.mount_config($content);
		} else if (step === 1) {
			this.mount_preview($content);
		} else if (step === 2) {
			this.mount_fix_issues($content);
		} else if (step === 3) {
			this.mount_import($content);
		}
	}

	reparent_field($into, fieldname) {
		const field = this.frm.fields_dict?.[fieldname];
		if (field?.$wrapper?.length) {
			$into.append(field.$wrapper);
			return true;
		}
		return false;
	}

	mount_config($content) {
		const frm = this.frm;
		const $step = $('<div class="diw-config-step flex flex-col gap-4"></div>');

		// Import settings — two-column grid of the configuration fields. The grid
		// container purposely does NOT use the frappe `section-body` class (whose flex
		// rules would override display:grid and collapse the columns).
		const $settings = $(`
			<div class="diw-config-section m-0 p-0 border-0 shadow-none bg-transparent">
				<div class="diw-config-head m-0 p-0 border-0 shadow-none bg-transparent mb-4"><span class="diw-section-head-title text-base-semibold">${__(
					"Import settings"
				)}</span></div>
				<div class="diw-config-grid grid items-start w-full gap-5">
					<div class="diw-config-column diw-config-main w-full min-w-0 m-0 p-0"></div>
					<div class="diw-config-column diw-config-options w-full min-w-0 m-0 p-0"></div>
				</div>
			</div>
		`);
		const $main = $settings.find(".diw-config-main");
		const $options = $settings.find(".diw-config-options");
		["reference_doctype", "import_type"].forEach((fn) => this.reparent_field($main, fn));
		[
			"mute_emails",
			"submit_after_import",
			"custom_delimiters",
			"delimiter_options",
			"use_csv_sniffer",
		].forEach((fn) => this.reparent_field($options, fn));
		this.maybe_render_pending_imports_banner($settings);
		$step.append($settings);

		// Upload file — header with Download Template, source tabs, then panes.
		const $upload = $(`
			<div class="diw-upload-section mt-4 pt-4 border-t">
				<div class="flex items-center justify-between gap-4 mb-2">
					<span class="diw-section-head-title text-base-semibold">${__("Upload file")}</span>
					<span class="diw-upload-header-action"></span>
				</div>
			</div>
		`);
		const $download_template = frappe.ui.button({
			label: __("Download Template"),
			variant: "outline",
			onclick: () => frm.events.download_template(frm),
		});
		if (this.has_import_settings()) {
			$upload.find(".diw-upload-header-action").empty().append($download_template);
		}

		if (!this.has_import_settings()) {
			$upload.append(
				`<div class="text-sm text-muted py-6">${__(
					"Select a Document Type to upload a file or Google Sheet."
				)}</div>`
			);
			$step.append($upload);
			$content.append($step);
			return;
		}

		// Tabs only when a source still needs choosing: once a file is attached (or a
		// Google Sheet URL is saved and unchanged) the source is fixed, so we show just
		// that source's card without tabs.
		const show_tabs = this.should_show_upload_tabs();
		const $file_pane = $('<div class="diw-frm-field w-full"></div>');
		this.reparent_field($file_pane, "import_file");
		const $sheet_pane = $('<div class="diw-frm-field w-full"></div>');
		this.reparent_field($sheet_pane, "google_sheets_url");
		this.reparent_field($sheet_pane, "refresh_google_sheet");
		this._upload_panes = { file_upload: $file_pane, google_sheet: $sheet_pane };

		// Standard Tabs owns both the full-width tab rail and its panels.
		const initial_source = show_tabs
			? this._upload_source || (frm.doc.google_sheets_url ? "google_sheet" : "file_upload")
			: frm.doc.google_sheets_url && !frm.doc.import_file
			? "google_sheet"
			: "file_upload";
		if (show_tabs) {
			const $tabs = frappe.ui.tabs({
				active: initial_source === "google_sheet" ? 1 : 0,
				css_class: "diw-upload-tabs",
				tabs: [
					{
						label: __("File upload"),
						icon: "upload",
						content: $file_pane,
					},
					{
						label: __("Google Sheet"),
						icon: "link",
						content: $sheet_pane,
					},
				],
				on_change: (index) =>
					this.select_upload_source(index === 1 ? "google_sheet" : "file_upload"),
			});
			this.upload_tabs = $tabs.data("es-tabs");
			$upload.append($tabs);
		} else {
			this.upload_tabs = null;
			$upload.append(initial_source === "google_sheet" ? $sheet_pane : $file_pane);
		}

		$step.append($upload);
		$content.append($step);
		frm.layout?.refresh_dependency?.();
		this.force_show_upload_fields();

		this.enhance_import_file_dropzone(frm.fields_dict.import_file);
		this.enhance_google_sheets_url(frm.fields_dict.google_sheets_url);
		this.select_upload_source(initial_source);
	}

	/** Document Type + Import Type are set (upload UI can show before save). */
	has_import_settings() {
		const doc = this.frm.doc;
		return Boolean(doc?.reference_doctype && doc?.import_type);
	}

	/** In the dialog, on a brand-new import, nudge the user to resume an existing Pending
	 *  import for this DocType (file attached) instead of starting a duplicate. Rendered
	 *  just below the "Import settings" heading. */
	maybe_render_pending_imports_banner($settings) {
		const frm = this.frm;
		const doctype = frm.doc?.reference_doctype;
		if (!frm.in_dialog || !frm.is_new() || !doctype) return;

		const $slot = $('<div class="diw-pending-imports-banner mb-4"></div>');
		$settings.find(".diw-config-head").after($slot);

		frappe.db
			.count("Data Import", {
				filters: {
					reference_doctype: doctype,
					status: "Pending",
					import_file: ["is", "set"],
				},
			})
			.then((count) => {
				count = cint(count);
				// Drop a stale async result (doctype changed, saved, or left the Config step).
				if (
					!count ||
					!frm.is_new() ||
					frm.doc.reference_doctype !== doctype ||
					this.current_step !== 0
				) {
					$slot.remove();
					return;
				}
				const message =
					count === 1
						? __("You have 1 pending {0} import with a file attached.", [__(doctype)])
						: __("You have {0} pending {1} imports with files attached.", [
								count,
								__(doctype),
						  ]);
				const $link = frappe.ui.button({
					label: __("Review pending imports"),
					variant: "outline",
					size: "xs",
					icon_right: "arrow-right",
					onclick: () => {
						frm._data_import_dialog?.hide?.();
						// Pending imports of this DocType that have a file — matches the count.
						frappe.set_route("List", "Data Import", {
							reference_doctype: doctype,
							status: "Pending",
							import_file: ["is", "set"],
						});
					},
				});
				$slot
					.empty()
					.append(frappe.ui.alert({ title: message, theme: "blue", footer: $link }));
			})
			.catch(() => $slot.remove());
	}

	/**
	 * Keep Import File / Google Sheets visible on Config once settings are filled,
	 * including on unsaved (new) docs. Clears dependency-hide from layout refresh.
	 */
	force_show_upload_fields() {
		const frm = this.frm;
		if (!this.has_import_settings()) return;

		const import_file_df = frm.fields_dict?.import_file?.df;
		if (import_file_df) {
			import_file_df.hidden = 0;
			import_file_df.hidden_due_to_dependency = false;
			frm.refresh_field("import_file");
		}

		const sheets_df = frm.fields_dict?.google_sheets_url?.df;
		if (sheets_df) {
			sheets_df.hidden = 0;
			sheets_df.hidden_due_to_dependency = Boolean(frm.doc.import_file);
			frm.refresh_field("google_sheets_url");
		}
	}

	/** Show the source tabs only while the upload source is still undecided. */
	should_show_upload_tabs() {
		const frm = this.frm;
		if (!this.has_import_settings()) return false;
		if (!frm.fields_dict?.google_sheets_url) return false;
		const sheets_selectable = !frm.doc.import_file;
		const has_saved_sheet = Boolean(frm.doc.google_sheets_url) && !frm.is_dirty?.();
		return sheets_selectable && !has_saved_sheet;
	}

	/** Toggle the File upload / Google Sheet panes and keep the tab in sync. */
	select_upload_source(source) {
		source = source === "google_sheet" ? "google_sheet" : "file_upload";
		this._upload_source = source;
		this.upload_tabs?.set_active?.(source === "google_sheet" ? 1 : 0, { silent: true });
		if (!this.upload_tabs) {
			this._upload_panes?.file_upload?.toggle(source === "file_upload");
			this._upload_panes?.google_sheet?.toggle(source === "google_sheet");
		}
		if (source === "file_upload") {
			this.frm.fields_dict?.import_file?._diw_sync_from_doc?.();
		} else {
			this.frm.fields_dict?.google_sheets_url?._diw_sync_from_doc?.();
		}
	}

	/**
	 * After FileUploader finishes: attach the file URL, save if the Data Import is
	 * still new (preview needs a real name), otherwise just persist when dirty and preview.
	 */
	bind_import_file_upload_complete(control) {
		const frm = this.frm;
		control.on_upload_complete = async function (attachment) {
			const file_url = attachment?.file_url;
			if (!file_url) return;

			// Do not call Attach's default handler — it fires an unawaited save and
			// races preview against a temporary new-* name.
			await this.parse_validate_and_set_in_model(file_url);
			frm.attachments?.update_attachment?.(attachment);
			control._diw_sync_from_doc?.();

			try {
				if (frm.is_new()) {
					await frm.save();
					// after_save triggers preview once the doc has a real name
					return;
				}
				if (frm.is_dirty() && !frappe.ui.form.is_saving) {
					await frm.save();
				}
			} catch (error) {
				console.error("Auto-save after import file upload failed", error);
				return;
			}

			frm.trigger("import_file");
			frm.trigger("update_primary_action");
			frm.layout?.refresh_dependency();
			$(frm.wrapper).triggerHandler("form-refresh", [frm]);
		};
	}

	/** Turn the reparented Attach control into a dashed drag-and-drop zone + file card. */
	enhance_import_file_dropzone(control) {
		const frm = this.frm;
		if (!control?.$wrapper) return;
		// Re-apply on every mount: a fresh pane is created each render, so the host
		// class must be re-added even when the control itself is already enhanced.
		const $host = control.$wrapper.closest(".diw-frm-field");
		$host.addClass("diw-file-dropzone-host");
		// Always rebind upload completion (control survives remounts across code changes).
		this.bind_import_file_upload_complete(control);
		if (control._diw_dropzone_enhanced) {
			control._diw_sync_from_doc?.();
			return;
		}
		if (!control.has_input) control.make_input?.();
		const $input_area = $(control.input_area);
		if (!$input_area.length) return;
		control._diw_dropzone_enhanced = true;

		const $ui = $(`
			<div class="diw-file-dropzone-ui flex flex-col items-center text-center gap-1 pointer-events-none" aria-hidden="true">
				<div class="diw-file-dropzone-icon text-muted">${frappe.utils.icon(
					"cloud-upload",
					"md",
					"",
					"",
					"",
					true
				)}</div>
				<div class="diw-file-dropzone-text text-sm text-muted max-w-sm">${__(
					"Drag a CSV or Excel file here, or click to browse"
				)}</div>
				${get_dropzone_hint_html()}
			</div>
		`);
		$input_area.addClass("diw-file-dropzone-target").append($ui);
		const $card_mount = $('<div class="hide"></div>');
		$input_area.append($card_mount);

		const original_set_input = control.set_input.bind(control);
		const is_read_only = () => control.df?.read_only || control.disp_status === "Read";

		const open_uploader = (files) => {
			if (control._diw_opening_uploader) return;
			const existing_uploader_visible = Boolean(
				control.file_uploader?.dialog?.$wrapper?.is?.(":visible")
			);
			if (existing_uploader_visible) return;

			control._diw_opening_uploader = true;
			control.set_upload_options?.();
			if (files?.length) control.upload_options = { ...control.upload_options, files };
			control.file_uploader = new frappe.ui.FileUploader(control.upload_options);
			setTimeout(() => {
				control._diw_opening_uploader = false;
			}, 350);
		};
		const on_zone_click = (event) => {
			if (control.value || is_read_only() || $(event.target).closest("[data-action]").length)
				return;
			// Attach control's own button already opens the uploader; avoid double-open
			// when its click bubbles to the dropzone host.
			if ($(event.target).closest(".btn-attach").length) return;
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation?.();
			control.on_attach_click?.();
		};
		// Bind to input_area (persists across reparents), not the pane (recreated each
		// render); toggle the drag state on whichever host currently wraps it.
		const host_of = () => $input_area.closest(".diw-file-dropzone-host");
		const on_dragover = (event) => {
			if (control.value || is_read_only()) return;
			event.preventDefault();
			host_of().addClass("is-dragover");
		};
		const on_drop = (event) => {
			if (control.value || is_read_only()) return;
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation?.();
			host_of().removeClass("is-dragover");
			const files = event.originalEvent?.dataTransfer?.files;
			if (files?.length) open_uploader(files);
		};
		$input_area
			.off(".diw_dropzone")
			.on("click.diw_dropzone", on_zone_click)
			.on("dragover.diw_dropzone", on_dragover)
			.on("dragleave.diw_dropzone", () => host_of().removeClass("is-dragover"))
			.on("drop.diw_dropzone", on_drop);

		const sync_has_file = () => {
			const has_file = Boolean(control.value);
			const read_only = is_read_only();
			host_of().toggleClass("has-file", has_file).toggleClass("is-read-only", read_only);
			if (has_file) {
				if (read_only) {
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
			if (!read_only) control.$input?.show();
		};

		const sync_from_doc = () => {
			const value = frm.doc?.import_file || null;
			if (value !== control.value) {
				control.value = value;
				original_set_input(value);
			}
			sync_has_file();
		};
		control._diw_sync_from_doc = sync_from_doc;
		sync_from_doc();

		$(frm.wrapper).on(
			"form-refresh.diw_import_file_card diw-import-preview-ready.diw_import_file_card",
			sync_from_doc
		);

		control.set_input = (value, dataurl) => {
			original_set_input(value, dataurl);
			sync_has_file();
		};
	}

	/** Google Sheets URL: editable input until saved, then a link bar with Clear. */
	enhance_google_sheets_url(control) {
		const frm = this.frm;
		if (!control?.$wrapper) return;
		const $host = control.$wrapper.closest(".diw-frm-field");
		$host.addClass("diw-google-sheet-host");
		if (control._diw_google_sheet_enhanced) {
			control._diw_sync_from_doc?.();
			return;
		}
		control.make_input?.();
		const $input_area = $(control.input_area);
		if (!$input_area.length || !control.$input?.length) return;
		control._diw_google_sheet_enhanced = true;
		const $card_mount = $('<div class="hide"></div>');
		$input_area.append($card_mount);

		// Resolve the current host each time — the pane is recreated on every render.
		const host_of = () => $input_area.closest(".diw-google-sheet-host");
		const original_set_input = control.set_input.bind(control);
		const is_meta_read_only = () => control.df?.read_only || control.disp_status === "Read";
		const get_url = () => (frm.doc?.google_sheets_url || control.value || "").trim();
		const is_locked = () => {
			const url = get_url();
			if (!url) return false;
			if (is_meta_read_only()) return true;
			if (frm.doc.__islocal) return false;
			return !frm.is_dirty?.();
		};

		const sync_ui = () => {
			const url = get_url();
			const locked = is_locked() && Boolean(url);
			host_of().toggleClass("is-locked", locked).toggleClass("has-value", Boolean(url));
			if (locked) {
				control.$input?.hide();
				control.$value?.hide();
				$card_mount.empty();
				render_google_sheet_card(control, frm, $card_mount);
				$card_mount.removeClass("hide");
				return;
			}
			$card_mount.addClass("hide").empty();
			control.$value?.hide();
			if (!is_meta_read_only()) control.$input?.show().prop("readonly", false);
		};

		const sync_from_doc = () => {
			const value = frm.doc?.google_sheets_url || null;
			if (value !== control.value) {
				control.value = value;
				original_set_input(value);
			}
			sync_ui();
		};
		control._diw_sync_from_doc = sync_from_doc;

		control.clear_google_sheet = async () => {
			if (!is_locked() || is_meta_read_only()) return;
			await frm.set_value("google_sheets_url", "");
			control.value = "";
			original_set_input("");
			sync_ui();
			frm.trigger("update_primary_action");
			frm.layout?.refresh_dependency();
			if (frm.is_dirty?.()) await frm.save();
			control.$input?.focus();
		};

		control.set_input = (value) => {
			original_set_input(value);
			sync_ui();
		};

		sync_from_doc();
		$(frm.wrapper).on("dirty.diw_google_sheet refresh-fields.diw_google_sheet", sync_from_doc);
	}

	mount_preview($content) {
		const frm = this.frm;
		const is_tree = frm.is_tree_doctype?.() ?? false;
		const $step = $('<div class="diw-preview-step"></div>');
		const $table_pane = $('<div class="diw-preview-pane-table min-h-0 min-w-0 w-full"></div>');

		if (!is_tree) {
			this.preview_tabs = null;
			this._preview_panes = { tree: null, table: $table_pane, is_tree };
			$step.append($table_pane);
			$content.append($step);
			frm.events.mount_preview_step(frm, { tree_el: null, table_el: $table_pane.get(0) });
			return;
		}

		const $tree_pane = $('<div class="diw-preview-pane-tree min-h-0 min-w-0 w-full"></div>');
		// Remembered tab, so a re-render (e.g. when the preview resolves) doesn't yank
		// the user back to Tree.
		const active = this._preview_tab === "table" ? 1 : 0;
		// frappe.ui.Tabs owns the panels and their visibility — these are two views of
		// the same data, which is exactly what Tabs is for (Pills/TabButtons are for
		// picking a value).
		this.preview_tabs = new frappe.ui.Tabs({
			css_class: "diw-preview-tabs",
			active,
			tabs: [
				{ label: __("Tree"), icon: "folder-tree", content: $tree_pane },
				{ label: __("Table"), icon: "table-2", content: $table_pane },
			],
			on_change: (index) => this.select_preview_tab(index === 1 ? "table" : "tree"),
		});
		$step.append(this.preview_tabs.el);
		$content.append($step);

		this._preview_panes = { tree: $tree_pane, table: $table_pane, is_tree };
		this._preview_tab = active === 1 ? "table" : "tree";

		frm.events.mount_preview_step(frm, {
			tree_el: $tree_pane.get(0),
			table_el: $table_pane.get(0),
		});
	}

	select_preview_tab(tab) {
		if (!this._preview_panes?.is_tree) return;
		this._preview_tab = tab;
		this.preview_tabs?.set_active?.(tab === "table" ? 1 : 0, { silent: true });
		if (tab === "table") {
			// Tabs mounts a panel lazily on first activation, so the datatable may have
			// been built against a detached pane — re-render now that it's laid out.
			this.frm.events.refresh_wizard_table_preview?.(this.frm);
		}
	}

	mount_fix_issues($content) {
		const frm = this.frm;
		// Value mappings come straight off the saved doc, but warnings are only known once
		// the preview fetch resolves — rendering now would show the mappings alone and pop
		// the warnings in a few seconds later. Wait behind a skeleton, then render once.
		if (frm.has_import_file?.() && !frm._import_preview_ready) {
			this.render_fix_issues_skeleton($content);
			const token = ++this._fix_issues_token;
			Promise.resolve(frm.events.ensure_import_preview_ready(frm))
				.catch(() => null)
				.then(() => {
					// Ignore if the user moved on / another load superseded this one.
					if (token !== this._fix_issues_token || this.current_step !== 2) return;
					this.render_panel();
					this.render_footer();
				});
			return;
		}
		const state = frm.events.mount_fix_issues_step(frm, $content.get(0)) || {};
		if (!state.has_issues) {
			this.render_fix_issues_empty($content, state);
		}
	}

	/** Placeholder while the preview resolves — generic skeleton rows, not a pixel-perfect mock. */
	render_fix_issues_skeleton($content) {
		const sk = (width, height = "14px") =>
			frappe.ui.skeleton.html({ width, height, css_class: "rounded" });
		$content.empty().append(`
			<div class="flex flex-col gap-3 w-full" role="status" aria-busy="true" aria-label="${frappe.utils.escape_html(
				__("Checking import file for issues...")
			)}">
				${sk("55%", "20px")}
				${sk("100%")}${sk("92%")}${sk("88%")}
				${sk("35%", "18px")}
				${sk("100%", "36px")}${sk("100%", "36px")}${sk("100%", "36px")}
			</div>
		`);
	}

	render_fix_issues_empty($content, state) {
		const frm = this.frm;
		const is_complete = is_import_complete(frm.doc.status);
		let subtitle;
		if (!frm.has_import_file?.()) {
			subtitle = __("Attach an import file to validate rows and mappings.");
		} else if (is_complete) {
			subtitle = __(
				"This import is complete. There are no pending warnings or mapping issues."
			);
		} else {
			subtitle = __("No warnings or mapping issues were found. You can continue to import.");
		}

		const preview_data = state?.preview_data || frm.import_preview?.preview_data || null;
		const rows_checked = cint(
			preview_data?.total_number_of_rows ||
				preview_data?.data?.length ||
				frm.doc.payload_count ||
				0
		);
		const rows_skipped = cint(state?.skipped_rows_count || frm.doc.skipped_rows?.length || 0);
		const columns = preview_data?.columns || [];
		const columns_matched = columns.filter(
			(col) => !is_sr_no_column(col) && !col?.skip_import && Boolean(col?.df)
		).length;

		// Icon well + title + description come from the component; the stats row below
		// is composed from the shared utility classes, the way empty_state itself is.
		const $empty = frappe.ui.empty_state({
			icon: "list-checks",
			title: __("No issues to fix"),
			description: subtitle,
			css_class: "min-h-96",
		});

		if (frm.has_import_file?.()) {
			const stat = (value, label, css_class = "", divider = false) => `
				<div class="flex flex-col items-center justify-center flex-1 gap-1 p-4${
					divider ? " diw-fix-empty-stat--divided border-s" : ""
				}" role="listitem">
					<div class="text-2xl-semibold text-ink-gray-8 ${css_class}">${frappe.utils.escape_html(
				String(value)
			)}</div>
					<div class="text-sm text-ink-gray-5 text-center">${frappe.utils.escape_html(label)}</div>
				</div>
			`;
			$empty.append(`
				<div class="diw-fix-empty-stats flex w-full max-w-4xl border rounded-lg overflow-hidden bg-surface-base mt-2" role="list" aria-label="${frappe.utils.escape_html(
					__("Fix issues summary")
				)}">
					${stat(rows_checked, __("Rows checked"))}
					${stat(columns_matched, __("Columns matched"), "", true)}
					${stat(rows_skipped, __("Rows skipped"), "", true)}
				</div>
			`);
		}

		$content.empty().append($empty);
	}

	mount_import($content) {
		this.frm.events.mount_import_step(this.frm, $content.get(0));
	}

	// ---- status ------------------------------------------------------------

	render_status() {
		const frm = this.frm;
		this.$status.empty();

		const in_import_step = cint(frm.wizard_step) === 3;
		const import_running = Boolean(
			frm.import_in_progress || frm.doc?.status === "In Progress"
		);
		// The Import step renders its own progress hero — keep the status bar quiet there.
		if (in_import_step && import_running) return;

		const $msg = frm.layout?.msg_area;
		const raw_message = ($msg?.text() || "").trim();
		if (raw_message) {
			const safe = frappe.utils.escape_html(raw_message).replace(/\n/g, "<br>");
			$(`<div class="p-4 rounded border bg-surface-gray-2">${safe}</div>`).appendTo(
				this.$status
			);
		}

		const $progress = frm.dashboard?.progress_area;
		if ($progress?.length && $progress.html()?.trim()) {
			this.$status.append($progress.clone(false, false));
		}
	}

	// ---- footer ------------------------------------------------------------

	render_footer() {
		const frm = this.frm;
		const step = this.current_step;
		const is_finished = is_import_complete(frm.doc.status);
		const import_started = Boolean(frm.has_import_started?.());
		const can_import =
			!frm.is_new() && frm.has_import_file?.() && frm.doc.status !== "Success";
		const is_dirty = frm.is_dirty();
		const loading = this._preview_loading;

		const show_back = step !== 0;
		const show_next = step === 0 || step === 1 || (step === 2 && import_started);
		const next_disabled = loading;
		// Fix Issues: Save while dirty; Import only when clean.
		const show_save = step === 2 && can_import && !import_started && is_dirty;
		const show_apply = step === 2 && can_import && !import_started && !is_dirty;
		const apply_disabled = loading;

		this.$footer_left.empty();
		this.$footer_right.empty();

		if (show_back) {
			this.$footer_left.append(
				frappe.ui.button({
					label: __("Back"),
					icon_left: "arrow-left",
					onclick: () => this.on_back(),
				})
			);
		}

		if (show_next) {
			this.$footer_right.append(
				frappe.ui.button({
					label: __("Next"),
					icon_right: "arrow-right",
					disabled: next_disabled,
					onclick: () => this.on_next(),
				})
			);
		}

		if (show_save) {
			this.$footer_right.append(
				frappe.ui.button({
					label: __("Save"),
					variant: "solid",
					disabled: loading,
					onclick: () => this.on_save(),
				})
			);
		}

		if (show_apply) {
			this.$footer_right.append(
				frappe.ui.button({
					label: __("Import"),
					variant: "solid",
					disabled: apply_disabled,
					onclick: () => this.on_apply(),
				})
			);
		}

		// Import step: the navbar has no actions now, so the contextual import controls
		// live on the footer right. Cancel while running; Retry / Report Error after.
		if (step === 3) {
			const status = frm.doc.status;
			const importing = status === "In Progress" || frm.import_in_progress;
			if (importing) {
				this.$footer_right.append(
					frappe.ui.button({
						label: __("Cancel Import"),
						icon_left: "x",
						onclick: () => frm.events.cancel_import(frm),
					})
				);
			} else if (status === "Error") {
				this.$footer_right.append(
					frappe.ui.button({
						label: __("Report Error"),
						variant: "outline",
						icon_left: "triangle-alert",
						onclick: () => frm.events.report_error_now(frm),
					})
				);
				this.$footer_right.append(
					frappe.ui.button({
						label: __("Retry"),
						variant: "solid",
						icon_left: "refresh-cw",
						onclick: () => frm.events.begin_import(frm),
					})
				);
			} else if (status === "Partial Success" || status === "Timed Out") {
				this.$footer_right.append(
					frappe.ui.button({
						label: __("Retry"),
						variant: "solid",
						icon_left: "refresh-cw",
						onclick: () => frm.events.begin_import(frm),
					})
				);
			}
		}
	}

	// ---- navigation --------------------------------------------------------

	on_step_click(index) {
		const frm = this.frm;
		if (!can_go_to_wizard_step(frm, index, this.current_step)) {
			frappe.show_alert({
				message:
					index === 3
						? __("Start the import before opening the Import step.")
						: __("Complete the earlier steps before continuing."),
				indicator: "orange",
			});
			return;
		}
		if (index === this.current_step) return;
		this.on_go(index);
	}

	/** Moving forward from a dirty form saves first (Save + Next), then re-fetches the
	 *  preview on the Preview step so tree warnings recompute against the saved edits. */
	async save_if_dirty() {
		const frm = this.frm;
		if (!frm.is_dirty()) return true;
		try {
			await frm.save();
		} catch (_error) {
			return false;
		}
		if (this.current_step === 1) {
			await Promise.resolve(frm.events.import_file(frm, { force: true })).catch(() => {});
		}
		return true;
	}

	async on_go(step) {
		const frm = this.frm;
		if (step === this.current_step) return;
		if (step < this.current_step) {
			frm.events.go_to_wizard_step(frm, step);
			this.set_step(step);
			return;
		}
		if (!(await this.save_if_dirty())) return;
		const ok = await frm.events.handle_wizard_go_to_step(frm, step, this.current_step);
		if (ok !== false) this.set_step(frm.wizard_step);
	}

	async on_next() {
		const frm = this.frm;
		if (!(await this.save_if_dirty())) return;
		const ok = await frm.events.handle_wizard_go_to_step(
			frm,
			this.current_step + 1,
			this.current_step
		);
		if (ok !== false) this.set_step(frm.wizard_step);
	}

	on_back() {
		this.on_go(this.current_step - 1);
	}

	/** Fix Issues footer: persist dirty mappings/skips, then swap Save → Import. */
	async on_save() {
		const frm = this.frm;
		const ok = await frm.events.handle_wizard_save?.(frm);
		if (ok !== false) {
			frm.trigger("update_primary_action");
			this.render_footer();
		}
	}

	async on_apply() {
		const frm = this.frm;
		if (frm.is_dirty()) {
			frappe.show_alert({
				message: __("Save your changes before importing."),
				indicator: "orange",
			});
			return;
		}
		await frm.events.handle_wizard_apply(frm);
		this.set_step(frm.wizard_step);
	}
};

export default frappe.ui.DataImportWizard;
