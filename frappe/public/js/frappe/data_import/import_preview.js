import DataTable from "frappe-datatable";

/** True for the synthetic row-number column added during import preview. */
function is_sr_no_column(col) {
	return col?.header_title === "Sr. No" || col?.header_title === __("Sr. No");
}
import { get_columns_for_picker } from "./data_exporter";

frappe.provide("frappe.data_import");

// Same sentinel the server checks in remap_column.
const DONT_IMPORT = "Don't Import";
// Row 1 shows the file's column titles because the header holds the mapper.
const DIW_MAP_CELL = "__diw_col_map__";
const DIW_MAP_LABEL = "__diw_col_map_label__";

const DATE_FIELDTYPES = ["Date", "Datetime", "Time"];

// The auto-detected format is always offered alongside these.
const COMMON_DATE_FORMATS = [
	"%Y-%m-%d",
	"%d-%m-%Y",
	"%m-%d-%Y",
	"%d/%m/%Y",
	"%m/%d/%Y",
	"%Y/%m/%d",
	"%d.%m.%Y",
	"%d-%b-%Y",
];
const COMMON_TIME_FORMATS = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"];

/** strptime format -> human display, e.g. "%Y-%m-%d" -> "yyyy-mm-dd". */
function date_format_label(fmt) {
	return (fmt || "")
		.replace(/%Y/g, "yyyy")
		.replace(/%y/g, "yy")
		.replace(/%m/g, "mm")
		.replace(/%d/g, "dd")
		.replace(/%B/g, "Month")
		.replace(/%b/g, "Mon")
		.replace(/%H/g, "HH")
		.replace(/%I/g, "hh")
		.replace(/%M/g, "mm")
		.replace(/%S/g, "ss")
		.replace(/%p/g, "AM/PM")
		.replace(/%f/g, "SSS");
}

/** Curated format options {value, label} for a Date / Time / Datetime column. */
function get_date_format_options(fieldtype) {
	if (fieldtype === "Time") {
		return COMMON_TIME_FORMATS.map((f) => ({ value: f, label: date_format_label(f) }));
	}
	const base = COMMON_DATE_FORMATS;
	if (fieldtype === "Datetime") {
		return base.map((f) => {
			const value = `${f} %H:%M:%S`;
			return { value, label: date_format_label(value) };
		});
	}
	return base.map((f) => ({ value: f, label: date_format_label(f) }));
}

frappe.data_import.ImportPreview = class ImportPreview {
	constructor({
		wrapper,
		doctype,
		preview_data,
		provider_schema = null,
		frm,
		import_log,
		events = {},
		on_ready,
	} = {}) {
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.preview_data = preview_data;
		this.provider_schema = provider_schema || null;
		this.events = events;
		this.import_log = import_log;
		this.frm = frm;
		this.on_ready = on_ready;

		frappe.model.with_doctype(doctype, () => {
			this.refresh();
			this.on_ready?.(this);
		});
	}

	refresh() {
		this.data = this.preview_data.data;
		this.make_wrapper();
		this.prepare_columns();
		this.prepare_data();
		this._rendered_container_width = null;
		this.render_datatable_if_needed(true);
		this.add_actions();
	}

	make_wrapper() {
		let $preview = this.wrapper.find(".diw-table-preview");
		if (!$preview.length) {
			this.wrapper.html(`
				<div class="diw-table-preview min-w-0 w-full">
					<div class="diw-preview-toolbar flex items-center justify-between gap-2 mb-2">
						<div class="table-actions inline-flex items-center shrink-0"></div>
						<div class="diw-preview-toolbar-meta table-message text-base text-ink-gray-6 ms-auto text-right whitespace-nowrap"></div>
					</div>
					<div class="table-preview mt-3 min-w-0 w-full border rounded-md bg-surface-base"></div>
					<div class="diw-skipped-columns hidden mt-3 flex flex-wrap items-center gap-1.5"></div>
				</div>
			`);
			$preview = this.wrapper.find(".diw-table-preview");
		}

		this.$table_preview = $preview.find(".table-preview");
	}

	prepare_columns() {
		this.columns = this.preview_data.columns.map((col, i) => {
			let df = col.df;
			const header_label = col.header_title || df?.label || "";
			let column_width = Math.max(140, Math.min(260, header_label.length * 9 + 48));
			const is_row_number_col = is_sr_no_column(col);
			if (is_row_number_col) {
				const row_number_label = __("Sr");
				return {
					id: "srno",
					name: row_number_label,
					content: row_number_label,
					editable: false,
					focusable: false,
					align: "left",
					width: 56,
					format: (value) => {
						if (value === DIW_MAP_LABEL) return "1";
						return value == null ? "" : value;
					},
				};
			}

			if (col.skip_import || !df) {
				const title =
					frappe.utils.escape_html(col.header_title) ||
					`<i>${__("Untitled Column")}</i>`;
				let column_title = `<span class="diw-preview-col-header diw-preview-col-header--skipped inline-flex items-center gap-2 min-w-0">
					<span class="diw-preview-col-title truncate">${title}</span>
				</span>`;
				return {
					id: `skipped-${i}`,
					name:
						frappe.utils.escape_html(col.header_title) ||
						(df ? df.label : "Untitled Column"),
					content: `<span class="diw-col-map-field block min-w-0 w-full" data-col-index="${i}"></span>`,
					skip_import: true,
					editable: false,
					focusable: false,
					align: "left",
					width: column_width,
					format: (value) => {
						if (value === DIW_MAP_CELL) {
							return column_title;
						}
						return value;
					},
				};
			}

			const is_date = DATE_FIELDTYPES.includes(df.fieldtype);
			if (is_date) {
				column_width = Math.max(column_width, 200);
			}

			// Sheet title; date columns get a calendar format pill.
			let column_title = `<span class="diw-preview-col-header inline-flex items-center gap-2 min-w-0 w-full">
				<span class="diw-preview-col-title truncate min-w-0">${
					frappe.utils.escape_html(col.header_title) || df.label
				}</span>
				${
					is_date
						? `<span class="diw-col-map-fmt-mount ms-auto shrink-0 inline-flex" data-col-index="${i}"></span>`
						: ""
				}
			</span>`;

			return {
				id: df.fieldname,
				name: frappe.utils.escape_html(col.header_title),
				content: `<span class="diw-col-map-field block min-w-0 w-full" data-col-index="${i}"></span>`,
				df: df,
				editable: false,
				align: "left",
				width: column_width,
				format: (value) => {
					if (value === DIW_MAP_CELL) {
						return column_title;
					}
					return value == null ? "" : value;
				},
			};
		});
	}

	/** Current mapped field for one preview column. */
	get_column_map_value(col) {
		const df = col.df;
		if (col.skip_import || !df) return DONT_IMPORT;
		if (col.map_to_field) return col.map_to_field;
		if (col.is_child_table_field) {
			return `${col.child_table_df.fieldname}.${df.fieldname}`;
		}
		return df.fieldname;
	}

	build_mapping_row() {
		return (this.preview_data.columns || []).map((col) =>
			is_sr_no_column(col) ? DIW_MAP_LABEL : DIW_MAP_CELL
		);
	}

	prepare_data() {
		this.data = this.data.map((row) => {
			return row.map((cell) => {
				if (cell == null) {
					return "";
				}

				if (typeof cell === "string") {
					cell = frappe.utils.xss_sanitise(cell);
				}
				return cell;
			});
		});

		this._has_mapping_row = true;
		this.data = [this.build_mapping_row(), ...this.data];
	}

	/** Build or refresh the datatable. The wizard calls this again once the pane is shown. */
	render_datatable_if_needed(force = false) {
		if (!this.$table_preview?.length) return;

		// A datatable built in a hidden pane measures its columns wrong.
		if (this.frm?._data_import_wizard && !this.is_visible()) {
			this._render_pending = true;
			return;
		}

		const width = this._get_container_width();
		if (
			!force &&
			!this._render_pending &&
			this.datatable &&
			this._rendered_container_width === width
		) {
			this.setup_wizard_scroll();
			return;
		}

		this._render_pending = false;
		this._build_datatable();
		this._rendered_container_width = width;
	}

	is_visible() {
		const el = this.$table_preview?.get(0);
		return Boolean(
			el?.isConnected && el.getClientRects().length && this._get_container_width()
		);
	}

	/** Width of the visible preview pane, used before stretching columns. */
	_get_container_width() {
		const el = this.$table_preview?.get(0);
		if (!el) return 0;

		const host =
			el.closest(".diw-preview-pane-table") ||
			el.closest(".diw-step-content") ||
			el.closest(".data-import-preview-section") ||
			el.closest(".form-section") ||
			el;

		return Math.floor(host.getBoundingClientRect().width || 0);
	}

	_build_datatable() {
		const host_el = this.$table_preview.get(0);
		if (!host_el || !host_el.isConnected || !document.contains(host_el)) {
			throw new Error("Preview host unavailable");
		}
		if (!document.head) {
			throw new Error("Document head unavailable");
		}
		const columns = this._get_render_columns();
		const can_refresh = this.datatable && this._datatable_host === host_el;

		if (can_refresh) {
			try {
				this.datatable.refresh(this.data, columns);
			} catch (error) {
				// Reparenting can break datatable's stylesheet ref; rebuild instead.
				console.warn("Data Import preview datatable refresh failed; rebuilding", error);
				this.datatable.destroy();
				this.datatable = null;
			}
		} else {
			if (this.datatable) {
				this.datatable.destroy();
				this.datatable = null;
			}
		}

		if (!this.datatable) {
			try {
				this.datatable = new DataTable(host_el, {
					data: this.data,
					columns,
					layout: "fixed",
					cellHeight: 42,
					language: frappe.boot.lang,
					translations: frappe.utils.datatable.get_translations(),
					serialNoColumn: false,
					checkboxColumn: false,
					noDataMessage: __("No Data"),
					disableReorderColumn: true,
				});
				this._datatable_host = host_el;
			} catch (error) {
				this.datatable = null;
				this._datatable_host = null;
				throw error;
			}
		}

		this.render_table_message();

		if (this.data.length === 0) {
			this.datatable.style.setStyle(".dt-scrollable", {
				height: "auto",
			});
		}

		this.datatable.style.setStyle(".dt-dropdown", {
			display: "none",
		});

		this.setup_styles();

		this.setup_wizard_scroll();
		this.mount_column_map_controls();
		this.mount_date_format_controls();
		this.show_skipped_columns();
	}

	/** Grey out columns that won't be imported and list them below the table. */
	show_skipped_columns() {
		const skipped = (this.preview_data.columns || [])
			.map((col, i) => ({ col, i }))
			.filter(({ i }) => i > 0 && this._column_map_values?.[i] === DONT_IMPORT);

		const style = this.datatable?.style;
		const cells = (i) => `.dt-cell--col-${i}:not(.dt-cell--header)`;
		// Cells force their text colour with !important, so colour the content inside them.
		const content = (i) => `${cells(i)} .dt-cell__content`;
		(this._greyed_columns || []).forEach((i) => {
			style?.removeStyle(cells(i));
			style?.removeStyle(content(i));
		});
		this._greyed_columns = skipped.map(({ i }) => i);
		this._greyed_columns.forEach((i) => {
			style?.setStyle(cells(i), { backgroundColor: "var(--surface-gray-2)" });
			style?.setStyle(content(i), { color: "var(--ink-gray-4)" });
		});

		const $list = this.wrapper.find(".diw-skipped-columns");
		$list.toggleClass("hidden", !skipped.length).html(
			skipped.length
				? `<span class="text-sm text-ink-gray-6">${__("Not imported:")}</span>` +
						skipped
							.map(({ col }) =>
								frappe.ui.badge.html({
									label: col.header_title || __("Untitled Column"),
								})
							)
							.join("")
				: ""
		);
	}

	/** Stretch a few columns to fill the width instead of leaving a blank strip. */
	_get_render_columns() {
		const base_columns = (this.columns || []).map((col) => ({ ...col }));
		// The wizard scrolls horizontally, and stretching there causes visible reflow.
		if (this.$table_preview?.closest(".diw-preview-step").length) {
			return base_columns;
		}

		const container_width = this._get_container_width();
		if (!container_width || base_columns.length === 0) {
			return base_columns;
		}

		const total_width = base_columns.reduce(
			(sum, col) => sum + (Number(col.width) > 0 ? Number(col.width) : 140),
			0
		);
		if (total_width >= container_width) {
			return base_columns;
		}

		const growable_columns = base_columns.filter((col) => col.id !== "srno");
		if (!growable_columns.length) {
			return base_columns;
		}

		const extra_width = container_width - total_width;
		const extra_per_column = Math.floor(extra_width / growable_columns.length);
		if (extra_per_column <= 0) {
			return base_columns;
		}

		growable_columns.forEach((col) => {
			const current = Number(col.width) > 0 ? Number(col.width) : 140;
			col.width = current + extra_per_column;
		});

		return base_columns;
	}

	/** Fixed scroll region when the preview table is inside the wizard card. */
	setup_wizard_scroll() {
		if (!this.datatable || !this.$table_preview?.length) return;
		if (!this.$table_preview.closest(".diw-preview-step").length) return;

		const rows = this.data?.length || 0;
		const dynamic_height = Math.min(360, Math.max(220, window.innerHeight * 0.42));
		// ~44px header plus 42px per row.
		const compact_height = Math.max(120, rows * 42 + 44);
		// Size from rendered rows, not whether the file was truncated.
		const use_compact = rows > 0 && rows <= 13;
		const scroll_height = use_compact ? compact_height : dynamic_height;

		this.datatable.style.setStyle(".dt-scrollable", {
			height: `${scroll_height}px`,
			overflowX: "auto",
			overflowY: use_compact ? "hidden" : "auto",
		});
		// Leave host overflow unset so it doesn't clip the mapper dropdown.
		this.$table_preview.css({ overflowX: "", overflowY: "" });
	}

	/** Scroll to and highlight a sheet row in the table preview. */
	highlight_table_row(row_number) {
		const row_index = this.data.findIndex((row) => cint(row[0]) === cint(row_number));
		if (row_index < 0 || !this.datatable) {
			return;
		}

		if (this._highlighted_row_index != null && this._highlighted_row_index !== row_index) {
			this.datatable.style.setStyle(`.dt-row-${this._highlighted_row_index} .dt-cell`, {
				backgroundColor: "",
			});
		}

		this._highlighted_row_index = row_index;
		const is_dark = document.documentElement.getAttribute("data-theme") === "dark";
		this.datatable.style.setStyle(`.dt-row-${row_index} .dt-cell`, {
			backgroundColor: frappe.ui.color.get_color_shade(
				"yellow",
				is_dark ? "dark" : "extra-light"
			),
		});
		frappe.utils.scroll_to(this.$table_preview.find(`.dt-row-${row_index}`), true, 30);
	}

	/** Row count in the preview toolbar. */
	render_table_message() {
		const $message = this.wrapper.find(".table-message");
		const visible_rows = this._has_mapping_row ? this.data.length - 1 : this.data.length;
		if (!visible_rows) {
			$message.empty();
			return;
		}

		const { max_rows_exceeded, max_rows_in_preview, total_number_of_rows } = this.preview_data;
		const total = total_number_of_rows ?? visible_rows;
		const shown = max_rows_exceeded ? max_rows_in_preview : visible_rows;
		let text;
		if (max_rows_exceeded || shown < total) {
			text = __("Showing first {0} rows of {1}", [shown, total]);
		} else {
			text = total === 1 ? __("1 row") : __("Showing all {0} rows", [total]);
		}

		$message.text(text);
	}

	setup_styles() {
		if (!this.datatable?.style) return;
		this.datatable.style.setStyle(".dt-row", {
			height: "42px",
		});
		this.datatable.style.setStyle(".dt-cell__content", {
			display: "flex",
			alignItems: "center",
		});

		const is_dark = document.documentElement.getAttribute("data-theme") === "dark";
		// import success checkbox
		this.datatable.style.setStyle(`svg.import-success`, {
			width: "16px",
			fill: frappe.ui.color.get_color_shade("green", is_dark ? "light" : "dark"),
		});
		// Shade names are light-mode, so flip them in dark mode to keep text readable.
		let row_classes = this.datatable
			.getRows()
			.filter((row) => this.is_row_imported(row))
			.map((row) => row.meta.rowIndex)
			.map((i) => `.dt-row-${i} .dt-cell`)
			.join(",");
		this.datatable.style.setStyle(row_classes, {
			pointerEvents: "none",
			backgroundColor: frappe.ui.color.get_color_shade(
				"gray",
				is_dark ? "dark" : "extra-light"
			),
			color: frappe.ui.color.get_color_shade("gray", is_dark ? "extra-light" : "dark"),
		});

		// Tint row 1 so it reads as the file-column header.
		if (this._has_mapping_row) {
			this.datatable.style.setStyle(".dt-row-0 .dt-cell", {
				backgroundColor: "var(--surface-gray-1)",
				fontWeight: "500",
			});
		}
	}

	/** Save persists these mappings through remap_column in after_save. */
	mount_column_map_controls() {
		this._map_controls?.forEach((control) => {
			control.$wrapper?.remove();
		});
		this._map_controls = [];
		// Dropdowns portaled to <body> would leak on re-render.
		this._portaled_dropdowns?.forEach((ul) => ul.remove());
		this._portaled_dropdowns = [];
		if (this._mapping_dropdown_scroll_handler) {
			document.removeEventListener("scroll", this._mapping_dropdown_scroll_handler, true);
			this._mapping_dropdown_scroll_handler = null;
		}
		this.$table_preview?.off(".diw-map-portal");
		// What each column is mapped to right now, including unsaved picks.
		this._column_map_values = {};
		if (!this.$table_preview?.length) return;

		const is_success = this.frm?.doc?.status === "Success";

		const options = [{ label: __("Don't Import"), value: DONT_IMPORT }].concat(
			get_fields_as_options(
				this.doctype,
				get_column_map_for_preview(this.doctype, this.provider_schema)
			)
		);

		this.$table_preview.find(".diw-col-map-field").each((_, el) => {
			const i = cint(el.getAttribute("data-col-index"));
			const col = this.preview_data.columns[i];
			if (!(i > 0) || !col) return;

			const current = this.get_column_map_value(col);
			this._column_map_values[i] = current;
			let ready = false;
			let applied = current;
			const control = frappe.ui.form.make_control({
				parent: el,
				only_input: true,
				df: {
					fieldtype: "Autocomplete",
					fieldname: `column_map_${i}`,
					label: "",
					input_class: "input-xs",
					max_items: Infinity,
					options,
					default: current,
					change: () => {
						if (!ready || is_success) return;
						const next = control.get_value() || DONT_IMPORT;
						if (next === applied) return;
						applied = next;
						this._column_map_values[i] = next;
						this.show_skipped_columns();
						this.events.remap_column({ [i - 1]: next });
					},
				},
				render_input: true,
			});
			control.set_value(current);
			control.$wrapper.addClass("w-full m-0");
			control.$wrapper.find(".tooltip-content").addClass("hidden");
			control.$input.addClass("rounded w-full");
			// Disable interaction after a completed import.
			if (is_success) {
				control.$input.prop("disabled", true);
			}
			control.$wrapper.on("mousedown click", (e) => e.stopPropagation());
			ready = true;
			this._map_controls.push(control);
		});

		this.setup_mapping_dropdown_portal();
	}

	/** Shared dropdown positioning for all mapper Autocomplete inputs. */
	setup_mapping_dropdown_portal() {
		if (!this.$table_preview?.length) return;
		// Once moved to <body> the list leaves .awesomplete, so the input keeps a ref.
		const get_dropdown = (input) =>
			input._diw_map_ul || $(input).closest(".awesomplete").children("ul").get(0);

		const position_dropdown = (input) => {
			// Fixed coords break inside transformed modal contexts; skip there.
			if (input.closest(".form-in-grid")) return;
			const ul = get_dropdown(input);
			if (!ul) return;
			// Move to <body> so the list escapes the header's transform and clipping.
			if (ul.parentNode !== document.body) {
				ul.classList.add("diw-map-dropdown-portaled");
				input._diw_map_ul = ul;
				document.body.appendChild(ul);
				this._portaled_dropdowns = this._portaled_dropdowns || [];
				if (!this._portaled_dropdowns.includes(ul)) {
					this._portaled_dropdowns.push(ul);
				}
			}
			const rect = input.getBoundingClientRect();
			const list_width = Math.max(rect.width, 250);
			// Fixed positioning escapes the wizard scroll container clipping.
			$(ul).css({
				position: "fixed",
				left: `${rect.left}px`,
				top: `${rect.bottom}px`,
				width: `${list_width}px`,
				minWidth: `${list_width}px`,
				maxWidth: "420px",
				zIndex: 1050,
			});
		};

		this.$table_preview.on(
			"awesomplete-open.diw-map-portal",
			".diw-col-map-field input",
			function () {
				// Reposition next frame too; first measure can be stale after reparent.
				position_dropdown(this);
				const input = this;
				requestAnimationFrame(() => position_dropdown(input));
			}
		);
		this.$table_preview.on(
			"input.diw-map-portal focus.diw-map-portal",
			".diw-col-map-field input",
			function () {
				const ul = get_dropdown(this);
				if (ul && !$(ul).is(":hidden")) {
					position_dropdown(this);
				}
			}
		);

		if (this._mapping_dropdown_scroll_handler) {
			document.removeEventListener("scroll", this._mapping_dropdown_scroll_handler, true);
		}
		// Capture phase catches scrolls on the wizard panel and nested containers.
		const reposition_open_dropdowns = () => {
			this.$table_preview.find(".diw-col-map-field input:focus").each(function () {
				const ul = get_dropdown(this);
				if (ul && $(ul).is(":visible")) {
					position_dropdown(this);
				}
			});
		};
		document.addEventListener("scroll", reposition_open_dropdowns, true);
		this._mapping_dropdown_scroll_handler = reposition_open_dropdowns;
	}

	/** Mount calendar format pills on Date / Time / Datetime column headers. */
	mount_date_format_controls() {
		this._fmt_dropdowns?.forEach((dropdown) => dropdown.destroy?.());
		this._fmt_dropdowns = [];

		if (!this.$table_preview?.length) return;

		const can_change_format =
			this.events.set_column_date_format && this.frm?.doc?.status !== "Success";

		this.$table_preview.find(".diw-col-map-fmt-mount").each((_, mount) => {
			const i = cint(mount.getAttribute("data-col-index"));
			const col = this.preview_data.columns[i];
			if (!col?.df) return;

			const fmt_label = col.date_format
				? date_format_label(col.date_format)
				: __("Select format");
			const $btn = frappe.ui.button({
				icon: "calendar",
				label: fmt_label,
				variant: "outline",
				size: "xs",
				title: __("Select date format"),
				css_class: "rounded-full shrink-0",
			});
			$btn.on("mousedown click", (e) => e.stopPropagation());
			$btn.prop("disabled", !can_change_format);
			$(mount).empty().append($btn);
			if (!can_change_format) return;

			const dropdown = new frappe.ui.Dropdown({
				trigger: $btn,
				side: "bottom",
				align: "end",
				options: () => {
					const current = col.date_format || "";
					const formats = get_date_format_options(col.df.fieldtype);
					if (current && !formats.some((o) => o.value === current)) {
						formats.unshift({
							value: current,
							label: date_format_label(current),
							detected: true,
						});
					}
					return [
						{
							group: __("Select date format"),
							options: formats.map((o) => ({
								label: o.detected ? __("{0} (detected)", [o.label]) : o.label,
								selected: o.value === current,
								onclick: () => this.events.set_column_date_format(i - 1, o.value),
							})),
						},
					];
				},
			});
			this._fmt_dropdowns.push(dropdown);
		});
	}

	add_actions() {
		if (this.frm?.doc?.status === "Success") {
			this.wrapper.find(".table-actions").empty();
			return;
		}
		this.wrapper
			.find(".table-actions")
			.html(
				`<div class="text-base text-ink-gray-6">${__(
					"Map each file column to a field. Save to apply changes."
				)}</div>`
			);
	}

	is_row_imported(row) {
		let serial_no = row[0].content;
		return this.import_log.find((log) => {
			return log.success && JSON.parse(log.row_indexes || "[]").includes(serial_no);
		});
	}
};

function get_column_map_for_preview(doctype, provider_schema = null) {
	if (!provider_schema) {
		return get_columns_for_picker(doctype);
	}

	let out = {};
	out[doctype] = provider_schema.fields || [];
	(provider_schema.child_tables || []).forEach((ct) => {
		out[ct.fieldname] = ct.fields || [];
	});
	return out;
}

function get_fields_as_options(doctype, column_map) {
	let keys = [doctype, ...Object.keys(column_map).filter((key) => key !== doctype)];
	return [].concat(
		...keys.map((key) => {
			return (column_map[key] || []).map((df) => {
				let label = __(df.label, null, df.parent);
				let value = df.fieldname;
				if (doctype !== key) {
					// Provider child tables aren't docfields; fall back to parent label.
					const table_field = frappe.meta.get_docfield(doctype, key);
					const table_label = table_field?.label || df.parent || key;
					label = `${__(df.label, null, df.parent)} (${__(table_label)})`;
					value = `${key}.${df.fieldname}`;
				}
				return {
					label,
					value,
					description: value,
				};
			});
		})
	);
}
