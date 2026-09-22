// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import { place } from "../ui/components/position.js";
import GridPagination from "./grid_pagination";

const MAX_ROWS = 5000;
const MAX_TEMPLATE_ROWS = 10000;
const FILE_TYPES = [".csv", ".xlsx", ".xls"];
const ID_FIELDNAME = "name";
const INSERT = "Insert New Records";
const UPDATE = "Update Existing Records";
const UPSERT = "Insert or Update Records";
const IMPORT_TYPES = [INSERT, UPDATE, UPSERT];
const DONT_IMPORT = "Don't Import";
const BLANK_TEMPLATE = "blank_template";
const ALL_RECORDS = "all";
const FIVE_RECORDS = "5_records";
const SECONDS_PATTERN = /^\d+$/;
const NUMERIC_FIELDTYPES = ["Int", "Float", "Currency", "Percent"];
const DATA_FORMATS = { Email: "email", Phone: "phone", Name: "name", URL: "url" };
const DEFERRED_FIELDTYPES = ["Date", "Datetime", "Time", "Duration", "Check"];
const DIALOG_SIZE = "extra-large";
const PREVIEW_ROWS = 10;
const FIX_PAGE_LENGTH = 50;

const TAB_SETUP = 0;
const TAB_UPLOAD = 1;
const TAB_FIX = 2;
const TAB_PREVIEW = 3;
const UPLOAD_TAB_SHEET = 1;
const SYSTEM_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}/;

const VALUE_FORMATTERS = {
	Date: (val) => {
		if (!val) return val;
		return SYSTEM_DATE_PATTERN.test(val) ? val.slice(0, 10) : frappe.datetime.user_to_str(val);
	},
	Datetime: (val) => {
		if (!val) return val;
		return moment(val, frappe.defaultDatetimeFormat, true).isValid()
			? val
			: frappe.datetime.user_to_str(val);
	},
	Time: (val) => to_system_time(val),
	Int: (val) => cint(val),
	Check: (val) => cint(frappe.utils.string_to_boolean(cstr(val))),
	Float: (val) => flt(val),
	Currency: (val) => flt(val),
	Percent: (val) => flt(val),
	Rating: (val) => flt(val),
	Duration: (val) => to_seconds(val),
};

const TIME_FORMATS = () => [frappe.datetime.get_user_time_fmt(), frappe.defaultTimeFormat];

export default class GridImport {
	constructor(grid) {
		this.grid = grid;
	}

	get_title() {
		return this.grid.df.label || frappe.model.unscrub(this.grid.df.fieldname);
	}

	get_docfields() {
		const can_write = (df) => this.grid.frm.get_perm(cint(df.permlevel), "write");
		return (this.docfields ??= [
			{ fieldname: ID_FIELDNAME, label: __("ID"), fieldtype: "Data" },
			...frappe
				.get_meta(this.grid.df.options)
				.fields.filter(
					(df) =>
						frappe.model.is_value_type(df.fieldtype) && !df.is_virtual && can_write(df)
				),
		]);
	}

	mappable_fieldnames() {
		return (this.mappable ??= new Set(this.get_docfields().map((df) => df.fieldname)));
	}

	get_id_index(column_map) {
		return Object.keys(column_map)
			.map(cint)
			.find((i) => column_map[i] === ID_FIELDNAME);
	}

	get_rows_by_id() {
		return new Map((this.grid.frm.doc[this.grid.df.fieldname] || []).map((d) => [d.name, d]));
	}

	get_field_label(fieldname) {
		if (fieldname === ID_FIELDNAME) return __("ID");
		const df = frappe.meta.get_docfield(this.grid.df.options, fieldname);
		return df ? __(df.label || df.fieldname, null, df.parent) : fieldname;
	}

	preview_description() {
		if (this.state.import_type === UPDATE) {
			return __("These rows will update the matching rows in the table when you apply.");
		}
		if (this.state.import_type === UPSERT) {
			return __(
				"Rows with a matching ID will be updated and the rest added to the table when you apply."
			);
		}
		return __("These rows will be added to the table when you apply.");
	}

	show() {
		this.can_import = this.grid.is_editable();
		this.state = {
			import_type: INSERT,
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
			setup: $('<div class="grid-import-panel"></div>'),
			upload: $('<div class="grid-import-panel grid-import-step-panel"></div>'),
			fix: $('<div class="grid-import-panel grid-import-step-panel"></div>'),
			preview: $('<div class="grid-import-panel grid-import-step-panel"></div>'),
		};
		this.mapping_controls = [];
		this.building_preview = false;
		this.preview_request_id = 0;
		this.server_warnings = [];
		this.stale_rows = new Set();
		this.cell_controls = {};

		this.make_dialog();
		this.make_setup_form();
		this.watch_cell_pickers();

		this.dialog.show();
		this.set_footer();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Upload {0}", [this.get_title()]),
			size: DIALOG_SIZE,
			centered: true,
		});
		$(this.dialog.wrapper).addClass("grid-import-dialog");
		this.dialog.$body.addClass("grid-import-body");

		this.tab_defs = this.can_import
			? [
					{ label: __("Setup"), content: () => this.panels.setup[0] },
					{ label: __("Upload"), content: () => this.make_upload_panel() },
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
				this.show_cell_message();
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
		this.tabs.$el.addClass("grid-import-tabs");

		this.stepper = new frappe.ui.Stepper({
			steps: this.tab_defs.map((tab) => ({ label: tab.label })),
			is_locked: (index) => this.tab_defs[index].disabled,
			on_step_click: (index) => this.tabs.set_active(index),
		});

		const $card = $('<div class="grid-import-card"></div>');
		this.dialog.$body.append(this.stepper.$el, $card);
		$card.append(this.tabs.$el, this.dialog.footer);

		this.$message = $(
			'<div class="grid-import-footer-message indicator red small hide"><span></span></div>'
		).appendTo(this.dialog.custom_actions);

		this.$back = frappe.ui
			.button({
				label: __("Back"),
				size: "sm",
				onclick: () => this.tabs.set_active(this.previous_step()),
			})
			.addClass("hide")
			.prependTo(this.dialog.standard_actions);
	}

	set_step_disabled(index, disabled) {
		this.tabs.set_disabled(index, disabled);
		this.stepper.refresh();
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
					options: IMPORT_TYPES.map((value) => ({ label: __(value), value })),
					default: INSERT,
					reqd: 1,
					change: () => {
						const value = this.setup_form.get_value("import_type");
						this.state.import_type = value;
						this.setup_form.set_value(
							"export_records",
							value === INSERT ? BLANK_TEMPLATE : ALL_RECORDS
						);
						this._built_step = null;
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
						{ label: __("Blank Template"), value: BLANK_TEMPLATE },
						{ label: __("All Records"), value: ALL_RECORDS },
						{ label: __("5 Records"), value: FIVE_RECORDS },
					],
					default: BLANK_TEMPLATE,
					description: __("{0} rows in this table", [
						(this.grid.frm.doc[this.grid.df.fieldname] || []).length,
					]),
				},
				{ fieldtype: "Section Break", label: __("Fields"), collapsible: 1 },
				{ fieldtype: "HTML", fieldname: "select_buttons" },
				{
					fieldtype: "MultiCheck",
					fieldname: "fields",
					columns: 2,
					sort_options: false,
					options: this.get_field_options(),
					on_change: () => this.set_footer(),
				},
			],
		});
		this.setup_form.make();
		this.make_select_buttons();
	}

	make_select_buttons() {
		const control = this.setup_form.fields_dict.fields;
		const button = (label, onclick) => frappe.ui.button({ label, size: "sm", onclick });
		$('<div class="flex items-center gap-2"></div>')
			.append(
				button(__("Select All"), () => control.select_all()),
				button(__("Select Mandatory"), () => this.select_mandatory()),
				button(__("Unselect All"), () => control.select_all(true))
			)
			.appendTo(this.setup_form.fields_dict.select_buttons.$wrapper);
	}

	select_mandatory() {
		const control = this.setup_form.fields_dict.fields;
		control.selected_options = control.options.filter((o) => o.danger).map((o) => o.value);
		control.select_options(control.selected_options);
		this.set_footer();
	}

	get_field_options(selected = []) {
		const matches_on_id = this.state.import_type !== INSERT;
		return this.get_docfields().map((df) => {
			const is_id = df.fieldname === ID_FIELDNAME;
			const mandatory = is_id ? matches_on_id : !!df.reqd;
			return {
				label: this.get_field_label(df.fieldname),
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
			this.discard_controls();
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

	sheet_url() {
		return cstr(this.sheet_form?.get_value("google_sheets_url")).trim();
	}

	make_upload_panel() {
		const $file_pane = $('<div class="grid-import-upload-pane grid-import-file-pane"></div>');
		const $sheet_pane = $('<div class="grid-import-upload-pane"></div>');

		this.upload_tabs = new frappe.ui.Tabs({
			css_class: "grid-import-upload-tabs",
			tabs: [
				{ label: __("File upload"), icon: "upload", content: $file_pane[0] },
				{ label: __("Google Sheet"), icon: "link", content: $sheet_pane[0] },
			],
			on_change: () => this.set_footer(),
		});
		this.panels.upload.append(this.upload_tabs.$el);

		this.file_uploader = new frappe.ui.FileUploader({
			wrapper: $file_pane,
			as_dataurl: true,
			allow_multiple: false,
			allow_web_link: false,
			allow_take_photo: false,
			allow_google_drive: false,
			restrictions: { allowed_file_types: FILE_TYPES },
			on_success: (file) => this.read_file(file, (rows) => this.on_file(rows)),
		});
		$file_pane.on("click change drop", () =>
			setTimeout(() => {
				this.sync_uploaded_file();
				this.set_footer();
			}, 0)
		);

		this.sheet_form = new frappe.ui.FieldGroup({
			body: $sheet_pane[0],
			no_submit_on_enter: true,
			fields: [
				{
					fieldtype: "Data",
					fieldname: "google_sheets_url",
					label: __("Import from Google Sheets"),
					description: __("Must be a publicly accessible Google Sheets URL"),
				},
			],
		});
		this.sheet_form.make();
		$sheet_pane.on("input change", () => this.set_footer());

		return this.panels.upload[0];
	}

	async upload_selected_file() {
		const files = this.file_uploader.uploader.files;
		try {
			await Promise.all(files.map((file) => file.file_obj?.slice(0, 1).arrayBuffer()));
		} catch {
			files.splice(0);
			this.panels.upload.find("input[type=file]").val("");
			this.sync_uploaded_file();
			this.set_footer();
			frappe.msgprint({
				title: __("File Changed"),
				message: __(
					"The file changed after you selected it. Select it again to load the latest version."
				),
				indicator: "orange",
			});
			return;
		}
		this.file_uploader.upload_files();
	}

	sync_uploaded_file() {
		if (this.state.google_sheets_url || this.state.library_file_url) return;
		if (!this.file_uploader || this.uploaded_file_count() || !this.state.rows.length) return;
		this.state.headers = [];
		this.state.rows = [];
		this.state.row_numbers = [];
		this.state.column_map = {};
		this._built_step = null;
		this.set_step_disabled(TAB_FIX, true);
		this.set_step_disabled(TAB_PREVIEW, true);
	}

	handle_document_mousedown(event) {
		Object.values(this.cell_controls).forEach((control) => {
			const picker = picker_api(control);
			if (!picker.el) return;

			if (control.$wrapper.closest("td").get(0)?.contains(event.target)) {
				if (!picker.is_open()) {
					picker.open();
					return;
				}
				picker.close();
				control._closed_by_cell = true;
				event.preventDefault();
				return;
			}
			if (picker.el.contains(event.target)) return;
			if (picker.is_open()) picker.close();
		});
	}

	discard_controls() {
		[...Object.values(this.cell_controls), ...this.mapping_controls].forEach(
			discard_cell_control
		);
	}

	mapping_options() {
		return [
			{ label: __("Don't Import"), value: DONT_IMPORT },
			...this.get_docfields().map((df) => ({
				label: this.get_field_label(df.fieldname),
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
		const columns = [...this.state.headers.keys()].filter(
			(index) => fixing || this.state.column_map[index]
		);
		const picked = [...this.state.row_numbers.keys()].filter((index) => {
			const row = this.state.row_numbers[index];
			const skipped = this.state.skipped_rows.has(row);
			return fixing
				? issues.has(row) || skipped || !issues.size
				: !issues.has(row) && !skipped;
		});
		const page = fixing ? this.paged(picked) : picked.slice(0, PREVIEW_ROWS);
		return {
			headers: this.state.headers,
			columns,
			rows: page.map((index) => this.state.rows[index]),
			row_numbers: page.map((index) => this.state.row_numbers[index]),
			total_rows: picked.length,
			mapping: fixing,
		};
	}

	make_pagination($table, view) {
		if (!view.mapping || view.total_rows <= FIX_PAGE_LENGTH) return;
		this.pagination = new GridPagination({
			wrapper: $table,
			grid: {
				data: new Array(view.total_rows),
				meta: { grid_page_length: FIX_PAGE_LENGTH },
				render_result_rows: () => {
					this.state.fix_page = this.pagination.page_index;
					this.build_preview(true);
				},
				scroll_to_top: () => $table.find(".grid-import-preview-table").scrollTop(0),
			},
		});
		this.pagination.page_index = this.state.fix_page;
		this.pagination.render_pagination();
		const digits = String(this.state.fix_page).length;
		this.pagination.$page_number.css("width", `${(digits + 1) * 8}px`);
	}

	paged(rows) {
		const pages = Math.ceil(rows.length / FIX_PAGE_LENGTH) || 1;
		this.state.fix_page = Math.min(this.state.fix_page, pages);
		const start = (this.state.fix_page - 1) * FIX_PAGE_LENGTH;
		return rows.slice(start, start + FIX_PAGE_LENGTH);
	}

	build_preview(keep_skipped_rows = false) {
		this.discard_controls();
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
		$table.find(".grid-import-refresh-sheet").on("click", () => this.refresh_google_sheet());
		$table.find(".grid-import-skip-all").on("click", () => this.skip_issue_rows());
		$table.on("click", ".grid-import-preview-row.has-note", (e) =>
			this.show_message(e.currentTarget.title)
		);
		this.make_pagination($table, view);
		$table.parentsUntil($panel).addBack().addClass("grid-import-fill");
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
					parent: $table.find(`.grid-import-mapping-row td[data-col="${i}"]`).get(0),
					render_input: true,
					only_input: true,
				});
				this.pin_dropdown(control);
				control.$input?.on("focus click", () => this.show_cell_message(control));
				seeded.push(control.set_value(this.state.column_map[i] || DONT_IMPORT));
				this.mapping_controls[i] = control;
			});

		this._built_step = this.tabs.get_active() === TAB_FIX ? TAB_FIX : TAB_PREVIEW;
		return Promise.all(seeded).then(() => {
			this.building_preview = false;
			return this.refresh_preview({ revalidate: [] });
		});
	}

	show_cell_message(control) {
		this.show_message(control?._warning?.message);
	}

	show_message(message = "") {
		this.$message.toggleClass("hide", !message).attr("title", message);
		this.$message.children("span").text(message);
	}

	pin_datepicker(control) {
		const picker = control.datepicker;
		const panel = picker && $(picker.$datepicker).get(0);
		if (!panel) return;

		const follower = follow_input(panel, control.$input[0], 4, () => picker.hide());
		add_unpin(control, () => follower.stop());
		const call = (hook, args) => typeof hook === "function" && hook.apply(picker, args);
		const original_show = picker.opts.onShow;
		const original_hide = picker.opts.onHide;
		picker.opts.onShow = (...args) => {
			call(original_show, args);
			panel.style.position = "fixed";
			follower.start();
		};
		picker.opts.onHide = (...args) => {
			follower.stop();
			call(original_hide, args);
		};
	}

	pin_dropdown(control) {
		const home = control.$input.closest(".awesomplete").get(0);
		const list = home?.querySelector(":scope > ul");
		if (!list) return;

		const host = document.createElement("div");
		host.className = "awesomplete grid-import-dropdown-host";
		const follower = follow_input(list, control.$input[0], 2, () =>
			control.awesomplete?.close()
		);
		add_unpin(control, () => {
			follower.stop();
			control.awesomplete?.close?.();
			if (host.contains(list)) home.appendChild(list);
			host.remove();
		});

		control.$input.on("awesomplete-open", () => {
			host.appendChild(list);
			document.body.appendChild(host);
			list.style.width = `${control.$input[0].offsetWidth}px`;
			follower.start();
		});

		control.$input.on("awesomplete-close", () => {
			follower.stop();
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
		df.read_only = 0;

		if (df.fieldtype === "Select") {
			const options = (df.options || "").split("\n").map((o) => o.trim());
			if (original && !options.includes(cstr(original).trim())) {
				const label = frappe.utils.escape_html(cstr(original));
				df.options = [{ value: original, label }, ...options];
			}
		} else if (df.fieldtype === "Link") {
			df.ignore_link_validation = true;
		}

		$(cell).removeClass("grid-import-pending-cell").addClass("grid-import-editable-cell");
		const control = frappe.ui.form.make_control({
			df: {
				...df,
				change: () => {
					if (control._seeding) return;
					this.state.rows[r][col] = control.get_value();
					this.refresh_preview({ revalidate: [r] });
				},
			},
			parent: $(cell).empty().get(0),
			render_input: true,
			only_input: true,
		});
		control._fieldname = fieldname;
		control._warning = warning;
		this.pin_datepicker(control);

		if (df.fieldtype === "Link") {
			control.set_link_title = async (value) =>
				control.translate_and_set_input_value(value, value);
			$(
				`<div class="select-icon">${frappe.utils.icon("chevrons-up-down", "sm")}</div>`
			).appendTo(control.$wrapper);
			this.pin_dropdown(control);
		}

		if (NUMERIC_FIELDTYPES.includes(df.fieldtype)) {
			control.parse = (value) => value;
			control.format_for_input = (value) => cstr(value);
			control.validate = (value) => value;
		}

		control._seeding = true;
		Promise.resolve(control.set_value(seed_value(df.fieldtype, original))).then(() => {
			control._seeding = false;
		});

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
		const rows_with_warnings = new Set();
		const notes_by_row = {};
		warnings.forEach((w) => {
			if (w.row === undefined) return;
			rows_with_warnings.add(cint(w.row));
			if (w.col === undefined) (notes_by_row[cint(w.row)] ??= []).push(w.message);
		});
		$table.find("tr[data-row]").each((_, tr) => {
			const row = cint(tr.dataset.row);
			const skipped = this.state.skipped_rows.has(row);
			const notes = notes_by_row[row];
			const $cell = $(tr).find(".grid-import-skip-cell").empty();
			$(tr).toggleClass("grid-import-skipped-row", skipped);
			$(tr)
				.find(".grid-import-preview-row")
				.toggleClass("has-note", Boolean(notes))
				.attr("title", notes ? notes.join("\n") : null);
			if (!skipped && !rows_with_warnings.has(row)) return;

			frappe.ui
				.button({
					label: skipped ? __("Restore") : __("Skip"),
					size: "sm",
					onclick: () => {
						this.state.skipped_rows[skipped ? "delete" : "add"](row);
						this.refresh_preview({ revalidate: [] });
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
				.find(`th[data-col="${i}"], .grid-import-mapping-row td[data-col="${i}"]`)
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
		const index_of_row = new Map(this.state.row_numbers.map((number, r) => [number, r]));

		$table.find("tr[data-row] td[data-col]").each((_, cell) => {
			const row = cint(cell.closest("tr").dataset.row);
			const col = cint(cell.dataset.col);
			const key = `${row}:${col}`;
			const warning = by_cell[key];
			const fieldname = this.state.column_map[col];
			const existing = this.cell_controls[key];
			const r = index_of_row.get(row);

			$(cell).toggleClass("has-error", Boolean(warning));

			if (existing) {
				if (existing._fieldname === fieldname) {
					existing._warning = warning;
					return;
				}
				discard_cell_control(existing);
				delete this.cell_controls[key];
				$(cell)
					.removeClass("grid-import-editable-cell")
					.empty()
					.text(this.state.rows[r][col]);
			}

			const mapped_df =
				fieldname && frappe.meta.get_docfield(this.grid.df.options, fieldname);
			const fieldtype = mapped_df?.fieldtype;
			$(cell).removeClass("grid-import-pending-cell").off("click.grid-import-reveal");

			if (warning?.field && DEFERRED_FIELDTYPES.includes(fieldtype)) {
				$(cell)
					.addClass("grid-import-pending-cell")
					.one("click.grid-import-reveal", () => {
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

	async refresh_preview({ revalidate = [...this.state.rows.keys()] } = {}) {
		if (this.building_preview) return;
		const request_id = ++this.preview_request_id;

		if (this.mapping_controls.length) {
			const picked = {};
			const mappable = this.mappable_fieldnames();
			this.mapping_controls.forEach((control, i) => {
				const value = control.get_value();
				if (value && value !== DONT_IMPORT && mappable.has(value)) picked[i] = value;
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

		const warnings = this.get_warnings(map);
		revalidate.forEach((r) => this.stale_rows.add(r));
		const stale = [...this.stale_rows];
		const fresh = await this.get_server_warnings(map, stale);
		if (request_id !== this.preview_request_id) return;
		const checked = new Set(stale.map((r) => this.state.row_numbers[r]));
		this.server_warnings = [
			...this.server_warnings.filter((w) => !checked.has(w.row)),
			...fresh,
		];
		this.stale_rows.clear();
		warnings.push(...this.server_warnings);
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

	has_unmapped_columns() {
		return this.state.warnings.some((w) => w.row === undefined && w.col !== undefined);
	}

	has_mapping_issues() {
		return this.state.warnings.some((w) => w.blocking && w.row === undefined);
	}

	skip_issue_rows() {
		this.get_issue_rows().forEach((row) => this.state.skipped_rows.add(row));
		this.refresh_preview({ revalidate: [] });
	}

	get_issue_rows() {
		return this.rows_matching((w) => w.blocking);
	}

	rows_matching(predicate) {
		const { warnings, skipped_rows } = this.state;
		const rows = warnings
			.filter((w) => w.row !== undefined && !skipped_rows.has(cint(w.row)) && predicate(w))
			.map((w) => cint(w.row));
		return new Set(rows);
	}

	settle_fix_step() {
		if (this.tabs.get_active() !== TAB_FIX) {
			this.set_step_disabled(TAB_FIX, !this.has_issues() && !this.has_unmapped_columns());
		}
		const $table = this.preview_form.get_field("table").$wrapper;
		$table.find(".grid-import-preview-hint").text(this.preview_hint());
		$table
			.find(".grid-import-skip-all")
			.prop("disabled", this.has_mapping_issues() || !this.get_issue_rows().size);
	}

	preview_hint() {
		const table_issue = this.state.warnings.find(
			(w) => w.blocking && w.row === undefined && w.col === undefined
		);
		if (table_issue) return table_issue.message;
		if (this.has_mapping_issues()) {
			return __("Two columns map to the same field. Fix the mapping to continue.");
		}
		const note_rows = this.rows_matching((w) => !w.blocking && w.col === undefined);
		return this.add_note_count(this.row_hint(), note_rows.size);
	}

	add_note_count(hint, count) {
		if (!count) return hint;
		const notes =
			count === 1
				? __("1 row has a note. Click its number to see it.")
				: __("{0} rows have notes. Click a row number to see them.", [count]);
		return `${hint} ${notes}`;
	}

	row_hint() {
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
		if (cint(data.length) - 1 > MAX_ROWS) {
			frappe.msgprint({
				message: __("Cannot import table with more than {0} rows.", [MAX_ROWS]),
				title: __("Too Many Rows"),
				indicator: "red",
			});
			return;
		}

		this.state.google_sheets_url = google_sheets_url;
		if (google_sheets_url) this.state.library_file_url = "";
		this.state.headers = data[0] || [];
		this.state.rows = [];
		this.state.row_numbers = [];
		data.slice(1).forEach((row, i) => {
			if (!row.some((v) => v)) return;
			this.state.rows.push(row);
			this.state.row_numbers.push(i + 2);
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
		this.state.skipped_rows = new Set();
		await this.open_checked_step();
	}

	async open_checked_step() {
		const map = this.state.column_map;
		this.preview_request_id++;
		this.server_warnings = await this.get_server_warnings(map, [...this.state.rows.keys()]);
		this.stale_rows.clear();
		this.state.warnings = [...this.get_warnings(map), ...this.server_warnings];

		const step = this.has_issues() || this.has_unmapped_columns() ? TAB_FIX : TAB_PREVIEW;
		this._built_step = null;
		this.set_step_disabled(TAB_FIX, step !== TAB_FIX);
		this.set_step_disabled(TAB_PREVIEW, false);
		if (this.tabs.get_active() === step) this.build_preview(true);
		else this.tabs.set_active(step);
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
				this.set_action(__("Next"), () => this.tabs.set_active(TAB_UPLOAD), {
					solid: true,
				});
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
					this.apply_rows(rows);
				},
				{ solid: true }
			);
			this.dialog.get_primary_btn().prop("disabled", this.has_issues());
			return;
		}

		const from_sheet = this.upload_tabs?.get_active() === UPLOAD_TAB_SHEET;
		const url = from_sheet ? this.sheet_url() : "";
		const has_source = from_sheet ? Boolean(url) : this.has_file_selection();
		this.set_action(
			__("Upload"),
			() => {
				if (!from_sheet && has_source) {
					this.upload_selected_file();
					return;
				}
				if (url && !(url === this.state.google_sheets_url && this.state.rows.length)) {
					this.read_google_sheet(url);
					return;
				}
				this.open_checked_step();
			},
			{ solid: true }
		);
		this.dialog
			.get_primary_btn()
			.prop("disabled", !has_source && this.tab_defs[TAB_PREVIEW].disabled);
	}

	download_template(file_type, fieldnames, export_records) {
		const title = this.get_title();
		const data = this.get_template_rows(fieldnames, export_records);

		if (data.length - 1 > MAX_TEMPLATE_ROWS) {
			frappe.msgprint({
				message: __(
					"Cannot download more than {0} rows. Export a blank template instead.",
					[MAX_TEMPLATE_ROWS]
				),
				title: __("Too Many Rows"),
				indicator: "red",
			});
			return;
		}

		if (file_type === "CSV") {
			frappe.tools.downloadify(data, null, title);
			return;
		}

		open_url_post("/api/method/frappe.desk.form.grid_import.download_template", {
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
			df.fieldname === ID_FIELDNAME
				? __("ID")
				: `${__(df.label || df.fieldname)} (${df.fieldname})`
		);
		const data = [header];

		let grid_rows = this.grid.frm.doc[this.grid.df.fieldname] || [];
		if (export_records === BLANK_TEMPLATE) grid_rows = [];
		else if (export_records === FIVE_RECORDS) grid_rows = grid_rows.slice(0, 5);

		grid_rows.forEach((d) => {
			data.push(
				docfields.map((df) => {
					const value = d[df.fieldname] ?? "";
					if (!value) return value;
					if (df.fieldtype === "Date") return frappe.datetime.str_to_user(value);
					return df.fieldtype === "Datetime" ? cstr(value).slice(0, 19) : value;
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
			method: "frappe.desk.form.grid_import.parse_file",
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
			method: "frappe.desk.form.grid_import.parse_google_sheet",
			args: { doctype: this.grid.frm.doctype, url },
			freeze: true,
			freeze_message: __("Reading Google Sheet"),
			callback: (r) => {
				if (r.message) this.on_file(r.message, url, is_refresh);
			},
		});
	}

	get_preview_html({ headers, rows, row_numbers, columns, mapping, total_rows }) {
		const escape = frappe.utils.escape_html;

		const head = columns.map(
			(i) => `<th data-col="${i}" data-mapped="0">${escape(cstr(headers[i]))}</th>`
		);
		const mapping_row = mapping
			? `
			<tr class="grid-import-mapping-row">
				<td class="grid-import-preview-row"></td>
				${columns.map((i) => `<td data-col="${i}"></td>`).join("")}
				<td class="grid-import-skip-cell"></td>
			</tr>
		`
			: "";
		const body = rows.map(
			(row, r) => `
				<tr data-row="${cint(row_numbers[r])}">
					<td class="grid-import-preview-row">${cint(row_numbers[r])}</td>
					${columns.map((i) => `<td data-col="${i}" data-mapped="0">${escape(cstr(row[i]))}</td>`).join("")}
					<td class="grid-import-skip-cell"></td>
				</tr>
			`
		);

		return `
			<div class="grid-import-preview-head">
				<span class="text-muted small">${
					mapping
						? __(
								"Map each column of the file to a field. Anything left unmapped is ignored."
						  )
						: this.preview_description()
				}</span>
				<div class="grid-import-preview-head-actions">
					${
						this.state.google_sheets_url
							? frappe.ui.button.html({
									label: __("Refresh"),
									icon: "refresh-cw",
									css_class: "grid-import-refresh-sheet",
							  })
							: ""
					}
					${
						mapping
							? frappe.ui.button.html({
									label: __("Skip All"),
									disabled: true,
									css_class: "grid-import-skip-all",
							  })
							: ""
					}
				</div>
			</div>
			<div class="grid-import-preview-hint text-muted small"></div>
			<div class="grid-import-preview-table">
				<table class="table table-bordered">
					<thead>
						<tr>
							<th class="grid-import-preview-row">${__("Row")}</th>
							${head.join("")}
							<th class="grid-import-skip-cell"></th>
						</tr>
					</thead>
					<tbody>${mapping_row}${body.join("")}</tbody>
				</table>
			</div>
			${
				mapping && total_rows > FIX_PAGE_LENGTH
					? '<div class="grid-import-preview-foot"><div class="grid-pagination"></div></div>'
					: ""
			}
		`;
	}

	get_mapped_fields(column_map) {
		const mappable = this.mappable_fieldnames();
		return Object.entries(column_map)
			.filter(([, fieldname]) => fieldname !== ID_FIELDNAME && mappable.has(fieldname))
			.map(([i, fieldname]) => ({
				i: cint(i),
				df: frappe.meta.get_docfield(this.grid.df.options, fieldname),
			}))
			.filter(({ df }) => df);
	}

	get_warnings(column_map) {
		const id_index = this.get_id_index(column_map);
		const rows_by_id = this.get_rows_by_id();
		const fields = this.get_mapped_fields(column_map);

		const warnings = [
			...this.get_header_warnings(column_map),
			...this.get_id_warnings(id_index, rows_by_id),
		];
		this.state.rows.forEach((row, r) => {
			const row_number = this.state.row_numbers[r];
			warnings.push(...this.get_row_warnings(row, row_number, fields, id_index, rows_by_id));
		});
		return warnings;
	}

	get_header_warnings(column_map) {
		const warnings = [];
		this.state.headers.forEach((header, i) => {
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
		const warnings = [];
		duplicated.forEach(([fieldname, columns]) => {
			const message = __("Columns {0} map to {1}. Only one column can fill a field.", [
				columns.map((i) => i + 1).join(", "),
				this.get_field_label(fieldname),
			]);
			columns.forEach((i) => warnings.push({ blocking: true, col: i, message }));
		});
		return warnings;
	}

	get_id_warnings(id_index, rows_by_id) {
		const { rows, row_numbers, import_type } = this.state;
		if (import_type === INSERT) return [];
		if (id_index === undefined) {
			return [
				{
					blocking: true,
					message: __("No column is mapped to ID, so rows can't be matched."),
				},
			];
		}

		const warnings = [];
		const file_rows_by_id = {};
		rows.forEach((row, r) => {
			const id = cstr(row[id_index]).trim();
			if (id) (file_rows_by_id[id] ??= []).push(row_numbers[r]);
		});
		Object.entries(file_rows_by_id).forEach(([id, id_rows]) => {
			if (id_rows.length > 1 && rows_by_id.has(id)) {
				const message = __("ID {0} appears in rows {1} — only the last one will apply.", [
					id,
					id_rows.join(", "),
				]);
				id_rows.forEach((row) => warnings.push({ row, message }));
			}
		});
		return warnings;
	}

	get_row_warnings(row, row_number, fields, id_index, rows_by_id) {
		const { import_type } = this.state;
		const warnings = [];

		const id = id_index === undefined ? null : cstr(row[id_index]).trim();
		if (import_type === UPDATE && id && !rows_by_id.has(id)) {
			warnings.push({
				row: row_number,
				message: __('No row in this table has the ID "{0}".', [id]),
			});
		}

		fields.forEach(({ i, df }) => {
			const message = this.get_value_error(df, cstr(row[i]).trim());
			if (message) {
				warnings.push({ blocking: true, row: row_number, col: i, field: df, message });
			}
		});

		return warnings;
	}

	get_value_error(df, value) {
		if (!value) return df.reqd ? __("This field is mandatory and is blank.") : "";

		if (df.fieldtype === "Time" && !moment(value, TIME_FORMATS(), true).isValid()) {
			return __('"{0}" is not a valid time. Use {1}', [
				value,
				frappe.datetime.get_user_time_fmt(),
			]);
		}

		if (NUMERIC_FIELDTYPES.includes(df.fieldtype) && !is_number(value)) {
			return __('"{0}" is not a valid number.', [value]);
		}

		if (
			df.fieldtype === "Check" &&
			typeof frappe.utils.string_to_boolean(value) !== "boolean"
		) {
			return __('"{0}" is not valid. Use {1}', [value, "0, 1, Yes, No"]);
		}

		if (df.fieldtype === "Rating" && !is_rating(value)) {
			return __('"{0}" is not a valid rating. Use a number between 0 and 1.', [value]);
		}

		const format = format_of(df);
		if (format && !matches_format(value, format)) {
			return __('"{0}" is not a valid {1}.', [value, __(df.options || df.fieldtype)]);
		}

		return "";
	}

	async get_server_warnings(column_map, indexes) {
		if (!indexes.length) return [];
		const { headers, rows, row_numbers } = this.state;
		const warnings = await frappe.xcall("frappe.desk.form.grid_import.validate_rows", {
			doctype: this.grid.frm.doctype,
			fieldname: this.grid.df.fieldname,
			headers: JSON.stringify(headers),
			rows: JSON.stringify(indexes.map((r) => rows[r])),
			column_map: JSON.stringify(column_map),
		});
		return warnings.map((w) => {
			const warning = {
				row: row_numbers[indexes[w.row]],
				blocking: w.blocking,
				message: w.message,
			};
			if (w.col != null) {
				warning.col = w.col;
				warning.field = frappe.meta.get_docfield(this.grid.df.options, column_map[w.col]);
			}
			return warning;
		});
	}

	async get_column_map(headers) {
		const map = await frappe.xcall("frappe.desk.form.grid_import.get_column_map", {
			doctype: this.grid.frm.doctype,
			fieldname: this.grid.df.fieldname,
			headers: JSON.stringify(headers),
		});
		const mappable = this.mappable_fieldnames();
		return Object.fromEntries(
			Object.entries(map).filter(([, fieldname]) => mappable.has(fieldname))
		);
	}

	apply_column_overrides(auto_mapped) {
		const map = { ...auto_mapped };
		Object.entries(this.state.column_overrides).forEach(([index, fieldname]) => {
			if (fieldname === DONT_IMPORT) delete map[index];
			else map[index] = fieldname;
		});
		return map;
	}

	apply_rows(rows) {
		const { import_type, column_map } = this.state;
		const id_index = this.get_id_index(column_map);
		const rows_by_id = this.get_rows_by_id();
		const fields = this.get_mapped_fields(column_map);
		const counts = { insert: 0, update: 0, skip: 0 };

		rows.forEach((row) => {
			const id = id_index === undefined ? "" : cstr(row[id_index]).trim();
			let target = import_type !== INSERT && rows_by_id.get(id);

			if (target) {
				counts.update++;
			} else if (import_type === UPDATE) {
				counts.skip++;
				return;
			} else {
				target = this.grid.frm.add_child(this.grid.df.fieldname);
				counts.insert++;
			}

			fields.forEach(({ i, df }) => {
				const format = VALUE_FORMATTERS[df.fieldtype];
				target[df.fieldname] = format ? format(row[i]) : row[i];
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

function to_seconds(value) {
	const text = cstr(value).trim();
	if (!text) return 0;
	if (SECONDS_PATTERN.test(text)) return cint(text);

	const part = (unit) => cint((text.match(new RegExp(`(\\d+)${unit}`)) || [])[1]);
	return frappe.utils.duration_to_seconds(part("d"), part("h"), part("m"), part("s"));
}

function seed_value(fieldtype, value) {
	if (fieldtype === "Check") return VALUE_FORMATTERS.Check(value);
	if (DEFERRED_FIELDTYPES.includes(fieldtype)) return "";
	return value;
}

function to_system_time(value) {
	if (!value) return value;
	const parsed = moment(value, TIME_FORMATS(), true);
	return parsed.isValid() ? parsed.format(frappe.defaultTimeFormat) : value;
}

function is_rating(value) {
	if (!is_number(value)) return false;
	const rating = flt(value);
	return rating >= 0 && rating <= 1;
}

function format_of(df) {
	if (df.fieldtype === "Phone") return "phone";
	return df.fieldtype === "Data" ? DATA_FORMATS[df.options] : "";
}

function matches_format(value, format) {
	const parts = format === "email" ? frappe.utils.split_emails(value) : [value];
	return (
		Boolean(parts?.length) && parts.every((part) => frappe.utils.validate_type(part, format))
	);
}

function is_number(value) {
	let text = cstr(value).trim();
	if (!text) return false;

	if (text.includes(" ")) {
		const parts = text.split(" ");
		if (isNaN(parseFloat(parts[0]))) text = parts.slice(parts.length - 1).join(" ");
	}

	text = strip_number_groups(text);
	return text !== "" && !isNaN(Number(text));
}

const add_unpin = (control, unpin) => {
	const previous = control._unpin;
	control._unpin = () => {
		previous?.();
		unpin();
	};
};

const discard_cell_control = (control) => {
	control?._unpin?.();
	control?.hide_picker?.();
	control?.datepicker?.destroy?.();
};

const picker_api = (control) => {
	if (control.$picker) {
		return {
			el: control.$picker.get(0),
			is_open: () => control.$picker.is(":visible"),
			open: () => control.show_picker(),
			close: () => control.hide_picker(),
		};
	}
	if (control.datepicker) {
		const picker = control.datepicker;
		return {
			el: picker.$datepicker?.get(0),
			is_open: () => Boolean(picker.visible),
			open: () => picker.show(),
			close: () => picker.hide(),
		};
	}
	return {
		el: control.awesomplete?.ul,
		is_open: () => Boolean(control.awesomplete?.opened),
		open: () => control.on_input?.({ target: { value: "" } }),
		close: () => control.awesomplete?.close(),
	};
};

const follow_input = (panel, input, offset, close) => {
	let anchor;
	const reposition = () => {
		anchor = input.getBoundingClientRect();
		place(panel, anchor, "bottom", "start", offset);
	};
	const close_if_moved = (event) => {
		if (panel.contains(event.target)) return;
		const { top, left } = input.getBoundingClientRect();
		if (top !== anchor.top || left !== anchor.left) close();
	};
	return {
		start() {
			reposition();
			window.addEventListener("resize", reposition);
			document.addEventListener("scroll", close_if_moved, { capture: true, passive: true });
		},
		stop() {
			window.removeEventListener("resize", reposition);
			document.removeEventListener("scroll", close_if_moved, { capture: true });
		},
	};
};
