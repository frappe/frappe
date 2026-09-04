// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// one row of labels, same as the Data Import doctype's own template (exporter.py add_header)
const BULK_EDIT_CSV_HEADER_ROWS = 1;
const BULK_EDIT_MAX_ROWS = 5000;
const BULK_EDIT_FILE_TYPES = [".csv", ".xlsx", ".xls"];
const BULK_EDIT_ID_FIELDNAME = "name";
// same labels as Data Import, so the strings are already translated
const BULK_EDIT_INSERT = "Insert New Records";
const BULK_EDIT_UPDATE = "Update Existing Records";
const BULK_EDIT_UPSERT = "Insert or Update Records";
const BULK_EDIT_IMPORT_TYPES = [BULK_EDIT_INSERT, BULK_EDIT_UPDATE, BULK_EDIT_UPSERT];
const BULK_EDIT_DONT_IMPORT = "Don't Import";
const BULK_EDIT_BLANK_TEMPLATE = "blank_template";
const BULK_EDIT_ALL_RECORDS = "all";
const BULK_EDIT_5_RECORDS = "5_records";
// same pattern as DURATION_PATTERN in importer.py (frappe/core/doctype/data_import/importer.py)
const BULK_EDIT_DURATION_PATTERN = /^(?:(\d+d)?((^|\s)\d+h)?((^|\s)\d+m)?((^|\s)\d+s)?)$/;
// a Duration is stored as a number of seconds, which is what the template
// exports, so a file coming back round-trip carries digits rather than "1h 30m"
const BULK_EDIT_SECONDS_PATTERN = /^\d+$/;
// the words importer.py's Row.parse_value accepts for a Check field, alongside 0/1
const BULK_EDIT_CHECK_TRUE = ["t", "true", "y", "yes"];
const BULK_EDIT_CHECK_FALSE = ["f", "false", "n", "no"];
const BULK_EDIT_CHECK_VALUES = ["0", "1", ...BULK_EDIT_CHECK_TRUE, ...BULK_EDIT_CHECK_FALSE];
const BULK_EDIT_NUMERIC_FIELDTYPES = ["Int", "Float", "Currency", "Percent"];
// Controls that paint their own widget state over the cell — "NaN:NaN:NaN" from a
// datepicker, NaN boxes from a duration picker, no word at all from a checkbox. A
// flagged cell of one keeps the file's text and builds its control on click.
const BULK_EDIT_DEFERRED_FIELDTYPES = ["Date", "Datetime", "Time", "Duration", "Check"];
// every step shares one size, so switching tabs never resizes the modal.
// the modal is sized against the window rather than in pixels: it takes 90%
// of the height, less the header and footer the body sits between, so the
// margin above and below stays even on any screen. the width comes with it,
// from .bulk-edit-dialog in grid.scss
const BULK_EDIT_DIALOG_SIZE = "extra-large";
const BULK_EDIT_DIALOG_HEIGHT = "calc(90vh - 104px)";
const BULK_EDIT_PREVIEW_ROWS = 10;

// the three steps, in the order the dialog walks them
const TAB_SETUP = 0;
const TAB_UPLOAD = 1;
const TAB_PREVIEW = 2;
// spreadsheet cells come back in system format, csv cells in the user's date format
const SYSTEM_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}/;

// Every fieldtype whose stored value is not the string the file carries. These
// mirror importer.py Row.parse_value — a value that passed validation still has
// to be converted, or it reaches the doc as text and is silently wrong.
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
	Duration: (val) => bulk_edit_to_seconds(val),
};

/** The two time formats a file may carry: the user's own, and the stored one. */
const BULK_EDIT_TIME_FORMATS = () => [
	frappe.datetime.get_user_time_fmt(),
	frappe.defaultTimeFormat,
];

/**
 * The Upload dialog behind a child table's bulk edit: download a template, feed
 * a file or a Google Sheet back in, map its columns onto fields, fix what the
 * file got wrong in place, and apply the rows to the grid.
 */
export default class BulkEdit {
	constructor(grid) {
		this.grid = grid;
	}

	get_title() {
		return this.grid.df.label || frappe.model.unscrub(this.grid.df.fieldname);
	}

	/**
	 * Value fields of the child doctype, ID first so rows can be matched on it.
	 * Read-only fields are left out — the document rewrites them on save. The one
	 * gate for template and picker alike; its twin is in bulk_edit.py.
	 */
	get_docfields() {
		return [
			{ fieldname: BULK_EDIT_ID_FIELDNAME, label: __("ID"), fieldtype: "Data" },
			...frappe
				.get_meta(this.grid.df.options)
				.fields.filter((df) => frappe.model.is_value_type(df.fieldtype) && !df.read_only),
		];
	}

	/**
	 * One modal, one size, three steps: Setup, Upload, Preview. A step unlocks once
	 * the one before it has produced what it needs and stays open afterwards, so
	 * earlier choices can be revisited. Mapping, per-cell fixes and skipping all
	 * happen in Preview, so nothing is corrected a step away from where it shows.
	 */
	show() {
		// a read only grid cannot take rows back, so only the template step applies
		this.can_import = this.grid.is_editable();
		this.state = {
			import_type: BULK_EDIT_INSERT,
			headers: [],
			rows: [],
			row_numbers: [],
			column_map: {},
			warnings: [],
			// row numbers left out of the import by their own checkbox in the preview
			skipped_rows: new Set(),
		};

		this.panels = {
			setup: $('<div class="bulk-edit-panel"></div>'),
			upload: $('<div class="bulk-edit-panel"></div>'),
			// mapping and inline fixes both live here — one step, not a
			// separate Preview/Fix Issues pair
			preview: $('<div class="bulk-edit-panel"></div>'),
		};
		// mounted inline rather than in its own dialog, so nothing stacks
		this.file_uploader = null;
		this.preview_form = null;
		this.mapping_controls = [];
		// set_value fires the control's change hook, so the initial pass would
		// redraw once per column before the last one exists. One redraw at the end
		// of the build covers them all.
		this.building_preview = false;
		// discards a stale link-check response if a newer mapping change started one first
		this.preview_request_id = 0;
		// live edit controls mounted over a flagged cell, keyed "row:col"
		this.cell_controls = {};

		this.make_dialog();
		this.make_setup_form();
		this.watch_cell_pickers();

		this.dialog.show();
		// an import type is picked by default, so upload is reachable straight away
		if (this.can_import) this.tabs.set_disabled(TAB_UPLOAD, false);
		this.set_footer();
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Upload {0}", [this.get_title()]),
			size: BULK_EDIT_DIALOG_SIZE,
			centered: true,
		});
		// the width is a share of the window too, so the modal keeps the same
		// proportions against the page that the height does
		$(this.dialog.wrapper).addClass("bulk-edit-dialog");
		// the body owns the height and each panel fills what is left under the tab
		// bar, so a tall panel scrolls inside itself instead of growing the modal
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
				this.set_footer();
			},
		});
		this.tabs.$el.addClass("bulk-edit-tabs");
		// Tabs' own bar still exists (it drives the panels) but the Stepper
		// below replaces it visually — same component the Data Import wizard
		// uses for its step row, so the two dialogs read identically.
		this.tabs.$el.find(".es-tabs__list").hide();

		this.stepper = new frappe.ui.Stepper({
			steps: this.tab_defs.map((tab) => ({ label: tab.label })),
			is_locked: (index) => this.tab_defs[index].disabled,
			on_step_click: (index) => this.tabs.set_active(index),
		});

		// tabs.set_disabled() is called from several places below to lock/unlock
		// steps as the flow progresses; wrapping it here means the stepper's
		// lock icons stay in sync everywhere, without touching each call site.
		const set_disabled = this.tabs.set_disabled.bind(this.tabs);
		this.tabs.set_disabled = (index, disabled) => {
			set_disabled(index, disabled);
			this.stepper.refresh();
		};

		// The step row reads on the modal's grey body; the panel it governs and
		// the dialog's own footer actions live together in one white card
		// underneath it — same shape as the Data Import wizard's dialog. Moving
		// dialog.footer's actual node (not rebuilding it) means set_footer()'s
		// primary/secondary action calls below need no changes.
		const $card = $('<div class="bulk-edit-card"></div>');
		this.dialog.$body.append(this.stepper.$el, $card);
		$card.append(this.tabs.$el, this.dialog.footer);

		this.tabs.$el.css({
			flex: "1 1 auto",
			"min-height": 0,
			display: "flex",
			"flex-direction": "column",
		});
		this.tabs.$el
			.find(".es-tabs__panel")
			.css({ flex: "1 1 auto", "min-height": 0, "overflow-y": "auto" });
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
					// the export that suits the import, still free to change afterwards
					change: () => {
						const value = this.setup_form.get_value("import_type");
						this.state.import_type = value;
						this.setup_form.set_value(
							"export_records",
							value === BULK_EDIT_INSERT
								? BULK_EDIT_BLANK_TEMPLATE
								: BULK_EDIT_ALL_RECORDS,
						);
						this.tabs.set_disabled(TAB_UPLOAD, !value);
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
				{ fieldtype: "Section Break" },
				{
					fieldtype: "MultiCheck",
					fieldname: "fields",
					label: __("Fields"),
					columns: 2,
					select_all: true,
					select_mandatory: true,
					sort_options: false,
					options: this.get_docfields().map((df) => {
						// ID and mandatory fields only; row-matching needs ID and the rest is opt-in
						const mandatory = df.fieldname === BULK_EDIT_ID_FIELDNAME || !!df.reqd;
						return {
							label: __(df.label || df.fieldname, null, df.parent),
							value: df.fieldname,
							checked: mandatory ? 1 : 0,
							danger: mandatory,
						};
					}),
					on_change: () => this.set_footer(),
				},
			],
		});
		this.setup_form.make();
	}

	/** Cell pickers mount on the body, so closing them is the dialog's job. */
	watch_cell_pickers() {
		// capture, so it runs before the dialog or the table can swallow the click
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
		// the bar keeps its own height regardless of what the panel below it
		// does — without this it's free to shrink (flex's default) and the
		// growing panel squeezes the tab labels
		upload_tabs.$el.find(".es-tabs__list").css({ flex: "0 0 auto" });
		// sizing only, not display — .es-tabs__panel's own display is how the
		// tab component hides the inactive pane ([data-state="inactive"]), and
		// an inline display here would win over that and show both at once.
		// overflow-y matters too: the file pane centres its content, and
		// without a scroll container of its own, anything taller than the
		// available space bleeds out both ways — up, over the tab bar, included
		upload_tabs.$el.find(".es-tabs__panel").css({
			flex: "1 1 auto",
			"min-height": 0,
			"overflow-y": "auto",
		});
		// centring (empty) vs. top-aligned (.has-file, toggled below) is in
		// grid.scss; the Google Sheet pane is a plain field, so it's always top
		$file_pane.css({ height: "100%" });
		$sheet_pane.css({ height: "100%" });

		this.file_uploader = new frappe.ui.FileUploader({
			wrapper: $file_pane,
			as_dataurl: true,
			allow_multiple: false,
			// none of these fit a CSV/Excel-only upload — Link duplicates the
			// Google Sheet tab, and Camera/Google Drive don't produce spreadsheets.
			// Library (the internal file browser) stays on, same as the PR.
			allow_web_link: false,
			allow_take_photo: false,
			allow_google_drive: false,
			restrictions: { allowed_file_types: BULK_EDIT_FILE_TYPES },
			on_success: (file) => this.read_file(file, (rows) => this.on_file(rows)),
		});
		// keep it at its natural height so the centring above has room to work
		$file_pane.children(".file-uploader").css({ flex: "0 0 auto" });
		// dropping a file or clearing one changes what the later tabs describe,
		// and whether the pane still reads as an empty drop target
		$file_pane.on("click change drop", () =>
			setTimeout(() => {
				$file_pane.toggleClass("has-file", Boolean(this.uploaded_file_count()));
				this.sync_uploaded_file();
				this.set_footer();
			}, 0),
		);

		// No separate Import button — same as the PR: entering a URL and
		// leaving the field (change fires on blur/Enter) is the trigger.
		const sheet_form = new frappe.ui.FieldGroup({
			body: $sheet_pane[0],
			no_submit_on_enter: true,
			fields: [
				{
					// same label/description as the Data Import doctype's own
					// google_sheets_url field, for the same reason it uses them
					fieldtype: "Data",
					fieldname: "google_sheets_url",
					label: __("Import from Google Sheets"),
					description: __("Must be a publicly accessible Google Sheets URL"),
					change: () => {
						const url = sheet_form.get_value("google_sheets_url");
						if (url) this.read_google_sheet(url, (rows) => this.on_file(rows));
					},
				},
			],
		});
		sheet_form.make();

		return this.panels.upload[0];
	}

	sync_uploaded_file() {
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
			// no picker, or the click is someone using it
			if (!picker || picker.contains(event.target)) return;

			if (control.$wrapper.closest("td").get(0)?.contains(event.target)) {
				// the cell toggles, since the control's own handler only ever opens
				if (!picker_is_open(control)) {
					open_picker(control);
					return;
				}
				close_picker(control);
				// both pickers open on focus, and hide() blurs the input on its way
				// out — so the focus this mousedown would deliver reopens it
				event.preventDefault();
				return;
			}
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
				// the file speaks fieldnames, so the picker shows both names
				description: df.fieldname,
			})),
		];
	}

	build_preview() {
		this.discard_cell_controls();
		this.panels.preview.empty();
		this.cell_controls = {};
		this.state.skipped_rows = new Set();
		this.preview_form = new frappe.ui.FieldGroup({
			body: this.panels.preview[0],
			no_submit_on_enter: true,
			fields: [{ fieldtype: "HTML", fieldname: "table" }],
		});
		this.preview_form.make();

		const $table = this.preview_form.get_field("table").$wrapper;
		$table.html(
			this.get_preview_html(this.state.headers, this.state.rows, this.state.row_numbers),
		);
		// FieldGroup nests the field several levels below the panel, and each level
		// sits at its content height by default — so the table would stop short and
		// leave the rest of the step empty. Walked rather than named, since the
		// depth is FieldGroup's business, not ours.
		this.panels.preview.css({ height: "100%", display: "flex", "flex-direction": "column" });
		$table.parentsUntil(this.panels.preview).addBack().css({
			display: "flex",
			"flex-direction": "column",
			flex: "1 1 auto",
			"min-height": 0,
		});
		const options = this.mapping_options();
		this.building_preview = true;
		this.mapping_controls = this.state.headers.map((header, i) => {
			const control = frappe.ui.form.make_control({
				df: {
					fieldtype: "Autocomplete",
					fieldname: `map_${i}`,
					placeholder: header || __("Column {0}", [i + 1]),
					max_items: Infinity,
					options,
					change: () => this.refresh_preview(),
				},
				parent: $table.find(`.bulk-edit-mapping-row td[data-col="${i}"]`).get(0),
				render_input: true,
				only_input: true,
			});
			// this list is every field of the child doctype, so it is long and
			// has to scroll; unpinned it is clipped by the table's own overflow
			this.pin_dropdown(control);
			control.set_value(this.state.column_map[i] || BULK_EDIT_DONT_IMPORT);
			return control;
		});
		this.building_preview = false;

		this.refresh_preview();
	}

	show_cell_message(control) {
		const message = control?._warning?.message || "";
		this.preview_form
			.get_field("table")
			.$wrapper.find(".bulk-edit-preview-message")
			.text(message)
			.attr("title", message);
	}

	pin_dropdown(control) {
		const list = () => control.$input.closest(".awesomplete").children("ul").get(0);
		// The list is closed when the page moves under it, since a fixed element
		// doesn't travel with the container it came from. Its own scrolling is
		// not that: the list is taller than its max-height and scrolls inside
		// itself, and closing on that would leave the last options reachable
		// only by typing.
		const close = (event) => {
			if (event && list()?.contains(event.target)) return;
			control.awesomplete?.close();
		};
		control.$input.on("awesomplete-open", () => {
			const rect = control.$input[0].getBoundingClientRect();
			$(list()).css({
				position: "fixed",
				top: `${rect.bottom}px`,
				left: `${rect.left}px`,
				width: `${rect.width}px`,
				"min-width": 0,
				// above the dialog and its sticky footer, which a fixed element
				// is no longer stacked against by nesting alone
				"z-index": 1050,
			});
			// capture: scroll doesn't bubble, and what scrolls here is an ancestor
			document.addEventListener("scroll", close, true);
		});
		control.$input.on("awesomplete-close", () =>
			document.removeEventListener("scroll", close, true),
		);
	}

	make_cell_control(cell, r, col, warning, fieldname) {
		const original = this.state.rows[r][col];
		const df = { ...warning.field };

		// A hidden field renders no control at all (base_control.js get_status
		// returns "None"), which would leave the cell looking empty and dead.
		// Hidden describes how the field behaves on a form; the value here is the
		// file's, still being corrected on its way in, and the import writes it
		// either way. Read-only needs no such reset — those fields are never
		// offered for mapping (get_docfields), so no cell is ever one.
		df.hidden = 0;
		df.hidden_due_to_dependency = 0;

		if (df.fieldtype === "Select") {
			// a <select> can't display a value with no matching <option> — add
			// the file's own value as one, so it shows instead of blank
			const options = (df.options || "").split("\n").map((o) => o.trim());
			if (original && !options.includes(cstr(original).trim())) {
				df.options = [original, ...options].join("\n");
			}
		} else if (df.fieldtype === "Link") {
			// ControlLink.validate() existence-checks against the server and
			// returns empty when there's no such record — exactly our case. The
			// value's invalidity is already reported by our own warning.
			df.ignore_link_validation = true;
		}

		// the input fills the whole cell (grid.scss) rather than sitting inside
		// it, so any click in the cell is a genuine click on the input — the
		// only way a native <select> reliably opens its list across browsers is
		// a real click, not a programmatic .focus()/.click()
		$(cell).addClass("bulk-edit-editable-cell");
		const control = frappe.ui.form.make_control({
			df: {
				...df,
				change: () => {
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
		// what the dropdown cue below positions itself against
		control.$wrapper.css("position", "relative");

		if (df.fieldtype === "Link") {
			// an invalid value has no record to fetch a title for, which would
			// otherwise blank the input — show it as plain text, same as every
			// other fieldtype already does
			control.set_link_title = async (value) =>
				control.translate_and_set_input_value(value, value);
			// Select gets a dropdown cue for free (ControlSelect.set_icon);
			// Link's autocomplete input doesn't. Inline position, not a
			// stylesheet rule: .select-icon's own CSS needs a positioned
			// ancestor this cell's markup doesn't reliably give it.
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
			// ControlFloat.parse() returns null for what parseFloat cannot read and
			// ControlInt.parse() turns "abc" into 0, blanking the very cell they are
			// flagged for. Hold the text; converting it is the formatters' job, on
			// apply. Only these: a deferred fieldtype is seeded empty, so it never
			// holds a bad value, and overriding its parse breaks the picker — the
			// datepicker feeds parse()'s result back through str_to_obj(), which
			// reads system format, and a user-format string there renders NaN.
			control.parse = (value) => value;
			control.format_for_input = (value) => cstr(value);
			control.validate = (value) => value;
		}

		control.set_value(bulk_edit_seed_value(df.fieldtype, original));

		// click as well as focus, since focus fires once and the cell stays focused.
		// The empty search term matters: link.js only opens on an empty input, and
		// searching on the value no record matches would list nothing.
		control.$input?.on("focus click", () => {
			this.show_cell_message(control);
			if (df.fieldtype === "Link") control.on_input({ target: { value: "" } });
		});

		return control;
	}

	render_skip_buttons($table, warnings) {
		const rows_with_warnings = new Set(
			warnings.filter((w) => w.row !== undefined).map((w) => cint(w.row)),
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
					// same options this grid's own footer buttons use (Add row,
					// Edit, Duplicate rows): default subtle variant, size sm, and
					// no red theme — skipping a row is an ordinary action, not a
					// destructive one
					size: "sm",
					onclick: () => {
						this.state.skipped_rows[skipped ? "delete" : "add"](row);
						this.refresh_preview();
					},
				})
				.appendTo($cell);
		});
	}

	sync_preview_errors(warnings) {
		const by_cell = {};
		warnings.forEach((w) => {
			if (w.row !== undefined && w.col !== undefined) by_cell[`${w.row}:${w.col}`] = w;
		});

		const $table = this.preview_form.get_field("table").$wrapper;
		this.render_skip_buttons($table, warnings);

		// tr[data-row] scopes this to the data rows: the mapping row carries
		// td[data-col] cells of its own, and they hold pickers, not values
		$table.find("tr[data-row] td[data-col]").each((_, cell) => {
			const row = cint(cell.closest("tr").dataset.row);
			const col = cint(cell.dataset.col);
			const key = `${row}:${col}`;
			const warning = by_cell[key];
			const fieldname = this.state.column_map[col];
			const existing = this.cell_controls[key];

			// red only while the value is actually invalid — the control
			// underneath stays put either way
			$(cell).toggleClass("has-error", Boolean(warning));

			if (existing) {
				// still the same target field: keep the control and just keep its
				// warning current, so re-editing is never a one-shot thing
				if (existing._fieldname === fieldname) {
					existing._warning = warning;
					return;
				}
				// the column got remapped — this control is for the field that
				// used to be here, so drop it and fall through to build a fresh
				// one for what's mapped now
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

			// A picker or a checkbox cannot show a value it cannot read — it draws
			// its own state over the input instead, which is where "NaN:NaN:NaN"
			// came from. So the faulty value stays on show as the cell's own text,
			// in the error colour, and the control is built by the click that goes
			// to resolve it: seeded clean, so the picker opens on a real time.
			if (warning?.field && BULK_EDIT_DEFERRED_FIELDTYPES.includes(fieldtype)) {
				$(cell)
					.addClass("bulk-edit-pending-cell")
					.one("click.bulk-edit-reveal", () => {
						const control = this.make_cell_control(cell, r, col, warning, fieldname);
						this.cell_controls[key] = control;
						// the click that revealed it landed on the cell, not on the control
						control.$input?.trigger("focus");
					});
				return;
			}

			// a Check whose value the box can represent reads as the box itself:
			// "Yes" and "1" both mean a tick, which is what will be imported
			if (!warning?.field && fieldtype !== "Check") return;

			this.cell_controls[key] = this.make_cell_control(
				cell,
				r,
				col,
				warning || { field: mapped_df },
				fieldname,
			);
		});

		// the edit that prompted this recompute may well have fixed the very
		// cell being edited, in which case the sentence saying what was wrong
		// with it has to go too. Focus doesn't move when a value is picked, so
		// the handler above won't fire again to clear it.
		this.show_cell_message(
			Object.values(this.cell_controls).find((c) => c.$input?.is(":focus")),
		);
	}

	async refresh_preview() {
		if (this.building_preview) return;
		const request_id = ++this.preview_request_id;

		const map = {};
		this.mapping_controls.forEach((control, i) => {
			const value = control.get_value();
			if (value && value !== BULK_EDIT_DONT_IMPORT) map[i] = value;
		});
		this.state.column_map = map;

		// a mapped column carries its values into the table, an unmapped one is
		// along for the ride; the cells say so without a legend. The header
		// text itself is the file's own and never changes with the mapping —
		// which field a column lands in is the picker's job to show, one row
		// down, and a column stays recognisable by what the file called it.
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
			map,
		);
		warnings.push(
			...(await this.get_link_warnings(this.state.rows, this.state.row_numbers, map)),
		);
		// a later mapping change already started its own refresh; let that one win
		if (request_id !== this.preview_request_id) return;
		this.state.warnings = warnings;
		// no text summary — the red, editable cells are the only warning
		// surface now; state.warnings still gates Apply below
		this.sync_preview_errors(warnings);

		this.set_footer();
	}

	async on_file(data) {
		if (cint(data.length) - BULK_EDIT_CSV_HEADER_ROWS > BULK_EDIT_MAX_ROWS) {
			frappe.throw(__("Cannot import table with more than {0} rows.", [BULK_EDIT_MAX_ROWS]));
		}

		this.state.headers = data[0] || [];
		this.state.rows = [];
		// kept alongside rows so a warning can name the line in the file
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

		this.state.column_map = await this.get_column_map(this.state.headers);
		this.build_preview();
		this.tabs.set_disabled(TAB_PREVIEW, false);
		this.tabs.set_active(TAB_PREVIEW);
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

	set_footer() {
		const active = this.tabs.get_active();
		this.dialog.get_primary_btn().addClass("hide").prop("disabled", false);
		const $secondary = this.dialog.get_secondary_btn().addClass("hide");

		if (active === TAB_SETUP) {
			this.dialog.set_secondary_action_label(__("Download Template"));
			this.dialog.set_secondary_action(() => this.download());
			$secondary.prop("disabled", !this.setup_form.get_value("fields")?.length);
			if (this.can_import) {
				this.set_action(__("Next"), () => {
					this.tabs.set_disabled(TAB_UPLOAD, false);
					this.tabs.set_active(TAB_UPLOAD);
				});
				// nothing on this tab should ever block moving on
				this.dialog.get_primary_btn().prop("disabled", false);
			}
			return;
		}

		if (active === TAB_PREVIEW) {
			// mapping and the red/editable cells are both right here —
			// Apply is the only action this step needs
			this.set_action(
				__("Apply"),
				() => {
					this.dialog.hide();
					const rows = this.state.rows.filter(
						(_, r) => !this.state.skipped_rows.has(this.state.row_numbers[r]),
					);
					this.apply_rows(rows, this.state.import_type, this.state.column_map);
				},
				{ solid: true },
			);
			// a skipped row isn't being imported, so what's wrong with it no
			// longer stands in the way of the rest of the file — same rule the
			// Data Import doctype applies (value_mapping.py: "Row warnings for
			// user-skipped rows are ignored")
			this.dialog.get_primary_btn().prop(
				"disabled",
				this.state.warnings.some(
					(w) => w.blocking && !this.state.skipped_rows.has(cint(w.row)),
				),
			);
			return;
		}

		// upload: a picked file needs uploading first; a parsed one (either
		// source, via on_file) just moves on. Stays visible either way.
		this.set_action(__("Next"), () => {
			if (this.uploaded_file_count()) {
				this.file_uploader.upload_files();
				return;
			}
			this.tabs.set_active(TAB_PREVIEW);
		});
		this.dialog
			.get_primary_btn()
			.prop("disabled", !this.uploaded_file_count() && this.tab_defs[TAB_PREVIEW].disabled);
	}

	download_template(file_type, fieldnames, export_records) {
		const title = this.get_title();
		const data = this.get_template_rows(fieldnames, export_records);

		if (file_type === "CSV") {
			frappe.tools.downloadify(data, null, title);
			return;
		}

		// the desk bundle cannot write xlsx, so the sheet is rendered on the server
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

		// One header row of "Label (fieldname)". Data Import prints the fieldname
		// only on a label clash; here always, because a spreadsheet has no picker to
		// say which field a label feeds ("Item" vs "Item Name" on Sales Invoice
		// Item). ID is the exception — the matcher knows "ID" and "name" but never
		// "ID (name)", and an unresolvable ID silently stops matching rows.
		const header = docfields.map((df) =>
			df.fieldname === BULK_EDIT_ID_FIELDNAME
				? __("ID")
				: `${__(df.label || df.fieldname)} (${df.fieldname})`,
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
				}),
			);
		});

		return data;
	}

	read_file(file, on_parsed) {
		// xlsx and xls need a reader the desk bundle does not have, and routing csv
		// through the same call keeps every format producing identical rows
		frappe.call({
			method: "frappe.desk.form.bulk_edit.parse_bulk_edit_file",
			args: {
				doctype: this.grid.frm.doctype,
				filename: file.name,
				dataurl: file.dataurl,
			},
			freeze: true,
			freeze_message: __("Reading {0}", [file.name]),
			callback: (r) => {
				if (r.message) on_parsed(r.message);
			},
		});
	}

	// Same server-side fetch Data Import uses for a Google Sheets URL
	// (frappe.utils.csvutils.get_csv_content_from_google_sheets), returning
	// rows in the same shape read_file does.
	read_google_sheet(url, on_parsed) {
		frappe.call({
			method: "frappe.desk.form.bulk_edit.parse_bulk_edit_google_sheet",
			args: { doctype: this.grid.frm.doctype, url },
			freeze: true,
			freeze_message: __("Reading Google Sheet"),
			callback: (r) => {
				if (r.message) on_parsed(r.message);
			},
		});
	}

	/**
	 * The header keeps the file's own column name, so a column stays findable by
	 * what the file calls it however it's mapped; the first body row is the
	 * picker naming the field it lands in. Two different things, one above the
	 * other, neither standing in for the other.
	 */
	get_preview_html(headers, rows, row_numbers) {
		const escape = frappe.utils.escape_html;
		const shown = rows.slice(0, BULK_EDIT_PREVIEW_ROWS);

		const head = headers.map(
			(header, i) => `<th data-col="${i}" data-mapped="0">${escape(cstr(header))}</th>`,
		);
		// trailing column: the per-row Skip button, mounted by sync_preview_errors
		// on the rows that need one. Header and mapping row carry an empty cell
		// each so the columns stay aligned.
		const mapping_row = `
			<tr class="bulk-edit-mapping-row">
				<td class="bulk-edit-preview-row"></td>
				${headers.map((header, i) => `<td data-col="${i}"></td>`).join("")}
				<td class="bulk-edit-skip-cell"></td>
			</tr>
		`;
		const body = shown.map(
			(row, r) => `
				<tr data-row="${cint(row_numbers[r])}">
					<td class="bulk-edit-preview-row">${cint(row_numbers[r])}</td>
					${headers
						.map(
							(header, i) =>
								`<td data-col="${i}" data-mapped="0">${escape(cstr(row[i]))}</td>`,
						)
						.join("")}
					<td class="bulk-edit-skip-cell"></td>
				</tr>
			`,
		);

		return `
			<div class="bulk-edit-preview-head">
				<span class="text-muted small">${__(
					"Map each column of the file to a field. Anything left unmapped is ignored.",
				)}</span>
				<span class="text-muted small">${
					rows.length > shown.length
						? __("Showing first {0} of {1} rows", [shown.length, rows.length])
						: __("Showing all {0} rows", [rows.length])
				}</span>
			</div>
			<div class="bulk-edit-preview-message text-muted small"></div>
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
		`;
	}

	/**
	 * Everything questionable about the file that can be found without touching the
	 * server. Link existence is checked separately, in {@link get_link_warnings}.
	 */
	/**
	 * Everything wrong with the file under the current mapping. A warning naming
	 * both a row and a column turns that cell red and editable; a blocking one
	 * holds Apply until it is fixed or the row is skipped.
	 */
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
				}),
			);
		});
		return warnings;
	}

	/** A column the mapping never claimed carries its values nowhere. */
	get_header_warnings(headers, column_map) {
		const warnings = [];
		headers.forEach((header, i) => {
			if (header && column_map[i] === undefined) {
				warnings.push({
					col: i + 1,
					message: __('"{0}" does not match a field and will be ignored.', [header]),
				});
			}
		});
		return warnings;
	}

	/** Rows are matched on ID, so a missing or repeated one decides what applies. */
	get_id_warnings(rows, row_numbers, import_type, id_index) {
		const warnings = [];

		if (id_index === undefined) {
			if (import_type !== BULK_EDIT_INSERT) {
				warnings.push({
					blocking: true,
					message: __(
						"No ID column is mapped, so no row can be matched. Every row will be skipped.",
					),
				});
			}
			return warnings;
		}

		// rows sharing an ID target the same row; the last one applied wins
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

	/**
	 * What is wrong with one cell's value, or "" if nothing is. The fieldtype
	 * checks mirror importer.py Row.validate_value; the numeric and Check ones
	 * additionally cover the blind spot it shares with flt() and cint(), where an
	 * unreadable value becomes 0 with no warning at all.
	 */
	get_value_error(df, value, is_new) {
		// a blank mandatory cell only matters on a row that is being created
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

		// Data Import guesses each column's own date format server-side; with no
		// round trip here, the user's format and the system's are what we check
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

		// the template exports the stored seconds, so both forms have to pass
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

		return "";
	}

	/** Existence-check every mapped Link column; batched into one call by target doctype. */
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
					]),
				),
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

	/**
	 * Column index to fieldname, for every header that names a field. Matched
	 * server-side by the Data Import doctype's own header map, so a label, a
	 * fieldname or "Label (fieldname)" all resolve — see bulk_edit.py.
	 */
	get_column_map(headers) {
		return frappe.xcall("frappe.desk.form.bulk_edit.get_bulk_edit_column_map", {
			doctype: this.grid.frm.doctype,
			fieldname: this.grid.df.fieldname,
			headers: JSON.stringify(headers),
		});
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
				// the ID is what the row was matched on, never something to overwrite
				if (fieldname === BULK_EDIT_ID_FIELDNAME) return;

				const df = frappe.meta.get_docfield(this.grid.df.options, fieldname);
				if (!df) return;

				const format = BULK_EDIT_VALUE_FORMATTERS[df.fieldtype];
				target[fieldname] = format ? format(row[i]) : row[i];
			});
		});

		this.grid.frm.refresh_field(this.grid.df.fieldname);
		frappe.show_alert({
			message: __("{0} added, {1} updated, {2} skipped — save to apply", [
				counts.insert,
				counts.update,
				counts.skip,
			]),
			indicator: "green",
		});

		// add_child() and assigning to target[fieldname] both write straight to
		// the local doc without going through frappe.model.set_value, so the form
		// is never marked changed. Without this the rows would exist only in this
		// browser and be lost on reload with no unsaved-changes warning.
		this.grid.frm.dirty();
	}
}

/** "1d 2h 30m" to seconds, via the same helper the Duration control uses. */
function bulk_edit_to_seconds(value) {
	const text = cstr(value).trim();
	if (!text) return 0;
	// already seconds — the template exports the stored value, not a duration string
	if (BULK_EDIT_SECONDS_PATTERN.test(text)) return cint(text);

	const part = (unit) => cint((text.match(new RegExp(`(\\d+)${unit}`)) || [])[1]);
	return frappe.utils.duration_to_seconds(part("d"), part("h"), part("m"), part("s"));
}

/**
 * What a freshly mounted cell control starts on. The file's own value goes in
 * unchanged wherever the control can hold it; where it cannot, the control is
 * seeded clean and the cell's own text is what keeps the faulty value on show.
 */
function bulk_edit_seed_value(fieldtype, value) {
	// ControlCheck.set_input() runs the value through cint(), reading "Yes" as 0
	if (fieldtype === "Check") return BULK_EDIT_VALUE_FORMATTERS.Check(value);
	// the rest of the deferred set is only ever mounted over a flagged cell, so the
	// value here is one the widget cannot read; starting clean opens the picker on
	// a real time rather than on nonsense, and the cell's own text is what kept the
	// faulty value on show until this click
	if (BULK_EDIT_DEFERRED_FIELDTYPES.includes(fieldtype)) return "";
	return value;
}

/** A time in the user's format to the "HH:mm:ss" the doc stores. */
function bulk_edit_to_system_time(value) {
	if (!value) return value;
	const parsed = moment(value, BULK_EDIT_TIME_FORMATS(), true);
	return parsed.isValid() ? parsed.format(frappe.defaultTimeFormat) : value;
}

/**
 * Whether the whole value reads as a number. Written against flt()'s own steps —
 * the same currency strip and the same strip_number_groups — so the locale's
 * group and decimal separators are read here exactly as they will be when the
 * value is applied, which a regex of our own would not manage.
 *
 * The last step is deliberately stricter than flt: parseFloat stops at the first
 * character it cannot read, so flt turns "12abc" into 12 and "1.2.3" into 1.2.
 * Number() rejects both, which is the point — a value that only half parses is
 * the kind that imports quietly wrong.
 */
function bulk_edit_is_number(value) {
	let text = cstr(value).trim();
	if (!text) return false;

	// flt drops a currency symbol when a space separates it from the figure
	if (text.includes(" ")) {
		const parts = text.split(" ");
		if (isNaN(parseFloat(parts[0]))) text = parts.slice(parts.length - 1).join(" ");
	}

	text = strip_number_groups(text);
	return text !== "" && !isNaN(Number(text));
}

/**
 * Drop a control's picker along with the control. air-datepicker mounts into a
 * container on the body, so one left behind outlives the cell it belonged to —
 * still on screen, with nothing left that could close it.
 */
const discard_cell_control = (control) => {
	control?.hide_picker?.();
	control?.datepicker?.destroy?.();
};

/**
 * Date, Datetime and Time carry an air-datepicker, Duration its own box; both
 * mount in the body, open on focus, and leave closing to the input's blur —
 * which never comes while that input keeps focus. So the picker hung over the
 * table when the same cell was clicked again, or the dialog around it was.
 */
const picker_of = (control) =>
	control?.$picker?.get(0) || control?.datepicker?.$datepicker?.get(0) || null;

const picker_is_open = (control) =>
	control.$picker ? control.$picker.is(":visible") : Boolean(control.datepicker?.visible);

const open_picker = (control) =>
	control.$picker ? control.show_picker() : control.datepicker?.show();

const close_picker = (control) =>
	control.$picker ? control.hide_picker() : control.datepicker?.hide();
