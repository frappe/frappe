import DataTable from "frappe-datatable";
import { get_columns_for_picker } from "./data_exporter";

frappe.provide("frappe.data_import");

frappe.data_import.ImportPreview = class ImportPreview {
	constructor({ wrapper, doctype, preview_data, frm, import_log, events = {}, on_ready } = {}) {
		this.wrapper = wrapper;
		this.doctype = doctype;
		this.preview_data = preview_data;
		this.events = events;
		this.import_log = import_log;
		this.frm = frm;
		this.on_ready = on_ready;

		frappe.model.with_doctype(doctype, () => {
			this.refresh();
			this.on_ready?.();
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
				<div class="diw-table-preview">
					<div class="diw-preview-toolbar">
						<div class="diw-preview-toolbar-actions table-actions"></div>
						<div class="diw-preview-toolbar-meta table-message"></div>
					</div>
					<div class="table-preview"></div>
				</div>
			`);
			$preview = this.wrapper.find(".diw-table-preview");
		}
		this.wrapper.off("click.import_preview_actions");
		this.wrapper.on("click.import_preview_actions", ".diw-preview-map-btn", (e) => {
			e.preventDefault();
			e.stopPropagation();
			this.show_column_mapper(e, $(e.currentTarget));
		});
		this.wrapper.on("click.import_preview_actions", ".diw-preview-col-warning-btn", (e) => {
			e.preventDefault();
			e.stopPropagation();
			this.show_column_warning(e, $(e.currentTarget));
		});

		this.$table_preview = $preview.find(".table-preview");
	}

	prepare_columns() {
		this.columns = this.preview_data.columns.map((col, i) => {
			let df = col.df;
			const header_label = col.header_title || df?.label || "";
			let column_width = Math.max(140, Math.min(260, header_label.length * 9 + 48));
			const is_row_number_col =
				col.header_title === "Sr. No" || col.header_title === __("Sr. No");
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
				};
			}

			if (col.skip_import || !df) {
				const title =
					frappe.utils.escape_html(col.header_title) ||
					`<i>${__("Untitled Column")}</i>`;
				let column_title = `<span class="diw-preview-col-header diw-preview-col-header--skipped">
					<span class="diw-preview-col-dot diw-preview-col-dot--skipped" aria-hidden="true"></span>
					<span class="diw-preview-col-title">${title}</span>
				</span>`;
				return {
					id: `skipped-${i}`,
					name:
						frappe.utils.escape_html(col.header_title) ||
						(df ? df.label : "Untitled Column"),
					content: column_title,
					skip_import: true,
					editable: false,
					focusable: false,
					align: "left",
					width: column_width,
					format: (value) => `<div class="text-muted">${value}</div>`,
				};
			}

			let date_format = col.date_format
				? col.date_format
						.replace("%Y", "yyyy")
						.replace("%y", "yy")
						.replace("%m", "mm")
						.replace("%d", "dd")
						.replace("%H", "HH")
						.replace("%M", "mm")
						.replace("%S", "ss")
						.replace("%b", "Mon")
				: null;

			let column_title = `<span class="diw-preview-col-header">
				<span class="diw-preview-col-dot diw-preview-col-dot--mapped" aria-hidden="true"></span>
				<span class="diw-preview-col-title">${
					frappe.utils.escape_html(col.header_title) || df.label
				}</span>
				${date_format ? `<span class="diw-preview-col-format text-muted">(${date_format})</span>` : ""}
			</span>`;

			return {
				id: df.fieldname,
				name: frappe.utils.escape_html(col.header_title),
				content: column_title,
				df: df,
				editable: false,
				align: "left",
				width: column_width,
			};
		});
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
	}

	render_datatable() {
		this.render_datatable_if_needed(false);
	}

	/** Build or refresh the datatable once the pane has a stable width. */
	render_datatable_if_needed(force = false) {
		if (!this.$table_preview?.length) return;

		if (!this._can_render_datatable()) {
			this._schedule_datatable_render();
			return;
		}

		const width = this._get_container_width();
		if (!force && this.datatable && this._rendered_container_width === width) {
			this.setup_wizard_scroll();
			return;
		}

		this._build_datatable();
		this._rendered_container_width = width;
	}

	/** Width of the visible preview pane — stable before stretching columns. */
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

	/** Preview may mount in a hidden wizard pane — wait until layout is visible. */
	_can_render_datatable() {
		const el = this.$table_preview?.get(0);
		if (!el) return false;

		const host =
			el.closest(".diw-preview-pane-table") ||
			el.closest(".data-import-preview-section") ||
			el.closest(".form-section");
		if (!host) return true;

		const step_panel = el.closest(".diw-step-panel");
		if (step_panel?.classList.contains("hidden")) return false;

		const style = window.getComputedStyle(host);
		if (style.display === "none" || style.visibility === "hidden") return false;
		if (host.offsetWidth <= 0) return false;
		if (this._get_container_width() <= 0) return false;
		return el.getClientRects().length > 0;
	}

	_schedule_datatable_render() {
		if (this._datatable_render_queued) return;
		this._datatable_render_queued = true;

		const try_render = (attempt = 0) => {
			if (this._can_render_datatable()) {
				this._datatable_render_queued = false;
				this.render_datatable_if_needed(true);
				return;
			}
			if (attempt < 40) {
				requestAnimationFrame(() => try_render(attempt + 1));
				return;
			}
			this._datatable_render_queued = false;
		};

		requestAnimationFrame(() => try_render(0));
	}

	_build_datatable() {
		const host_el = this.$table_preview.get(0);
		const columns = this._get_render_columns();
		const can_refresh = this.datatable && this._datatable_host === host_el;

		if (can_refresh) {
			this.datatable.refresh(this.data, columns);
		} else {
			if (this.datatable) {
				this.datatable.destroy();
			}

			this.datatable = new DataTable(host_el, {
				data: this.data,
				columns,
				layout: "fixed",
				cellHeight: 35,
				language: frappe.boot.lang,
				translations: frappe.utils.datatable.get_translations(),
				serialNoColumn: false,
				checkboxColumn: false,
				noDataMessage: __("No Data"),
				disableReorderColumn: true,
			});
			this._datatable_host = host_el;
		}

		this._datatable_container_width = this._get_container_width();
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
	}

	/**
	 * Stretch columns to fill the available width when the dataset has few columns,
	 * avoiding a large blank strip on the right side of the table.
	 */
	_get_render_columns() {
		const base_columns = (this.columns || []).map((col) => ({ ...col }));
		// Wizard uses horizontal scroll — stretching columns causes visible width reflow.
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
		const preview_limited = Boolean(this.preview_data?.max_rows_exceeded);
		const dynamic_height = Math.min(360, Math.max(220, window.innerHeight * 0.42));
		const compact_height = Math.max(120, rows * 35 + 44);
		const use_compact = rows > 0 && rows <= 10 && !preview_limited;
		const scroll_height = use_compact ? compact_height : dynamic_height;

		this.datatable.style.setStyle(".dt-scrollable", {
			height: `${scroll_height}px`,
			overflowX: "auto",
			overflowY: use_compact ? "hidden" : "auto",
		});
		this.$table_preview.css({
			overflowX: "auto",
			overflowY: "hidden",
		});
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
		this.datatable.style.setStyle(`.dt-row-${row_index} .dt-cell`, {
			backgroundColor: frappe.ui.color.get_color_shade("yellow", "extra-light"),
		});
		frappe.utils.scroll_to(this.$table_preview.find(`.dt-row-${row_index}`), true, 30);
	}

	/** Row count in the preview toolbar (right side). */
	render_table_message() {
		const $message = this.wrapper.find(".table-message");
		if (!this.data.length) {
			$message.empty();
			return;
		}

		const { max_rows_exceeded, max_rows_in_preview, total_number_of_rows } = this.preview_data;
		const total = total_number_of_rows ?? this.data.length;
		const shown = max_rows_exceeded ? max_rows_in_preview : this.data.length;
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

		// import success checkbox
		this.datatable.style.setStyle(`svg.import-success`, {
			width: "16px",
			fill: frappe.ui.color.get_color_shade("green", "dark"),
		});
		// make successfully imported rows readonly
		let row_classes = this.datatable
			.getRows()
			.filter((row) => this.is_row_imported(row))
			.map((row) => row.meta.rowIndex)
			.map((i) => `.dt-row-${i} .dt-cell`)
			.join(",");
		this.datatable.style.setStyle(row_classes, {
			pointerEvents: "none",
			backgroundColor: frappe.ui.color.get_color_shade("gray", "extra-light"),
			color: frappe.ui.color.get_color_shade("gray", "dark"),
		});
	}

	add_actions() {
		let actions = [
			{
				label: __("Map columns"),
				handler: "show_column_mapper",
				condition: this.frm.doc.status !== "Success",
			},
		];

		let html = actions
			.filter((action) => action.condition)
			.map((action) => {
				if (action.handler === "show_column_mapper") {
					const map_icon = frappe.utils.icon("arrow-right-left", "sm", "", "", "", true);
					// No inline onclick — the delegated click.import_preview_actions handler
					// owns this button; two bindings opened duplicate dialogs.
					return `<button type="button" class="btn btn-sm btn-default diw-preview-map-btn" data-action="${action.handler}">
						<span class="diw-preview-map-btn-icon">${map_icon}</span>
						${action.label}
					</button>`;
				}
				return `<button type="button" class="btn btn-sm btn-default" data-action="${action.handler}">
					${action.label}
				</button>`;
			});

		this.wrapper.find(".table-actions").html(html.join(""));
	}

	show_column_warning(_, $target) {
		const scroll_to_warning = (attempt = 0) => {
			let $warning = this.frm
				.get_field("import_warnings")
				.$wrapper.find(`[data-col=${$target.data("col")}]`);
			if ($warning?.length) {
				frappe.utils.scroll_to($warning, true, 30);
				return;
			}
			if (attempt < 10) {
				setTimeout(() => scroll_to_warning(attempt + 1), 100);
				return;
			}
			frappe.show_alert({ message: __("Column warning not found"), indicator: "orange" });
		};

		this.frm.events.go_to_wizard_step?.(this.frm, 2);
		setTimeout(() => scroll_to_warning(), 150);
	}

	show_column_mapper() {
		let column_picker_fields = get_columns_for_picker(this.doctype);
		let changed = [];
		let initial_map_by_index = {};
		let fields = this.preview_data.columns.map((col, i) => {
			let df = col.df;
			const is_row_number_col =
				col.header_title === "Sr. No" || col.header_title === __("Sr. No");
			if (is_row_number_col) return [];

			let fieldname;
			if (col.map_to_field) {
				fieldname = col.map_to_field;
			} else if (!df) {
				fieldname = null;
			} else if (col.is_child_table_field) {
				fieldname = `${col.child_table_df.fieldname}.${df.fieldname}`;
			} else {
				fieldname = df.fieldname;
			}
			initial_map_by_index[i] = fieldname || "Don't Import";
			return [
				{
					label: "",
					fieldtype: "Data",
					default: col.header_title,
					fieldname: `Column ${i}`,
					read_only: 1,
				},
				{
					fieldtype: "Column Break",
				},
				{
					fieldtype: "Autocomplete",
					fieldname: i,
					label: "",
					max_items: Infinity,
					options: [
						{
							label: __("Don't Import"),
							value: "Don't Import",
						},
					].concat(get_fields_as_options(this.doctype, column_picker_fields)),
					default: fieldname || "Don't Import",
					change() {
						changed.push(i);
					},
				},
				{
					fieldtype: "Section Break",
				},
			];
		});
		// flatten the array
		fields = fields.reduce((acc, curr) => [...acc, ...curr]);
		let file_name = (this.frm.doc.import_file || "").split("/").pop();
		let parts = [file_name.bold(), this.doctype.bold()];
		fields = [
			{
				fieldtype: "HTML",
				fieldname: "heading",
				options: `
					<div class="margin-top text-muted">
					${__("Map columns from {0} to fields in {1}", parts)}
					</div>
				`,
			},
			{
				fieldtype: "Section Break",
			},
		].concat(fields);

		if (this._column_mapper_dialog) {
			this._column_mapper_dialog.hide();
			this._column_mapper_dialog.$wrapper?.remove();
			this._column_mapper_dialog = null;
		}

		let dialog = new frappe.ui.Dialog({
			title: __("Map Columns"),
			fields,
			primary_action: (values) => {
				let changed_map = {};
				changed.map((i) => {
					let header_row_index = i - 1;
					const next_value = values[i] || "Don't Import";
					const current_value = initial_map_by_index[i] || "Don't Import";
					if (next_value !== current_value) {
						changed_map[header_row_index] = next_value;
					}
				});
				if (Object.keys(changed_map).length > 0) {
					this.events.remap_column(changed_map);
				}
				dialog.hide();
			},
		});
		this._column_mapper_dialog = dialog;
		dialog.$body.addClass("map-columns");
		dialog.show();
	}

	is_row_imported(row) {
		let serial_no = row[0].content;
		return this.import_log.find((log) => {
			return log.success && JSON.parse(log.row_indexes || "[]").includes(serial_no);
		});
	}
};

function get_fields_as_options(doctype, column_map) {
	let keys = [doctype];
	frappe.meta.get_table_fields(doctype).forEach((df) => {
		keys.push(df.fieldname);
	});
	// flatten array
	return [].concat(
		...keys.map((key) => {
			return column_map[key].map((df) => {
				let label = __(df.label, null, df.parent);
				let value = df.fieldname;
				if (doctype !== key) {
					let table_field = frappe.meta.get_docfield(doctype, key);
					label = `${__(df.label, null, df.parent)} (${__(table_field.label)})`;
					value = `${table_field.fieldname}.${df.fieldname}`;
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
