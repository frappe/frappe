// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import { place } from "../ui/components/position.js";
import GridPagination from "./grid_pagination";

const BULK_EDIT_CSV_HEADER_ROWS = 1;
const BULK_EDIT_MAX_ROWS = 5000;
const BULK_EDIT_FILE_TYPES = [".csv", ".xlsx", ".xls"];
const BULK_EDIT_ID_FIELDNAME = "name";
const BULK_EDIT_INSERT = "Insert New Records";
const BULK_EDIT_UPDATE = "Update Existing Records";
const BULK_EDIT_UPSERT = "Insert or Update Records";
const BULK_EDIT_IMPORT_TYPES = [BULK_EDIT_INSERT, BULK_EDIT_UPDATE, BULK_EDIT_UPSERT];
const BULK_EDIT_DONT_IMPORT = "Don't Import";
const BULK_EDIT_BLANK_TEMPLATE = "blank_template";
const BULK_EDIT_ALL_RECORDS = "all";
const BULK_EDIT_5_RECORDS = "5_records";
const BULK_EDIT_DURATION_PATTERN = /^(?:(\d+d)?((^|\s)\d+h)?((^|\s)\d+m)?((^|\s)\d+s)?)$/;
const BULK_EDIT_SECONDS_PATTERN = /^\d+$/;
const BULK_EDIT_CHECK_TRUE = ["t", "true", "y", "yes"];
const BULK_EDIT_CHECK_FALSE = ["f", "false", "n", "no"];
const BULK_EDIT_CHECK_VALUES = ["0", "1", ...BULK_EDIT_CHECK_TRUE, ...BULK_EDIT_CHECK_FALSE];
const BULK_EDIT_NUMERIC_FIELDTYPES = ["Int", "Float", "Currency", "Percent"];
const BULK_EDIT_DATA_FORMATS = { Email: "email", Phone: "phone", Name: "name", URL: "url" };
const BULK_EDIT_DEFERRED_FIELDTYPES = ["Date", "Datetime", "Time", "Duration", "Check"];
const BULK_EDIT_DIALOG_SIZE = "extra-large";
const BULK_EDIT_DIALOG_HEIGHT = "calc(90vh - 104px)";
const BULK_EDIT_PREVIEW_ROWS = 10;
const BULK_EDIT_FIX_PAGE_LENGTH = 50;

const TAB_SETUP = 0;
const TAB_UPLOAD = 1;
const TAB_FIX = 2;
const TAB_PREVIEW = 3;
const SYSTEM_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}/;

const BULK_EDIT_VALUE_FORMATTERS = {
	Date: (val) => {
		if (!val) return val;
		return SYSTEM_DATE_PATTERN.test(val) ? val.slice(0, 10) : frappe.datetime.user_to_str(val);
	},
	Datetime: (val) => (val ? frappe.datetime.user_to_str(val) : val),
	Time: (val) => bulk_edit_to_system_time(val),
	Int: (val) => cint(val),
	Check: (val) => {
		const word = cstr(val).trim().toLowerCase();
		if (BULK_EDIT_CHECK_TRUE.includes(word)) return 1;
		if (BULK_EDIT_CHECK_FALSE.includes(word)) return 0;
		return cint(val);
	},
	Float: (val) => flt(val),
	Currency: (val) => flt(val),
	Percent: (val) => flt(val),
	Rating: (val) => flt(val),
	Duration: (val) => bulk_edit_to_seconds(val),
};

const BULK_EDIT_TIME_FORMATS = () => [
	frappe.datetime.get_user_time_fmt(),
	frappe.defaultTimeFormat,
];

export default class BulkEdit {
	constructor(grid) {
		this.grid = grid;
	}

	get_title() {
		return this.grid.df.label || frappe.model.unscrub(this.grid.df.fieldname);
	}

	get_docfields() {
		return [
			{ fieldname: BULK_EDIT_ID_FIELDNAME, label: __("ID"), fieldtype: "Data" },
			...frappe
				.get_meta(this.grid.df.options)
				.fields.filter((df) => frappe.model.is_value_type(df.fieldtype) && !df.read_only),
		];
	}

	show() {
		this.can_import = this.grid.is_editable();
		this.state = {
			import_type: BULK_EDIT_INSERT,
			headers: [],
			rows: [],
			row_numbers: [],
			column_map: {},
			column_overrides: {},
			warnings: [],
			skipped_rows: new Set(),
			google_sheets_url: "",
			library_file_url: "",
			fix_page: 1,
		};

		this.panels = {
			setup: $('<div class="bulk-edit-panel"></div>'),
			upload: $('<div class="bulk-edit-panel"></div>'),
			fix: $('<div class="bulk-edit-panel"></div>'),
			preview: $('<div class="bulk-edit-panel"></div>'),
		};
		this.file_uploader = null;
		this.preview_form = null;
		this.mapping_controls = [];
		this.building_preview = false;
		this.preview_request_id = 0;
		this.link_warnings = [];
		this.cell_controls = {};

		this.make_dialog();
		this.make_setup_form();
		this.watch_cell_pickers();

		this.dialog.show();
		if (this.can_import) this.tabs.set_disabled(TAB_UPLOAD, false);
		this.set_footer();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Upload {0}", [this.get_title()]),
			size: BULK_EDIT_DIALOG_SIZE,
			centered: true,
		});
		$(this.dialog.wrapper).addClass("bulk-edit-dialog");
		this.dialog.modal_body.css({ height: BULK_EDIT_DIALOG_HEIGHT, "overflow-y": "hidden" });
		this.dialog.$body.css({ height: "100%", display: "flex", "flex-direction": "column" });

		this.tab_defs = this.can_import
			? [
					{ label: __("Setup"), content: () => this.panels.setup[0] },
					{
						label: __("Upload"),
						content: () => this.make_upload_panel(),
						disabled: true,
					},
					{
						label: __("Fix Issues"),
						content: () => this.panels.fix[0],
						disabled: true,
					},
					{
						label: __("Preview"),
						content: () => this.panels.preview[0],
						disabled: true,
					},
			  ]
			: [{ label: __("Setup"), content: () => this.panels.setup[0] }];

		this.tabs = new frappe.ui.Tabs({
			tabs: this.tab_defs,
			on_change: (index) => {
				this.stepper.set_current(index);
				this.sync_uploaded_file();
				if (
					[TAB_FIX, TAB_PREVIEW].includes(index) &&
					this.state.rows.length &&
					this._built_step !== index
				) {
					this.build_preview(true);
				}
				this.set_footer();
			},
		});
		this.tabs.$el.addClass("bulk-edit-tabs");
		this.tabs.$el.find(".es-tabs__list").hide();

		this.stepper = new frappe.ui.Stepper({
			steps: this.tab_defs.map((tab) => ({ label: tab.label })),
			is_locked: (index) => this.tab_defs[index].disabled,
			on_step_click: (index) => this.tabs.set_active(index),
		});

		const set_disabled = this.tabs.set_disabled.bind(this.tabs);
		this.tabs.set_disabled = (index, disabled) => {
			set_disabled(index, disabled);
			this.stepper.refresh();
		};

		const $card = $('<div class="bulk-edit-card"></div>');
		this.dialog.$body.append(this.stepper.$el, $card);
		$card.append(this.tabs.$el, this.dialog.footer);

		this.$message = $(
			'<div class="bulk-edit-footer-message indicator red small hide"><span></span></div>'
		).appendTo(this.dialog.custom_actions);

		this.$back = frappe.ui
			.button({
				label: __("Back"),
				size: "sm",
				onclick: () => this.tabs.set_active(this.previous_step()),
			})
			.addClass("hide")
			.prependTo(this.dialog.standard_actions);

		this.tabs.$el.css({
			flex: "1 1 auto",
			"min-height": 0,
			display: "flex",
			"flex-direction": "column",
		});
		this.tabs.$el.find(".es-tabs__panel").css({ flex: "1 1 auto", "min-height": 0 });
	}

	make_setup_form() {
		this.setup_form = new frappe.ui.FieldGroup({
			body: this.panels.setup[0],
			no_submit_on_enter: true,
			fields: [
				{
					fieldtype: "Select",
					fieldname: "import_type",
					label: __("Import Type"),
					options: BULK_EDIT_IMPORT_TYPES.map((value) => ({ label: __(value), value })),
					default: BULK_EDIT_INSERT,
					reqd: 1,
					change: () => {
						const value = this.setup_form.get_value("import_type");
						this.state.import_type = value;
						this.setup_form.set_value(
							"export_records",
							value === BULK_EDIT_INSERT
								? BULK_EDIT_BLANK_TEMPLATE
								: BULK_EDIT_ALL_RECORDS
						);
						this.tabs.set_disabled(TAB_UPLOAD, !value);
						this.refresh_field_options();
					},
				},
				{ fieldtype: "Section Break" },
				{
					fieldtype: "Select",
					fieldname: "file_type",
					label: __("File Type"),
					options: ["Excel", "CSV"],
					default: "Excel",
					reqd: 1,
				},
				{ fieldtype: "Column Break" },
				{
					fieldtype: "Select",
					fieldname: "export_records",
					label: __("Export Type"),
					options: [
						{ label: __("Blank Template"), value: BULK_EDIT_BLANK_TEMPLATE },
						{ label: __("All Records"), value: BULK_EDIT_ALL_RECORDS },
						{ label: __("5 Records"), value: BULK_EDIT_5_RECORDS },
					],
					default: BULK_EDIT_BLANK_TEMPLATE,
					description: __("{0} rows in this table", [
						(this.grid.frm.doc[this.grid.df.fieldname] || []).length,
					]),
				},
				{ fieldtype: "Section Break", label: __("Fields"), collapsible: 1 },
				{
					fieldtype: "MultiCheck",
					fieldname: "fields",
					columns: 2,
					select_all: true,
					select_mandatory: true,
					sort_options: false,
					options: this.get_field_options(),
					on_change: () => this.set_footer(),
				},
			],
		});
		this.setup_form.make();
	}

	get_field_options(selected = []) {
		const matches_on_id = this.state.import_type !== BULK_EDIT_INSERT;
		return this.get_docfields().map((df) => {
			const is_id = df.fieldname === BULK_EDIT_ID_FIELDNAME;
			const mandatory = is_id ? matches_on_id : !!df.reqd;
			return {
				label: __(df.label || df.fieldname, null, df.parent),
				value: df.fieldname,
				checked: mandatory || (!is_id && selected.includes(df.fieldname)) ? 1 : 0,
				danger: mandatory,
			};
		});
	}

	refresh_field_options() {
		const control = this.setup_form.fields_dict.fields;
		control.df.options = this.get_field_options(control.get_value() || []);
		control.set_options();
		this.set_footer();
	}

	watch_cell_pickers() {
		this.on_document_mousedown = (event) => this.handle_document_mousedown(event);
		document.addEventListener("mousedown", this.on_document_mousedown, true);
		this.dialog.$wrapper.on("hidden.bs.modal", () => {
			this.discard_cell_controls();
			document.removeEventListener("mousedown", this.on_document_mousedown, true);
		});
	}

	uploaded_file_count() {
		return this.file_uploader?.uploader?.files?.length || 0;
	}

	has_library_selection() {
		return Boolean(this.panels.upload.find(".tree-link.active .file-doc-link").length);
	}

	has_file_selection() {
		return Boolean(this.uploaded_file_count() || this.has_library_selection());
	}

	make_upload_panel() {
		this.panels.upload.css({ height: "100%", display: "flex", "flex-direction": "column" });

		const $file_pane = $('<div class="bulk-edit-upload-pane bulk-edit-file-pane"></div>');
		const $sheet_pane = $('<div class="bulk-edit-upload-pane"></div>');

		const upload_tabs = new frappe.ui.Tabs({
			css_class: "bulk-edit-upload-tabs",
			tabs: [
				{ label: __("File upload"), icon: "upload", content: $file_pane[0] },
				{ label: __("Google Sheet"), icon: "link", content: $sheet_pane[0] },
			],
		});
		this.panels.upload.append(upload_tabs.$el);
		upload_tabs.$el.css({
			flex: "1 1 auto",
			"min-height": 0,
			display: "flex",
			"flex-direction": "column",
		});
		upload_tabs.$el.find(".es-tabs__list").css({ flex: "0 0 auto" });
		upload_tabs.$el.find(".es-tabs__panel").css({
			flex: "1 1 auto",
			"min-height": 0,
			"overflow-y": "auto",
		});
		$file_pane.css({ height: "100%" });
		$sheet_pane.css({ height: "100%" });

		this.file_uploader = new frappe.ui.FileUploader({
			wrapper: $file_pane,
			as_dataurl: true,
			allow_multiple: false,
			allow_web_link: false,
			allow_take_photo: false,
			allow_google_drive: false,
			restrictions: { allowed_file_types: BULK_EDIT_FILE_TYPES },
			on_success: (file) => this.read_file(file, (rows) => this.on_file(rows)),
		});
		$file_pane.children(".file-uploader").css({ flex: "0 0 auto" });
		$file_pane.on("click change drop", () =>
			setTimeout(() => {
				$file_pane.toggleClass("has-file", Boolean(this.uploaded_file_count()));
				this.sync_uploaded_file();
				this.set_footer();
			}, 0)
		);

		const sheet_form = new frappe.ui.FieldGroup({
			body: $sheet_pane[0],
			no_submit_on_enter: true,
			fields: [
				{
					fieldtype: "Data",
					fieldname: "google_sheets_url",
					label: __("Import from Google Sheets"),
					description: __("Must be a publicly accessible Google Sheets URL"),
					change: () => {
						const url = sheet_form.get_value("google_sheets_url");
						if (url) this.read_google_sheet(url);
					},
				},
			],
		});
		sheet_form.make();

		return this.panels.upload[0];
	}

	sync_uploaded_file() {
		if (this.state.google_sheets_url || this.state.library_file_url) return;
		if (!this.file_uploader || this.uploaded_file_count() || !this.state.rows.length) return;
		this.state.headers = [];
		this.state.rows = [];
		this.state.row_numbers = [];
		this.state.column_map = {};
		this.tabs.set_disabled(TAB_PREVIEW, true);
	}

	handle_document_mousedown(event) {
		Object.values(this.cell_controls).forEach((control) => {
			const picker = picker_of(control);
			if (!picker) return;

			if (control.$wrapper.closest("td").get(0)?.contains(event.target)) {
				if (!picker_is_open(control)) {
					open_picker(control);
					return;
				}
				close_picker(control);
				control._closed_by_cell = true;
				event.preventDefault();
				return;
			}
			if (picker.contains(event.target)) return;
			if (picker_is_open(control)) close_picker(control);
		});
	}

	discard_cell_controls() {
		return Object.values(this.cell_controls).forEach(discard_cell_control);
	}

	mapping_options() {
		return [
			{ label: __("Don't Import"), value: BULK_EDIT_DONT_IMPORT },
			...this.get_docfields().map((df) => ({
				label: __(df.label || df.fieldname, null, df.parent),
				value: df.fieldname,
				description: df.fieldname,
			})),
		];
	}

	step_panel() {
		return this.tabs.get_active() === TAB_FIX ? this.panels.fix : this.panels.preview;
	}

	step_view() {
		const fixing = this.tabs.get_active() === TAB_FIX;
		const issues = this.get_issue_rows();
		const columns = this.state.headers
			.map((header, index) => index)
			.filter((index) => fixing || this.state.column_map[index]);
		const picked = this.state.row_numbers
			.map((number, index) => index)
			.filter((index) => {
				const row = this.state.row_numbers[index];
				const skipped = this.state.skipped_rows.has(row);
				return fixing ? issues.has(row) || skipped : !issues.has(row) && !skipped;
			});
		const page = fixing ? this.paged(picked) : picked;
		return {
			headers: this.state.headers,
			columns,
			rows: page.map((index) => this.state.rows[index]),
			row_numbers: page.map((index) => this.state.row_numbers[index]),
			total_rows: picked.length,
			limit: fixing ? Infinity : BULK_EDIT_PREVIEW_ROWS,
			mapping: fixing,
		};
	}

	make_pagination($table, view) {
		if (!view.mapping || view.total_rows <= BULK_EDIT_FIX_PAGE_LENGTH) return;
		this.pagination = new GridPagination({
			wrapper: $table,
			grid: {
				data: new Array(view.total_rows),
				meta: { grid_page_length: BULK_EDIT_FIX_PAGE_LENGTH },
				render_result_rows: () => {
					this.state.fix_page = this.pagination.page_index;
					this.build_preview(true);
				},
				scroll_to_top: () => $table.find(".bulk-edit-preview-table").scrollTop(0),
			},
		});
		this.pagination.page_index = this.state.fix_page;
		this.pagination.render_pagination();
	}

	paged(rows) {
		const pages = Math.ceil(rows.length / BULK_EDIT_FIX_PAGE_LENGTH) || 1;
		this.state.fix_page = Math.min(this.state.fix_page, pages);
		const start = (this.state.fix_page - 1) * BULK_EDIT_FIX_PAGE_LENGTH;
		return rows.slice(start, start + BULK_EDIT_FIX_PAGE_LENGTH);
	}

	build_preview(keep_skipped_rows = false) {
		this.discard_cell_controls();
		this.panels.fix.empty();
		this.panels.preview.empty();
		this.cell_controls = {};
		if (!keep_skipped_rows) this.state.skipped_rows = new Set();
		const $panel = this.step_panel();
		this.preview_form = new frappe.ui.FieldGroup({
			body: $panel[0],
			no_submit_on_enter: true,
			fields: [{ fieldtype: "HTML", fieldname: "table" }],
		});
		this.preview_form.make();

		const $table = this.preview_form.get_field("table").$wrapper;
		const view = this.step_view();
		$table.html(this.get_preview_html(view));
		$table.find(".bulk-edit-refresh-sheet").on("click", () => this.refresh_google_sheet());
		$table.find(".bulk-edit-skip-all").on("click", () => this.skip_issue_rows());
		this.make_pagination($table, view);
		$panel.css({ height: "100%", display: "flex", "flex-direction": "column" });
		$table.parentsUntil($panel).addBack().css({
			display: "flex",
			"flex-direction": "column",
			flex: "1 1 auto",
			"min-height": 0,
		});
		const options = this.mapping_options();
		this.building_preview = true;
		const seeded = [];
		this.mapping_controls = [];
		view.mapping &&
			view.columns.forEach((i) => {
				const header = this.state.headers[i];
				const control = frappe.ui.form.make_control({
					df: {
						fieldtype: "Autocomplete",
						fieldname: `map_${i}`,
						placeholder: header || __("Column {0}", [i + 1]),
						max_items: Infinity,
						options,
						change: () => {
							if (!this.building_preview) {
								this.state.column_overrides[i] = control.get_value();
							}
							this.refresh_preview();
						},
					},
					parent: $table.find(`.bulk-edit-mapping-row td[data-col="${i}"]`).get(0),
					render_input: true,
					only_input: true,
				});
				this.pin_dropdown(control);
				control.$input?.on("focus click", () => this.show_cell_message(control));
				seeded.push(control.set_value(this.state.column_map[i] || BULK_EDIT_DONT_IMPORT));
				this.mapping_controls[i] = control;
			});

		this._built_step = this.tabs.get_active() === TAB_FIX ? TAB_FIX : TAB_PREVIEW;
		return Promise.all(seeded).then(() => {
			this.building_preview = false;
			return this.refresh_preview();
		});
	}

	show_cell_message(control) {
		const message = control?._warning?.message || "";
		this.$message.toggleClass("hide", !message).attr("title", message);
		this.$message.children("span").text(message);
	}

	pin_datepicker(control) {
		const picker = control.datepicker;
		const panel = picker && $(picker.$datepicker).get(0);
		if (!panel) return;

		const reposition = () => {
			panel.style.position = "fixed";
			place(panel, control.$input[0].getBoundingClientRect(), "bottom", "start", 4);
		};

		const call = (hook, args) => typeof hook === "function" && hook.apply(picker, args);
		const original_show = picker.opts.onShow;
		const original_hide = picker.opts.onHide;
		picker.opts.onShow = (...args) => {
			call(original_show, args);
			reposition();
			window.addEventListener("resize", reposition);
			document.addEventListener("scroll", reposition, { capture: true, passive: true });
		};
		picker.opts.onHide = (...args) => {
			window.removeEventListener("resize", reposition);
			document.removeEventListener("scroll", reposition, { capture: true });
			call(original_hide, args);
		};
	}

	pin_dropdown(control) {
		const home = control.$input.closest(".awesomplete").get(0);
		const list = home?.querySelector(":scope > ul");
		if (!list) return;

		const host = document.createElement("div");
		host.className = "awesomplete bulk-edit-dropdown-host";

		const reposition = () =>
			place(list, control.$input[0].getBoundingClientRect(), "bottom", "start", 2);

		control.$input.on("awesomplete-open", () => {
			host.appendChild(list);
			document.body.appendChild(host);
			list.style.width = `${control.$input[0].offsetWidth}px`;
			reposition();
			window.addEventListener("resize", reposition);
			document.addEventListener("scroll", reposition, { capture: true, passive: true });
		});

		control.$input.on("awesomplete-close", () => {
			window.removeEventListener("resize", reposition);
			document.removeEventListener("scroll", reposition, { capture: true });
			home.appendChild(list);
			host.remove();
			list.style.width = "";
		});
	}

	make_cell_control(cell, r, col, warning, fieldname) {
		const original = this.state.rows[r][col];
		const df = { ...warning.field };

		df.hidden = 0;
		df.hidden_due_to_dependency = 0;

		if (df.fieldtype === "Select") {
			const options = (df.options || "").split("\n").map((o) => o.trim());
			if (original && !options.includes(cstr(original).trim())) {
				df.options = [original, ...options].join("\n");
			}
		} else if (df.fieldtype === "Link") {
			df.ignore_link_validation = true;
		}

		$(cell).addClass("bulk-edit-editable-cell");
		const control = frappe.ui.form.make_control({
			df: {
				...df,
				change: () => {
					if (control._seeding) return;
					this.state.rows[r][col] = control.get_value();
					this.refresh_preview();
				},
			},
			parent: $(cell).empty().get(0),
			render_input: true,
			only_input: true,
		});
		control._fieldname = fieldname;
		control._warning = warning;
		control.$wrapper.css("position", "relative");
		this.pin_datepicker(control);

		if (df.fieldtype === "Link") {
			control.set_link_title = async (value) =>
				control.translate_and_set_input_value(value, value);
			$(`<div class="select-icon">${frappe.utils.icon("chevrons-up-down", "sm")}</div>`)
				.css({
					position: "absolute",
					top: "3px",
					right: "12px",
					"pointer-events": "none",
				})
				.appendTo(control.$wrapper);
			this.pin_dropdown(control);
		}

		if (BULK_EDIT_NUMERIC_FIELDTYPES.includes(df.fieldtype)) {
			control.parse = (value) => value;
			control.format_for_input = (value) => cstr(value);
			control.validate = (value) => value;
		}

		control._seeding = true;
		Promise.resolve(control.set_value(bulk_edit_seed_value(df.fieldtype, original))).then(
			() => {
				control._seeding = false;
			}
		);

		control.$input?.on("focus click", () => {
			this.show_cell_message(control);
			if (df.fieldtype !== "Link") return;
			if (control._closed_by_cell) {
				control._closed_by_cell = false;
				return;
			}
			control.on_input({ target: { value: "" } });
		});

		return control;
	}

	render_skip_buttons($table, warnings) {
		const rows_with_warnings = new Set(
			warnings.filter((w) => w.row !== undefined).map((w) => cint(w.row))
		);
		$table.find("tr[data-row]").each((_, tr) => {
			const row = cint(tr.dataset.row);
			const skipped = this.state.skipped_rows.has(row);
			const $cell = $(tr).find(".bulk-edit-skip-cell").empty();
			$(tr).toggleClass("bulk-edit-skipped-row", skipped);
			if (!skipped && !rows_with_warnings.has(row)) return;

			frappe.ui
				.button({
					label: skipped ? __("Restore") : __("Skip"),
					size: "sm",
					onclick: () => {
						this.state.skipped_rows[skipped ? "delete" : "add"](row);
						this.refresh_preview({ recheck_links: false });
					},
				})
				.appendTo($cell);
		});
	}

	sync_column_errors($table, warnings) {
		const by_column = {};
		warnings.forEach((w) => {
			if (w.row === undefined && w.col !== undefined) by_column[w.col] = w;
		});

		this.mapping_controls.forEach((control, i) => {
			const warning = by_column[i];
			control._warning = warning;
			$table
				.find(`th[data-col="${i}"], .bulk-edit-mapping-row td[data-col="${i}"]`)
				.toggleClass("has-error", Boolean(warning));
		});
	}

	sync_preview_errors(warnings) {
		const by_cell = {};
		warnings.forEach((w) => {
			if (w.row !== undefined && w.col !== undefined) by_cell[`${w.row}:${w.col}`] = w;
		});

		const $table = this.preview_form.get_field("table").$wrapper;
		this.render_skip_buttons($table, warnings);
		this.sync_column_errors($table, warnings);

		$table.find("tr[data-row] td[data-col]").each((_, cell) => {
			const row = cint(cell.closest("tr").dataset.row);
			const col = cint(cell.dataset.col);
			const key = `${row}:${col}`;
			const warning = by_cell[key];
			const fieldname = this.state.column_map[col];
			const existing = this.cell_controls[key];

			$(cell).toggleClass("has-error", Boolean(warning));

			if (existing) {
				if (existing._fieldname === fieldname) {
					existing._warning = warning;
					return;
				}
				discard_cell_control(existing);
				delete this.cell_controls[key];
				$(cell)
					.removeClass("bulk-edit-editable-cell")
					.empty()
					.text(this.state.rows[this.state.row_numbers.indexOf(row)][col]);
			}

			const r = this.state.row_numbers.indexOf(row);
			const mapped_df =
				fieldname && frappe.meta.get_docfield(this.grid.df.options, fieldname);
			const fieldtype = mapped_df?.fieldtype;
			$(cell).removeClass("bulk-edit-pending-cell").off("click.bulk-edit-reveal");

			if (warning?.field && BULK_EDIT_DEFERRED_FIELDTYPES.includes(fieldtype)) {
				$(cell)
					.addClass("bulk-edit-pending-cell")
					.one("click.bulk-edit-reveal", () => {
						const control = this.make_cell_control(cell, r, col, warning, fieldname);
						this.cell_controls[key] = control;
						control.$input?.trigger("focus");
					});
				return;
			}

			if (!warning?.field && fieldtype !== "Check") return;

			this.cell_controls[key] = this.make_cell_control(
				cell,
				r,
				col,
				warning || { field: mapped_df },
				fieldname
			);
		});

		this.show_cell_message(
			[...Object.values(this.cell_controls), ...this.mapping_controls].find((c) =>
				c?.$input?.is(":focus")
			)
		);
	}

	async refresh_preview({ recheck_links = true } = {}) {
		if (this.building_preview) return;
		const request_id = ++this.preview_request_id;

		if (this.mapping_controls.length) {
			const picked = {};
			this.mapping_controls.forEach((control, i) => {
				const value = control.get_value();
				if (value && value !== BULK_EDIT_DONT_IMPORT) picked[i] = value;
			});
			this.state.column_map = picked;
		}
		const map = this.state.column_map;

		this.preview_form
			.get_field("table")
			.$wrapper.find("[data-col]")
			.each((_, cell) => {
				$(cell).attr("data-mapped", map[cint(cell.dataset.col)] ? 1 : 0);
			});

		const warnings = this.get_warnings(
			this.state.headers,
			this.state.rows,
			this.state.row_numbers,
			this.state.import_type,
			map
		);
		const link_warnings = recheck_links
			? await this.get_link_warnings(this.state.rows, this.state.row_numbers, map)
			: this.link_warnings;
		if (request_id !== this.preview_request_id) return;
		this.link_warnings = link_warnings;
		warnings.push(...link_warnings);
		this.state.warnings = warnings;
		this.sync_preview_errors(warnings);
		this.settle_fix_step();

		this.set_footer();
	}

	has_issues() {
		return this.state.warnings.some(
			(w) => w.blocking && !this.state.skipped_rows.has(cint(w.row))
		);
	}

	has_mapping_issues() {
		return this.state.warnings.some((w) => w.blocking && w.row === undefined);
	}

	skip_issue_rows() {
		this.get_issue_rows().forEach((row) => this.state.skipped_rows.add(row));
		this.refresh_preview({ recheck_links: false });
	}

	get_issue_rows() {
		return new Set(
			this.state.warnings
				.filter(
					(w) =>
						w.blocking &&
						w.row !== undefined &&
						!this.state.skipped_rows.has(cint(w.row))
				)
				.map((w) => cint(w.row))
		);
	}

	settle_fix_step() {
		if (this.tab_defs.length <= TAB_PREVIEW) return;
		if (this.tabs.get_active() !== TAB_FIX) {
			this.tabs.set_disabled(TAB_FIX, !this.has_issues());
		}
		const $table = this.preview_form?.get_field("table").$wrapper;
		$table?.find(".bulk-edit-preview-hint").text(this.preview_hint());
		$table
			?.find(".bulk-edit-skip-all")
			.prop("disabled", this.has_mapping_issues() || !this.get_issue_rows().size);
	}

	preview_hint() {
		if (this.has_mapping_issues()) {
			return __("Two columns map to the same field. Fix the mapping to continue.");
		}
		const total = this.state.rows.length;
		const skipped = this.state.skipped_rows.size;

		if (this.tabs.get_active() !== TAB_FIX) {
			return __("{0} of {1} rows ready to import.", [total - skipped, total]);
		}

		const pending = this.get_issue_rows().size;
		if (pending) {
			return pending === 1
				? __("{0} rows found, 1 needs fixing. Fix it, or skip it to move on.", [total])
				: __("{0} rows found, {1} need fixing. Fix them, or skip them to move on.", [
						total,
						pending,
				  ]);
		}
		return skipped
			? __("{0} rows found, {1} skipped. Nothing left to fix.", [total, skipped])
			: __("{0} rows found. Nothing to fix.", [total]);
	}

	async on_file(data, google_sheets_url = "", is_refresh = false) {
		if (cint(data.length) - BULK_EDIT_CSV_HEADER_ROWS > BULK_EDIT_MAX_ROWS) {
			frappe.throw(__("Cannot import table with more than {0} rows.", [BULK_EDIT_MAX_ROWS]));
		}

		this.state.google_sheets_url = google_sheets_url;
		if (google_sheets_url) this.state.library_file_url = "";
		this.state.headers = data[0] || [];
		this.state.rows = [];
		this.state.row_numbers = [];
		data.slice(BULK_EDIT_CSV_HEADER_ROWS).forEach((row, i) => {
			if (!row.some((v) => v)) return;
			this.state.rows.push(row);
			this.state.row_numbers.push(BULK_EDIT_CSV_HEADER_ROWS + i + 1);
		});

		if (!this.state.rows.length) {
			frappe.msgprint({
				message: __("There are no rows to import in this file."),
				title: __("Nothing to Import"),
				indicator: "orange",
			});
			return;
		}

		if (!is_refresh) this.state.column_overrides = {};
		this.state.column_map = this.apply_column_overrides(
			await this.get_column_map(this.state.headers)
		);
		await this.build_preview();
		this.tabs.set_disabled(TAB_PREVIEW, false);
		this.tabs.set_active(this.has_issues() ? TAB_FIX : TAB_PREVIEW);
	}

	download() {
		const values = this.setup_form.get_values();
		if (!values) return;
		this.download_template(values.file_type, values.fields, values.export_records);
	}

	set_action(label, handler, { solid = false } = {}) {
		this.dialog.set_primary_action(label, handler);
		if (!solid) {
			frappe.ui.button.dress(this.dialog.get_primary_btn(), { label, variant: "subtle" });
		}
	}

	previous_step() {
		for (let index = this.tabs.get_active() - 1; index >= 0; index--) {
			if (!this.tab_defs[index].disabled) return index;
		}
		return null;
	}

	set_footer() {
		const active = this.tabs.get_active();
		this.dialog.get_primary_btn().addClass("hide").prop("disabled", false);
		const $secondary = this.dialog.get_secondary_btn().addClass("hide");
		this.$back.toggleClass("hide", this.previous_step() === null);

		if (active === TAB_SETUP) {
			this.dialog.set_secondary_action_label(__("Download Template"));
			this.dialog.set_secondary_action(() => this.download());
			$secondary.prop("disabled", !this.setup_form.get_value("fields")?.length);
			if (this.can_import) {
				this.set_action(
					__("Next"),
					() => {
						this.tabs.set_disabled(TAB_UPLOAD, false);
						this.tabs.set_active(TAB_UPLOAD);
					},
					{ solid: true }
				);
				this.dialog.get_primary_btn().prop("disabled", false);
			}
			return;
		}

		if (active === TAB_FIX) {
			this.set_action(__("Next"), () => this.tabs.set_active(TAB_PREVIEW));
			this.dialog.get_primary_btn().prop("disabled", this.has_issues());
			return;
		}

		if (active === TAB_PREVIEW) {
			this.set_action(
				__("Apply"),
				() => {
					this.dialog.hide();
					const rows = this.state.rows.filter(
						(_, r) => !this.state.skipped_rows.has(this.state.row_numbers[r])
					);
					this.apply_rows(rows, this.state.import_type, this.state.column_map);
				},
				{ solid: true }
			);
			this.dialog.get_primary_btn().prop("disabled", this.has_issues());
			return;
		}

		this.set_action(__("Next"), () => {
			if (this.has_file_selection()) {
				this.file_uploader.upload_files();
				return;
			}
			this.tabs.set_active(TAB_PREVIEW);
		});
		this.dialog
			.get_primary_btn()
			.prop("disabled", !this.has_file_selection() && this.tab_defs[TAB_PREVIEW].disabled);
	}

	download_template(file_type, fieldnames, export_records) {
		const title = this.get_title();
		const data = this.get_template_rows(fieldnames, export_records);

		if (file_type === "CSV") {
			frappe.tools.downloadify(data, null, title);
			return;
		}

		open_url_post("/api/method/frappe.desk.form.bulk_edit.download_bulk_edit_template", {
			doctype: this.grid.frm.doctype,
			title: title,
			file_type: file_type,
			data: JSON.stringify(data),
		});
	}

	get_template_rows(fieldnames, export_records) {
		let docfields = this.get_docfields();
		if (fieldnames && fieldnames.length) {
			docfields = docfields.filter((df) => fieldnames.includes(df.fieldname));
		}

		const header = docfields.map((df) =>
			df.fieldname === BULK_EDIT_ID_FIELDNAME
				? __("ID")
				: `${__(df.label || df.fieldname)} (${df.fieldname})`
		);
		const data = [header];

		let grid_rows = this.grid.frm.doc[this.grid.df.fieldname] || [];
		if (export_records === BULK_EDIT_BLANK_TEMPLATE) grid_rows = [];
		else if (export_records === BULK_EDIT_5_RECORDS) grid_rows = grid_rows.slice(0, 5);

		grid_rows.forEach((d) => {
			data.push(
				docfields.map((df) => {
					const value = d[df.fieldname];
					if (!value) return "";
					return df.fieldtype === "Date" ? frappe.datetime.str_to_user(value) : value;
				})
			);
		});

		return data;
	}

	read_file(file, on_parsed) {
		const filename = file?.file_url ? file.file_name : file?.name;
		if (!file || (!file.dataurl && !file.file_url)) return;
		this.state.library_file_url = file.file_url || "";

		frappe.call({
			method: "frappe.desk.form.bulk_edit.parse_bulk_edit_file",
			args: {
				doctype: this.grid.frm.doctype,
				filename,
				dataurl: file.dataurl,
				file_url: file.file_url,
			},
			freeze: true,
			freeze_message: __("Reading {0}", [filename]),
			callback: (r) => {
				if (r.message) on_parsed(r.message);
			},
		});
	}

	refresh_google_sheet() {
		if (!this.state.google_sheets_url) return;
		this.read_google_sheet(this.state.google_sheets_url, true);
	}

	read_google_sheet(url, is_refresh = false) {
		frappe.call({
			method: "frappe.desk.form.bulk_edit.parse_bulk_edit_google_sheet",
			args: { doctype: this.grid.frm.doctype, url },
			freeze: true,
			freeze_message: __("Reading Google Sheet"),
			callback: (r) => {
				if (r.message) this.on_file(r.message, url, is_refresh);
			},
		});
	}

	get_preview_html({ headers, rows, row_numbers, columns, limit, mapping, total_rows }) {
		const escape = frappe.utils.escape_html;
		const shown = rows.slice(0, limit);

		const head = columns.map(
			(i) => `<th data-col="${i}" data-mapped="0">${escape(cstr(headers[i]))}</th>`
		);
		const mapping_row = mapping
			? `
			<tr class="bulk-edit-mapping-row">
				<td class="bulk-edit-preview-row"></td>
				${columns.map((i) => `<td data-col="${i}"></td>`).join("")}
				<td class="bulk-edit-skip-cell"></td>
			</tr>
		`
			: "";
		const body = shown.map(
			(row, r) => `
				<tr data-row="${cint(row_numbers[r])}">
					<td class="bulk-edit-preview-row">${cint(row_numbers[r])}</td>
					${columns.map((i) => `<td data-col="${i}" data-mapped="0">${escape(cstr(row[i]))}</td>`).join("")}
					<td class="bulk-edit-skip-cell"></td>
				</tr>
			`
		);

		return `
			<div class="bulk-edit-preview-head">
				<span class="text-muted small">${
					mapping
						? __(
								"Map each column of the file to a field. Anything left unmapped is ignored."
						  )
						: __("These rows will be added to the table when you apply.")
				}</span>
				<div class="bulk-edit-preview-head-actions">
					${
						this.state.google_sheets_url
							? frappe.ui.button.html({
									label: __("Refresh"),
									icon: "refresh-cw",
									css_class: "bulk-edit-refresh-sheet",
							  })
							: ""
					}
					${
						mapping
							? frappe.ui.button.html({
									label: __("Skip All"),
									disabled: true,
									css_class: "bulk-edit-skip-all",
							  })
							: ""
					}
				</div>
			</div>
			<div class="bulk-edit-preview-hint text-muted small">${__(
				"Fix the highlighted cells. Click one to see and resolve its error."
			)}</div>
			<div class="bulk-edit-preview-table">
				<table class="table table-bordered">
					<thead>
						<tr>
							<th class="bulk-edit-preview-row">${__("Row")}</th>
							${head.join("")}
							<th class="bulk-edit-skip-cell"></th>
						</tr>
					</thead>
					<tbody>${mapping_row}${body.join("")}</tbody>
				</table>
			</div>
			${
				mapping && total_rows > BULK_EDIT_FIX_PAGE_LENGTH
					? '<div class="bulk-edit-preview-foot"><div class="grid-pagination"></div></div>'
					: ""
			}
		`;
	}

	get_warnings(headers, rows, row_numbers, import_type, column_map) {
		const columns = Object.keys(column_map).map(cint);
		const id_index = columns.find((i) => column_map[i] === BULK_EDIT_ID_FIELDNAME);

		const warnings = this.get_header_warnings(headers, column_map);
		warnings.push(...this.get_id_warnings(rows, row_numbers, import_type, id_index));
		rows.forEach((row, r) => {
			warnings.push(
				...this.get_row_warnings(row, row_numbers[r], headers, columns, column_map, {
					import_type,
					id_index,
				})
			);
		});
		return warnings;
	}

	get_header_warnings(headers, column_map) {
		const warnings = [];
		headers.forEach((header, i) => {
			if (header && column_map[i] === undefined) {
				warnings.push({
					col: i,
					message: __('"{0}" does not match a field and will be ignored.', [header]),
				});
			}
		});
		warnings.push(...this.get_duplicate_mapping_warnings(column_map));
		return warnings;
	}

	get_duplicate_mapping_warnings(column_map) {
		const columns_by_field = {};
		Object.entries(column_map).forEach(([index, fieldname]) => {
			(columns_by_field[fieldname] ??= []).push(cint(index));
		});
		const duplicated = Object.entries(columns_by_field).filter(
			([, columns]) => columns.length > 1
		);
		if (!duplicated.length) return [];

		const label_of = Object.fromEntries(
			this.get_docfields().map((df) => [
				df.fieldname,
				__(df.label || df.fieldname, null, df.parent),
			])
		);

		const warnings = [];
		duplicated.forEach(([fieldname, columns]) => {
			const message = __("Columns {0} map to {1}. Only one column can fill a field.", [
				columns.map((i) => i + 1).join(", "),
				label_of[fieldname] || fieldname,
			]);
			columns.forEach((i) => warnings.push({ blocking: true, col: i, message }));
		});
		return warnings;
	}

	get_id_warnings(rows, row_numbers, import_type, id_index) {
		const warnings = [];

		if (id_index === undefined) {
			if (import_type !== BULK_EDIT_INSERT) {
				warnings.push({
					blocking: true,
					message: __(
						"No ID column is mapped, so no row can be matched. Every row will be skipped."
					),
				});
			}
			return warnings;
		}

		const rows_by_id = {};
		rows.forEach((row, r) => {
			const id = cstr(row[id_index]).trim();
			if (id) (rows_by_id[id] ??= []).push(row_numbers[r]);
		});
		Object.entries(rows_by_id).forEach(([id, id_rows]) => {
			if (id_rows.length > 1) {
				warnings.push({
					message: __("ID {0} appears in rows {1} — only the last one will apply.", [
						id,
						id_rows.join(", "),
					]),
				});
			}
		});
		return warnings;
	}

	get_row_warnings(row, row_number, headers, columns, column_map, { import_type, id_index }) {
		const warnings = [];

		if (row.length !== headers.length) {
			warnings.push({
				row: row_number,
				message:
					row.length < headers.length
						? __("This row has fewer cells than the header.")
						: __("This row has more cells than the header."),
			});
		}

		const id = id_index === undefined ? null : cstr(row[id_index]).trim();
		const existing = id ? this.get_row_by_id(id) : null;
		const is_new =
			import_type === BULK_EDIT_INSERT || (!existing && import_type === BULK_EDIT_UPSERT);

		if (import_type === BULK_EDIT_UPDATE && id && !existing) {
			warnings.push({
				row: row_number,
				message: __('No row in this table has the ID "{0}".', [id]),
			});
		}

		columns.forEach((i) => {
			const fieldname = column_map[i];
			if (fieldname === BULK_EDIT_ID_FIELDNAME) return;

			const df = frappe.meta.get_docfield(this.grid.df.options, fieldname);
			if (!df) return;

			const message = this.get_value_error(df, cstr(row[i]).trim(), is_new);
			if (message) {
				warnings.push({ blocking: true, row: row_number, col: i, field: df, message });
			}
		});

		return warnings;
	}

	get_value_error(df, value, is_new) {
		if (!value) return df.reqd && is_new ? __("This field is mandatory and is blank.") : "";

		if (df.fieldtype === "Select") {
			const options = (df.options || "").split("\n").map((o) => o.trim());
			if (!options.includes(value)) {
				return __('"{0}" is not a valid option. Allowed: {1}', [
					value,
					options.filter(Boolean).join(", "),
				]);
			}
		}

		if (df.fieldtype === "Date" || df.fieldtype === "Datetime") {
			const date_fmt = frappe.datetime.get_user_date_fmt().toUpperCase();
			const time_fmt = frappe.datetime.get_user_time_fmt();
			const is_date = df.fieldtype === "Date";
			const formats = is_date
				? [date_fmt, frappe.defaultDateFormat]
				: [`${date_fmt} ${time_fmt}`, frappe.defaultDatetimeFormat];
			if (!moment(value, formats, true).isValid()) {
				return is_date
					? __('"{0}" is not a valid date. Use {1}', [value, date_fmt])
					: __('"{0}" is not a valid datetime. Use {1}', [
							value,
							`${date_fmt} ${time_fmt}`,
					  ]);
			}
		}

		if (df.fieldtype === "Time" && !moment(value, BULK_EDIT_TIME_FORMATS(), true).isValid()) {
			return __('"{0}" is not a valid time. Use {1}', [
				value,
				frappe.datetime.get_user_time_fmt(),
			]);
		}

		if (
			df.fieldtype === "Duration" &&
			!BULK_EDIT_DURATION_PATTERN.test(value) &&
			!BULK_EDIT_SECONDS_PATTERN.test(value)
		) {
			return __('"{0}" is not valid. Use duration format: d h m s', [value]);
		}

		if (BULK_EDIT_NUMERIC_FIELDTYPES.includes(df.fieldtype) && !bulk_edit_is_number(value)) {
			return __('"{0}" is not a valid number.', [value]);
		}

		if (df.fieldtype === "Check" && !BULK_EDIT_CHECK_VALUES.includes(value.toLowerCase())) {
			return __('"{0}" is not valid. Use {1}', [value, "0, 1, Yes, No"]);
		}

		if (df.fieldtype === "Rating" && !bulk_edit_is_rating(value)) {
			return __('"{0}" is not a valid rating. Use a number between 0 and 1.', [value]);
		}

		const format = bulk_edit_format_of(df);
		if (format && !bulk_edit_matches_format(value, format)) {
			return __('"{0}" is not a valid {1}.', [value, __(df.options || df.fieldtype)]);
		}

		return "";
	}

	async get_link_warnings(rows, row_numbers, column_map) {
		const link_columns = Object.keys(column_map)
			.map(cint)
			.map((i) => ({ i, df: frappe.meta.get_docfield(this.grid.df.options, column_map[i]) }))
			.filter(({ df }) => df?.fieldtype === "Link");

		if (!link_columns.length) return [];

		const values_by_doctype = {};
		link_columns.forEach(({ i, df }) => {
			const values = (values_by_doctype[df.options] ??= new Set());
			rows.forEach((row) => {
				const value = cstr(row[i]).trim();
				if (value) values.add(value);
			});
		});

		const invalid = await frappe.xcall("frappe.desk.form.bulk_edit.get_invalid_link_values", {
			doctype: this.grid.frm.doctype,
			values_by_doctype: JSON.stringify(
				Object.fromEntries(
					Object.entries(values_by_doctype).map(([doctype, values]) => [
						doctype,
						[...values],
					])
				)
			),
		});

		const warnings = [];
		link_columns.forEach(({ i, df }) => {
			const invalid_values = new Set(invalid[df.options] || []);
			if (!invalid_values.size) return;
			rows.forEach((row, r) => {
				const value = cstr(row[i]).trim();
				if (value && invalid_values.has(value)) {
					warnings.push({
						blocking: true,
						row: row_numbers[r],
						col: i,
						field: df,
						message: __('"{0}" is not a valid {1}', [value, df.label]),
					});
				}
			});
		});
		return warnings;
	}

	get_column_map(headers) {
		return frappe.xcall("frappe.desk.form.bulk_edit.get_bulk_edit_column_map", {
			doctype: this.grid.frm.doctype,
			fieldname: this.grid.df.fieldname,
			headers: JSON.stringify(headers),
		});
	}

	apply_column_overrides(auto_mapped) {
		const map = { ...auto_mapped };
		Object.entries(this.state.column_overrides).forEach(([index, fieldname]) => {
			if (fieldname === BULK_EDIT_DONT_IMPORT) delete map[index];
			else map[index] = fieldname;
		});
		return map;
	}

	get_row_by_id(id) {
		return (this.grid.frm.doc[this.grid.df.fieldname] || []).find((d) => d.name === id);
	}

	apply_rows(rows, import_type, column_map) {
		const columns = Object.keys(column_map).map(cint);
		const id_index = columns.find((i) => column_map[i] === BULK_EDIT_ID_FIELDNAME);
		const counts = { insert: 0, update: 0, skip: 0 };

		rows.forEach((row) => {
			const id = id_index === undefined ? null : cstr(row[id_index]).trim();
			const existing = id && this.get_row_by_id(id);
			let target;

			if (import_type === BULK_EDIT_INSERT) {
				target = this.grid.frm.add_child(this.grid.df.fieldname);
				counts.insert++;
			} else if (existing) {
				target = existing;
				counts.update++;
			} else if (import_type === BULK_EDIT_UPSERT) {
				target = this.grid.frm.add_child(this.grid.df.fieldname);
				counts.insert++;
			} else {
				counts.skip++;
				return;
			}

			columns.forEach((i) => {
				const fieldname = column_map[i];
				if (fieldname === BULK_EDIT_ID_FIELDNAME) return;

				const df = frappe.meta.get_docfield(this.grid.df.options, fieldname);
				if (!df) return;

				const format = BULK_EDIT_VALUE_FORMATTERS[df.fieldtype];
				target[fieldname] = format ? format(row[i]) : row[i];
			});
		});

		this.grid.frm.refresh_field(this.grid.df.fieldname);
		frappe.show_alert({
			message: __("{0} added, {1} updated, {2} skipped, save to apply", [
				counts.insert,
				counts.update,
				counts.skip,
			]),
			indicator: "green",
		});

		this.grid.frm.dirty();
	}
}

function bulk_edit_to_seconds(value) {
	const text = cstr(value).trim();
	if (!text) return 0;
	if (BULK_EDIT_SECONDS_PATTERN.test(text)) return cint(text);

	const part = (unit) => cint((text.match(new RegExp(`(\\d+)${unit}`)) || [])[1]);
	return frappe.utils.duration_to_seconds(part("d"), part("h"), part("m"), part("s"));
}

function bulk_edit_seed_value(fieldtype, value) {
	if (fieldtype === "Check") return BULK_EDIT_VALUE_FORMATTERS.Check(value);
	if (BULK_EDIT_DEFERRED_FIELDTYPES.includes(fieldtype)) return "";
	return value;
}

function bulk_edit_to_system_time(value) {
	if (!value) return value;
	const parsed = moment(value, BULK_EDIT_TIME_FORMATS(), true);
	return parsed.isValid() ? parsed.format(frappe.defaultTimeFormat) : value;
}

function bulk_edit_is_rating(value) {
	if (!bulk_edit_is_number(value)) return false;
	const rating = flt(value);
	return rating >= 0 && rating <= 1;
}

function bulk_edit_format_of(df) {
	if (df.fieldtype === "Phone") return "phone";
	return df.fieldtype === "Data" ? BULK_EDIT_DATA_FORMATS[df.options] : "";
}

function bulk_edit_matches_format(value, format) {
	const parts = format === "email" ? frappe.utils.split_emails(value) : [value];
	return (
		Boolean(parts?.length) && parts.every((part) => frappe.utils.validate_type(part, format))
	);
}

function bulk_edit_is_number(value) {
	let text = cstr(value).trim();
	if (!text) return false;

	if (text.includes(" ")) {
		const parts = text.split(" ");
		if (isNaN(parseFloat(parts[0]))) text = parts.slice(parts.length - 1).join(" ");
	}

	text = strip_number_groups(text);
	return text !== "" && !isNaN(Number(text));
}

const discard_cell_control = (control) => {
	control?.hide_picker?.();
	control?.datepicker?.destroy?.();
};

const picker_of = (control) =>
	control?.$picker?.get(0) ||
	control?.datepicker?.$datepicker?.get(0) ||
	control?.awesomplete?.ul ||
	null;

const picker_is_open = (control) => {
	if (control.$picker) return control.$picker.is(":visible");
	if (control.datepicker) return Boolean(control.datepicker.visible);
	return Boolean(control.awesomplete?.opened);
};

const open_picker = (control) => {
	if (control.$picker) return control.show_picker();
	if (control.datepicker) return control.datepicker.show();
	return control.on_input?.({ target: { value: "" } });
};

const close_picker = (control) => {
	if (control.$picker) return control.hide_picker();
	if (control.datepicker) return control.datepicker.hide();
	return control.awesomplete?.close();
};
