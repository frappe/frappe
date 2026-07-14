// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import GridRow from "./grid_row";
import GridPagination from "./grid_pagination";

const BULK_EDIT_CSV_HEADER_ROWS = 7; // title, labels, fieldnames, descriptions, 2 instructions, separator

// Static pixel column widths; legacy map migrates old 1-12 `columns`/`colsize`.
export const GRID_MIN_COLUMN_WIDTH = 60;
export const GRID_MAX_COLUMN_WIDTH = 600;
export const DEFAULT_COLUMN_WIDTHS = {
	Text: 200,
	"Small Text": 200,
	"Long Text": 200,
	Check: 60,
	Int: 100,
	Float: 100,
	Currency: 100,
	Percent: 100,
};

export const LEGACY_COLSIZE_TO_PX = {
	1: 60,
	2: 100,
	3: 140,
	4: 200,
	5: 250,
	6: 300,
	7: 350,
	8: 400,
	9: 450,
	10: 500,
	11: 550,
	12: 600,
};

frappe.ui.form.get_open_grid_form = function () {
	return $(".grid-row-open").data("grid_row");
};

frappe.ui.form.close_grid_form = function () {
	const open_form = frappe.ui.form.get_open_grid_form();
	open_form && open_form.hide_form();

	// hide editable row too
	if (frappe.ui.form.editable_row) {
		frappe.ui.form.editable_row.toggle_editable_row(false);
	}
};

export default class Grid {
	constructor(opts) {
		$.extend(this, opts);
		this.fieldinfo = {};
		this.doctype = this.df.options;

		this.sticky_offsets = {};

		if (this.doctype) {
			this.meta = frappe.get_meta(this.doctype);
		}
		this.fields_map = {};
		// per-grid column visibility overrides set via `set_column_disp`. Kept
		// grid-local (rather than mutating the shared meta docfield) so two grids
		// of the same child doctype on the same form don't affect each other.
		this.column_disp_overrides = {};
		this.template = null;
		this.multiple_set = false;
		if (
			this.frm &&
			this.frm.meta.__form_grid_templates &&
			this.frm.meta.__form_grid_templates[this.df.fieldname]
		) {
			this.template = this.frm.meta.__form_grid_templates[this.df.fieldname];
		}
		this.filter = {};
		this.is_grid = true;
		this.debounced_refresh = this.refresh.bind(this);
		this.debounced_refresh = frappe.utils.debounce(this.debounced_refresh, 100);
	}

	get perm() {
		return this.control?.perm || this.frm?.perm || this.df.perm;
	}

	set perm(_perm) {
		console.error("Setting perm on grid isn't supported, update form's perm instead");
	}

	allow_on_grid_editing() {
		return !this.meta || !!this.meta.editable_grid;
	}

	make() {
		let template = `
			<div class="grid-field">
				<label class="control-label">${__(this.df.label || "", null, this.df.parent)}</label>
				<span class="help"></span>
				<p class="text-muted small grid-description"></p>
				<div class="grid-custom-buttons"></div>
				<div class="form-grid-container">
					<div class="form-grid">
						<div class="grid-heading-row"></div>
						<div class="grid-body">
							<div class="rows"></div>
							<div class="grid-empty text-center text-extra-muted">
								${__("No rows")}
							</div>
						</div>
					</div>
				</div>
				<div class="small form-clickable-section grid-footer">
					<div class="flex justify-between">
						<div class="grid-buttons">
							<button type="button" class="btn btn-xs btn-danger grid-remove-rows hidden"
								data-action="delete_rows">
								${__("Delete")}
							</button>
							<button type="button" class="btn btn-xs btn-secondary grid-edit-rows hidden"
								data-action="bulk_edit_rows">
								${__("Edit")}
							</button>
							<button type="button" class="btn btn-xs btn-danger grid-remove-all-rows hidden"
							data-action="delete_all_rows">
							${__("Delete all")}
							</button>
							<button type="button" class="btn btn-xs btn-secondary grid-duplicate-rows hidden"
								data-action="duplicate_rows">
								${__("Duplicate rows")}
							</button>
							<!-- hack to allow firefox include this in tabs -->
							<button type="button" class="btn btn-xs btn-secondary grid-add-row">
								${__("Add row")}
							</button>
							<button type="button" class="grid-add-multiple-rows btn btn-xs btn-secondary hidden">
								${__("Add multiple")}</a>
							</button>
						</div>
						<div class="grid-pagination">
						</div>
						<div class="grid-bulk-actions text-right">
							<button type="button" class="grid-download btn btn-xs btn-secondary hidden">
								${__("Download")}
							</button>
							<button type="button" class="grid-upload btn btn-xs btn-secondary hidden">
								${__("Upload")}
							</button>
						</div>
					</div>
				</div>
			</div>
		`;

		this.wrapper = $(template).appendTo(this.parent);
		$(this.parent).addClass("form-group");
		this.set_grid_description();
		this.set_doc_url();

		frappe.utils.bind_actions_with_object(this.wrapper, this);

		this.form_grid = this.wrapper.find(".form-grid");

		this.form_grid.on("scroll", (e) => {
			if ($(e.currentTarget).scrollLeft() > 0) {
				this.grid_rows.forEach((grid_row) => {
					grid_row.on_grid_fields.forEach((field) => {
						if (field.df.fieldtype === "Link" && field.awesomplete) {
							field.awesomplete.close();
						}
					});
				});
			}
		});

		this.setup_add_row();

		this.setup_grid_pagination();
		this.update_idx_and_name();

		this.custom_buttons = {};
		this.grid_buttons = this.wrapper.find(".grid-buttons");
		this.grid_custom_buttons = this.wrapper.find(".grid-custom-buttons");
		this.remove_rows_button = this.grid_buttons.find(".grid-remove-rows");
		this.edit_rows_button = this.grid_buttons.find(".grid-edit-rows");
		this.duplicate_rows_button = this.grid_buttons.find(".grid-duplicate-rows");
		this.remove_all_rows_button = this.grid_buttons.find(".grid-remove-all-rows");

		this.setup_allow_bulk_edit();
		this.setup_check();
		if (this.df.on_setup) {
			this.df.on_setup(this);
		}
	}
	set_grid_description() {
		let description_wrapper = $(this.parent).find(".grid-description");
		if (this.df.description) {
			description_wrapper.html(__(this.df.description));
		} else {
			description_wrapper.hide();
		}
	}

	update_idx_and_name() {
		this.data.forEach((d, ri) => {
			if (d.idx === undefined) {
				d.idx = ri + 1;
			}
			if (d.name === undefined) {
				d.name = this.get_random_name();
			}
		});
	}

	get_random_name() {
		return Math.random().toString(36).slice(2, 10);
	}

	set_doc_url() {
		let unsupported_fieldtypes = frappe.model.no_value_type.filter(
			(x) => frappe.model.table_fields.indexOf(x) === -1
		);

		if (
			!this.df.label ||
			!this.df?.documentation_url ||
			unsupported_fieldtypes.includes(this.df.fieldtype)
		)
			return;

		let $help = $(this.parent).find("span.help");
		$help.empty();
		$(`<a href="${this.df.documentation_url}" target="_blank">
			${frappe.utils.icon("circle-question-mark", "sm")}
		</a>`).appendTo($help);
	}

	setup_grid_pagination() {
		this.grid_pagination = new GridPagination({
			grid: this,
			wrapper: this.wrapper,
		});
	}

	setup_check() {
		this.wrapper.on("click touchend", ".grid-row-check", (e) => {
			if (e.type === "touchend") {
				e.stopPropagation();
				return;
			}

			const $check = $(e.currentTarget);
			const checked = $check.prop("checked");
			const is_select_all = $check.parents(".grid-heading-row:first").length !== 0;
			const docname = $check.parents(".grid-row:first")?.attr("data-name");

			if (is_select_all) {
				// (un)check all visible checkboxes
				this.form_grid.find(".grid-row-check").prop("checked", checked);

				// set following rows as checked in model
				let result_length = this.grid_pagination.get_result_length();
				let page_index = this.grid_pagination.page_index;
				let page_length = this.grid_pagination.page_length;
				for (let ri = (page_index - 1) * page_length; ri < result_length; ri++) {
					this.grid_rows[ri].select(checked);
				}
			} else if (docname) {
				if (e.shiftKey && this.last_checked_docname) {
					this.check_range(docname, this.last_checked_docname, checked);
				}
				this.grid_rows_by_docname[docname].select(checked);
				this.last_checked_docname = docname;
			}

			const num_selected_rows = this.get_selected_children().length;

			// toggle "Add row" button
			this.wrapper
				.find(".grid-add-row, .grid-add-multiple-rows")
				.toggleClass(
					"hidden",
					num_selected_rows > 0 ||
						this.cannot_add_rows ||
						(this.df && this.df.cannot_add_rows)
				);

			// update "Delete" and "Duplicate" button labels
			if (num_selected_rows == 1) {
				this.remove_rows_button.text(__("Delete row"));
				this.edit_rows_button.text(__("Edit row"));
				this.duplicate_rows_button.text(__("Duplicate row"));
			} else {
				this.remove_rows_button.text(__("Delete {0} rows", [num_selected_rows]));
				this.edit_rows_button.text(__("Edit {0} rows", [num_selected_rows]));
				this.duplicate_rows_button.text(__("Duplicate {0} rows", [num_selected_rows]));
			}

			this.refresh_remove_rows_button();
			this.refresh_edit_rows_button();
			this.refresh_duplicate_rows_button();
		});
	}

	/**
	 * Checks or unchecks all checkboxes between two rows (included), given their docnames.
	 * Rows are only checked only if both parameters are valid docnames.
	 * @param {string} docname1
	 * @param {string} docname2
	 */
	check_range(docname1, docname2, checked = true) {
		const row_1 = this.grid_rows_by_docname[docname1];
		const row_2 = this.grid_rows_by_docname[docname2];
		const index_1 = this.grid_rows.indexOf(row_1);
		const index_2 = this.grid_rows.indexOf(row_2);
		if (index_1 === -1 || index_2 === -1) return;
		const [start, end] = [index_1, index_2].sort((a, b) => a - b);
		const rows = this.grid_rows.slice(start, end + 1);
		for (const row of rows) {
			row.select(checked);
			row.row_check?.find(".grid-row-check").prop("checked", checked);
		}
	}

	duplicate_rows() {
		let selected_children = this.get_selected_children();
		selected_children.forEach((doc) => {
			this.add_new_row(null, null, false, doc, false);
			this.check_range(doc.name, doc.name, false);
		});
	}

	delete_rows() {
		var dirty = false;

		let tasks = [];
		let selected_children = this.get_selected_children();
		selected_children.forEach((doc) => {
			tasks.push(() => {
				if (!this.frm) {
					this.df.data = this.get_data();
					this.df.data = this.df.data.filter((row) => row.idx != doc.idx);
				}
				this.grid_rows_by_docname[doc.name]?.remove();
				dirty = true;
			});
			tasks.push(() => frappe.timeout(0.1));
		});

		if (!this.frm) {
			tasks.push(() => {
				// reorder idx of df.data
				this.df.data.forEach((row, index) => (row.idx = index + 1));
			});
		}

		tasks.push(() => {
			if (dirty) {
				this.refresh();
				this.frm &&
					this.frm.script_manager.trigger(this.df.fieldname + "_delete", this.doctype);
			}
		});

		frappe.run_serially(tasks);

		this.wrapper.find(".grid-heading-row .grid-row-check:checked:first").prop("checked", 0);
		if (selected_children.length == this.grid_pagination.page_length) {
			this.scroll_to_top();
		}
	}

	delete_all_rows() {
		const num_rows = this.data.length;
		frappe.confirm(__("Are you sure you want to delete all {0} rows?", [num_rows]), () => {
			this.frm.doc[this.df.fieldname] = [];
			$(this.parent).find(".rows").empty();
			this.grid_rows = [];
			this.refresh();
			this.frm &&
				this.frm.script_manager.trigger(this.df.fieldname + "_delete", this.doctype);
			this.frm && this.frm.dirty();
			this.scroll_to_top();
		});
	}

	scroll_to_top() {
		frappe.utils.scroll_to(this.wrapper);
	}

	select_row(name) {
		this.grid_rows_by_docname[name].select();
	}

	remove_all() {
		this.grid_rows.forEach((row) => {
			row.remove();
		});
	}

	_any_rows_checked() {
		return !!this.wrapper.find(".grid-body .grid-row-check:checked:first").length;
	}

	refresh_remove_rows_button() {
		if (this.df.cannot_delete_rows) {
			return;
		}

		const has_checked = this._any_rows_checked();
		this.remove_rows_button.toggleClass("hidden", !has_checked);
		this.duplicate_rows_button.toggleClass(
			"hidden",
			!has_checked || this.cannot_add_rows || (this.df && this.df.cannot_add_rows)
		);

		const all_checked = !!this.wrapper.find(".grid-heading-row .grid-row-check:checked:first")
			.length;
		const show_delete_all_btn =
			all_checked && this.data.length > this.get_selected_children().length;
		this.remove_all_rows_button.toggleClass("hidden", !show_delete_all_btn);

		if (show_delete_all_btn) {
			this.remove_all_rows_button.text(__("Delete all {0} rows", [this.data.length]));
		}
	}

	refresh_edit_rows_button() {
		if (!this.meta?.allow_bulk_edit) {
			this.edit_rows_button.toggleClass("hidden", true);
			return;
		}

		this.edit_rows_button.toggleClass("hidden", !this._any_rows_checked());
	}

	debounced_refresh_remove_rows_button = frappe.utils.debounce(
		this.refresh_remove_rows_button,
		100
	);

	refresh_duplicate_rows_button() {
		if (this.df.cannot_add_rows || (this.df && this.df.cannot_add_rows)) {
			return;
		}

		this.duplicate_rows_button.toggleClass("hidden", !this._any_rows_checked());
	}

	debounced_duplicate_rows_button = frappe.utils.debounce(
		this.refresh_duplicate_rows_button,
		100
	);

	get_selected() {
		return (this.data || []).filter((doc) => doc.__checked).map((doc) => doc.name);
	}

	get_selected_children() {
		return (this.data || []).filter((row) => row.__checked);
	}

	_teardown_column_layout() {
		this.visible_columns = [];
		this.grid_rows = [];
		$(this.parent).find(".grid-body .grid-row").remove();
	}

	reset_grid() {
		this._teardown_column_layout();
		this.refresh();
	}

	make_head() {
		if (this.prevent_build) return;

		// labels
		if (this.header_row) {
			$(this.parent).find(".grid-heading-row .grid-row").remove();
		}
		this.header_row = new GridRow({
			parent: $(this.parent).find(".grid-heading-row"),
			parent_df: this.df,
			docfields: this.docfields,
			frm: this.frm,
			grid: this,
			configure_columns: true,
			header_row: true,
		});

		this.header_search = new GridRow({
			parent: $(this.parent).find(".grid-heading-row"),
			parent_df: this.df,
			docfields: this.docfields,
			frm: this.frm,
			grid: this,
			show_search: true,
		});
		this.header_search.row.addClass("filter-row");
		if (this.header_search.show_search || this.header_search.show_search_row()) {
			$(this.parent).find(".grid-heading-row").addClass("with-filter");
		} else {
			$(this.parent).find(".grid-heading-row").removeClass("with-filter");
		}

		this.filter_applied && this.update_search_columns();

		this.setup_column_resize();
	}

	setup_column_resize() {
		if (frappe.is_mobile() || !this.wrapper) return;

		let me = this;
		// Unique namespace per grid so multiple grids don't unbind each other.
		let ns =
			this._resize_ns || (this._resize_ns = "grid-col-resize-" + this.get_random_name());

		this.wrapper.off(`mousedown.${ns}`);
		this.wrapper.on(
			`mousedown.${ns}`,
			".grid-heading-row .grid-col-resize-handle",
			function (e) {
				e.preventDefault();
				e.stopPropagation();
				let $col = $(this).closest(".grid-static-col");
				let fieldname = $col.attr("data-fieldname");
				if (!fieldname) return;

				let start_x = e.pageX;
				let start_width = $col.outerWidth();
				$("body").addClass("grid-col-resizing");

				// Bind document listeners only for the drag, so they don't outlive it.
				$(document)
					.on(`mousemove.${ns}`, function (ev) {
						let width = me.clamp_column_width(start_width + (ev.pageX - start_x));
						me.wrapper.find(`.grid-static-col[data-fieldname="${fieldname}"]`).css({
							width: `${width}px`,
							flex: `0 0 ${width}px`,
						});
					})
					.on(`mouseup.${ns}`, function (ev) {
						$(document).off(`mousemove.${ns} mouseup.${ns}`);
						$("body").removeClass("grid-col-resizing");
						me.save_column_width(
							fieldname,
							me.clamp_column_width(start_width + (ev.pageX - start_x))
						);
					});
			}
		);
	}

	save_column_width(fieldname, width) {
		if (!this.frm) return;

		let columns = this.visible_columns.map((col) => {
			let df = col[0];
			if (df.fieldname === fieldname) {
				df.width = width;
				// setup_columns renders from col[1]; keep it in sync for new rows.
				col[1] = width;
			}
			return {
				fieldname: df.fieldname,
				width: this.get_column_width(df),
				sticky: df.sticky ? 1 : 0,
			};
		});

		// Recompute sticky offsets with the new width and patch the DOM so
		// subsequent sticky columns don't shift without a page reload.
		this.sticky_offsets = {};
		let sticky_sum = 71;
		for (let [df, w] of this.visible_columns) {
			if (df.sticky) {
				this.sticky_offsets[df.fieldname] = sticky_sum;
				this.wrapper
					.find(`.grid-static-col[data-fieldname="${df.fieldname}"]`)
					.css("left", `${sticky_sum}px`);
				sticky_sum += w;
			}
		}

		let value = {};
		value[this.doctype] = columns;
		frappe.model.user_settings.save(this.frm.doctype, "GridView", value).then((r) => {
			frappe.model.user_settings[this.frm.doctype] = r.message || r;
		});
	}

	update_search_columns() {
		for (const field in this.filter) {
			if (this.filter[field] && !this.header_search.search_columns[field]) {
				delete this.filter[field];
				this.data = this.get_data(this.filter_applied);
				break;
			}

			if (this.filter[field] && this.filter[field].value) {
				let $input = this.header_search.row_index.find("input");
				if (field && field !== "row-index") {
					$input = this.header_search.search_columns[field].find("input");
				}
				$input.val(this.filter[field].value);
			}
		}
	}

	refresh() {
		if (this.frm && this.frm.setting_dependency) return;

		this.filter_applied = Object.keys(this.filter).length !== 0;
		this.data = this.get_data(this.filter_applied);

		!this.wrapper && this.make();
		let $rows = $(this.parent).find(".rows");

		this.setup_fields();

		if (this.frm) {
			this.display_status = frappe.perm.get_field_display_status(
				this.df,
				this.frm.doc,
				this.perm
			);
		} else if (this.df.is_web_form && this.control) {
			this.display_status = this.control.get_status();
		} else {
			// not in form
			this.display_status = "Write";
		}

		if (this.display_status === "None") return;

		// redraw
		this.make_head();

		if (!this.grid_rows) {
			/** @type {GridRow[]} */
			this.grid_rows = [];
		}

		/** @type {Record<string, GridRow>} */
		this.grid_rows_by_docname = {};

		this.grid_pagination.update_page_numbers();
		this.render_result_rows($rows);
		this.grid_pagination.check_page_number();
		this.wrapper.find(".grid-empty").toggleClass("hidden", Boolean(this.data.length));

		// toolbar
		this.setup_toolbar();
		this.toggle_checkboxes(this.display_status !== "Read");

		// sortable
		if (this.is_sortable() && !this.sortable_setup_done) {
			this.make_sortable($rows);
			this.sortable_setup_done = true;
		}

		this.last_display_status = this.display_status;
		this.last_docname = this.frm && this.frm.docname;

		// red if mandatory
		this.form_grid.toggleClass("error", !!(this.df.reqd && !(this.data && this.data.length)));

		this.refresh_remove_rows_button();
		this.refresh_edit_rows_button();
		this.refresh_duplicate_rows_button();

		this.wrapper.trigger("change");
	}

	render_result_rows($rows) {
		if (!$rows) {
			$rows = $(this.parent).find(".rows");
		}

		let result_length = this.grid_pagination.get_result_length();
		let page_index = this.grid_pagination.page_index;
		let page_length = this.grid_pagination.page_length;
		let page_start = (page_index - 1) * page_length;
		if (!this.grid_rows) {
			return;
		}

		// index existing rows by doc object reference for identity-based matching
		let rows_by_doc = new Map();
		for (let row of this.grid_rows) {
			if (row?.doc) {
				rows_by_doc.set(row.doc, row);
			}
		}

		let matched_rows = new Set();

		for (let ri = page_start; ri < result_length; ri++) {
			const d = this.data[ri];
			if (!d) {
				return;
			}
			if (d.idx === undefined) {
				d.idx = ri + 1;
			}
			if (d.name === undefined) {
				d.name = this.get_random_name();
			}

			let grid_row = rows_by_doc.get(d);
			if (grid_row) {
				matched_rows.add(grid_row);
				grid_row.refresh();
			} else {
				grid_row = new GridRow({
					parent: $rows,
					parent_df: this.df,
					docfields: this.docfields,
					doc: d,
					frm: this.frm,
					grid: this,
				});
			}
			this.grid_rows[ri] = grid_row;
			this.grid_rows_by_docname[d.name] = grid_row;
		}

		// remove stale / invisible rows
		for (let [, row] of rows_by_doc) {
			if (!matched_rows.has(row)) {
				row.wrapper.remove();
			}
		}

		// reorder DOM from the first mismatch onward
		let $children = $rows.children();
		let page_count = result_length - page_start;
		let reorder_from = -1;
		for (let i = 0; i < page_count; i++) {
			if ($children.get(i) !== this.grid_rows[page_start + i].wrapper.get(0)) {
				reorder_from = i;
				break;
			}
		}
		if (reorder_from >= 0) {
			for (let ri = page_start + reorder_from; ri < result_length; ri++) {
				$rows.append(this.grid_rows[ri].wrapper);
			}
		}

		// clear non-visible slots to prevent duplicates and stale references
		for (let i = 0; i < this.grid_rows.length; i++) {
			if (i < page_start || i >= result_length) {
				delete this.grid_rows[i];
			}
		}

		if (this.grid_rows.length > this.data.length) {
			this.grid_rows.length = this.data.length;
		}
	}

	setup_toolbar() {
		const is_editable = this.is_editable();
		if (is_editable) {
			this.wrapper.find(".grid-footer").removeClass("hidden");

			const num_selected_rows = this.get_selected_children().length;
			// show, hide buttons to add rows
			if (
				this.cannot_add_rows ||
				(this.df && this.df.cannot_add_rows) ||
				num_selected_rows > 0
			) {
				// add 'hidden' to buttons
				this.wrapper
					.find(".grid-add-row, .grid-add-multiple-rows, .grid-duplicate-rows")
					.addClass("hidden");
			} else {
				// show buttons
				this.wrapper.find(".grid-add-row").removeClass("hidden");

				if (this.multiple_set) {
					this.wrapper.find(".grid-add-multiple-rows").removeClass("hidden");
				}
			}
		} else if (
			this.grid_rows.length < this.grid_pagination.page_length &&
			!this.df.allow_bulk_edit
		) {
			this.wrapper.find(".grid-footer").addClass("hidden");
		}

		// don't be tempted to use the `.hidden` class here
		// it is used in other logic for the same buttons and will cause conflicts
		this.wrapper
			.find(".grid-add-row, .grid-add-multiple-rows, .grid-upload")
			.toggleClass("d-none", !is_editable);
	}

	setup_fields() {
		// reset docfield
		if (this.frm && this.frm.docname) {
			// use doc specific docfield object
			this.df = frappe.meta.get_docfield(
				this.frm.doctype,
				this.df.fieldname,
				this.frm.docname
			);
		} else {
			// use non-doc specific docfield
			if (this.df.options) {
				this.df =
					frappe.meta.get_docfield(this.df.options, this.df.fieldname) ||
					this.df ||
					null;
			}
		}

		if (this.doctype && this.frm) {
			this.docfields = frappe.meta.get_docfields(this.doctype, this.frm.docname);
		} else {
			// fields given in docfield
			this.docfields = this.df.fields;
		}

		this._apply_layout_child_overrides();
		this._apply_column_disp_overrides();
		this._apply_mask_overrides();

		this.docfields.forEach((df) => {
			this.fields_map[df.fieldname] = df;
		});
	}

	_apply_mask_overrides() {
		const masked_fields = frappe.get_meta(this.doctype)?.masked_fields || [];
		if (!masked_fields.length) return;

		// Shallow copy so the shared `frappe.meta` docfield is not mutated. Render masked
		// child fields as read-only Data so the grid shows the XXXXXXXX placeholder and the
		// cell can't be edited inline, matching the form view (layout.init_field).
		this.docfields = this.docfields.map((df) => {
			if (!masked_fields.includes(df.fieldname)) return df;
			return Object.assign({}, df, { read_only: 1, fieldtype: "Data" });
		});
	}

	_apply_column_disp_overrides() {
		const fieldnames = Object.keys(this.column_disp_overrides || {});
		if (!fieldnames.length) return;

		// Replace overridden fields with a shallow copy carrying the grid-local
		// `hidden` value. The base docfield comes from `frappe.meta` and is shared
		// across every grid of the same child doctype on this form, so it must not
		// be mutated in place.
		this.docfields = this.docfields.map((df) => {
			if (!(df.fieldname in this.column_disp_overrides)) return df;
			return Object.assign({}, df, { hidden: this.column_disp_overrides[df.fieldname] });
		});
	}

	_apply_layout_child_overrides() {
		const layout = this.frm?.doctype_layout;
		if (!layout?.child_tables?.length || !this.df?.fieldname) return;

		const table_fn = this.df.fieldname;
		const entry = layout.child_tables.find((r) => r.table_fieldname === table_fn);
		if (!entry?.child_layout) return;

		const child_layout = frappe.get_doc("DocType Layout", entry.child_layout);
		if (!child_layout?.fields?.length) return;

		const OVERRIDE_PROPS = [
			"hidden",
			"reqd",
			"read_only",
			"bold",
			"allow_in_quick_entry",
			"in_list_view",
			"in_standard_filter",
			"default",
			"description",
			"depends_on",
			"mandatory_depends_on",
			"read_only_depends_on",
		];
		const override_map = Object.fromEntries(child_layout.fields.map((f) => [f.fieldname, f]));

		this.docfields = this.docfields.map((df) => {
			const o = override_map[df.fieldname];
			if (!o) return df;
			const copy = Object.assign({}, df);
			if (o.label) copy.label = o.label;
			for (const prop of OVERRIDE_PROPS) {
				// Use truthy check so Check fields defaulting to 0 in the layout row
				// don't accidentally override the base field's value (e.g. in_list_view: 1).
				if (o[prop]) {
					copy[prop] = o[prop];
				}
			}
			return copy;
		});
	}

	refresh_row(docname) {
		this.grid_rows_by_docname[docname] && this.grid_rows_by_docname[docname].refresh();
	}

	make_sortable($rows) {
		this.grid_sortable = new Sortable($rows.get(0), {
			group: { name: this.df.fieldname },
			handle: ".sortable-handle",
			draggable: ".grid-row",
			animation: 100,
			filter: "li, a",
			onMove: (event) => {
				// don't move if editable
				if (!this.is_editable()) {
					return false;
				}
				// prevent drag behaviour if _sortable property is "false"
				let idx = $(event.dragged).closest(".grid-row").attr("data-idx");
				let doc = this.data[idx % this.grid_pagination.page_length];
				if (doc && doc._sortable === false) {
					return false;
				}
			},
			onUpdate: (event) => {
				let idx = $(event.item).closest(".grid-row").attr("data-idx") - 1;
				let doc = this.data[idx % this.grid_pagination.page_length];
				this.renumber_based_on_dom();
				this.frm &&
					this.frm.script_manager.trigger(
						this.df.fieldname + "_move",
						this.df.options,
						doc.name
					);
				this.refresh();
				this.frm && this.frm.dirty();
			},
		});

		this.frm && $(this.frm.wrapper).trigger("grid-make-sortable", [this.frm]);
	}

	get_data(filter_field) {
		let data = [];
		if (filter_field) {
			data = this.get_filtered_data();
		} else {
			data = this.frm
				? this.frm.doc[this.df.fieldname] || []
				: this.df.data || this.get_modal_data();
		}
		return data;
	}

	get_filtered_data() {
		let all_data = this.frm ? this.frm.doc[this.df.fieldname] : this.df.data;

		if (!all_data) return;

		for (const field in this.filter) {
			all_data = all_data.filter((data) => {
				let { df, value } = this.filter[field];
				return this.get_data_based_on_fieldtype(df, data, value.toLowerCase());
			});
		}

		return all_data;
	}

	get_data_based_on_fieldtype(df, data, value) {
		let fieldname = df.fieldname;
		let fieldtype = df.fieldtype;
		let fieldvalue = data[fieldname];

		if (fieldtype === "Check") {
			value = frappe.utils.string_to_boolean(value);
			return Boolean(fieldvalue) === value && data;
		} else if (fieldtype === "Sr No" && data.idx.toString().includes(value)) {
			return data;
		} else if (fieldtype === "Duration" && fieldvalue) {
			let formatted_duration = frappe.utils.get_formatted_duration(fieldvalue);

			if (formatted_duration.includes(value)) {
				return data;
			}
		} else if (fieldtype === "Barcode" && fieldvalue) {
			let barcode = fieldvalue.startsWith("<svg")
				? $(fieldvalue).attr("data-barcode-value")
				: fieldvalue;

			if (barcode.toLowerCase().includes(value)) {
				return data;
			}
		} else if (["Datetime", "Date"].includes(fieldtype) && fieldvalue) {
			let user_formatted_date = frappe.datetime.str_to_user(fieldvalue);

			if (user_formatted_date.includes(value)) {
				return data;
			}
		} else if (["Currency", "Float", "Int", "Percent", "Rating"].includes(fieldtype)) {
			let num = fieldvalue || 0;

			if (fieldtype === "Rating") {
				let out_of_rating = parseInt(df.options) || 5;
				num = num * out_of_rating;
			}

			if (num.toString().includes(value)) {
				return data;
			}
		} else if (fieldvalue && fieldvalue.toLowerCase().includes(value)) {
			return data;
		}
	}

	get_modal_data() {
		return this.df.get_data
			? this.df.get_data().filter((data) => {
					if (!this.deleted_docs || !this.deleted_docs.includes(data.name)) {
						return data;
					}
			  })
			: [];
	}

	set_column_disp(fieldname, show) {
		if (Array.isArray(fieldname)) {
			for (let field of fieldname) {
				this.update_docfield_property(field, "hidden", show ? 0 : 1);
				this.set_editable_grid_column_disp(field, show);
			}
		} else {
			this.get_docfield(fieldname).hidden = show ? 0 : 1;
			this.set_editable_grid_column_disp(fieldname, show);
		}

		this.debounced_refresh();
	}

	set_column_disp_in_list_view(fieldname, show) {
		// Show/hide a column in this grid's list view (the static, read-only row
		// rendering). Unlike `set_column_disp`, the change is kept as a grid-local
		// override and never mutates the shared meta docfield, so other grids of
		// the same child doctype on the same form are unaffected. The override is
		// applied to a grid-local docfield copy in `_apply_column_disp_overrides`
		// (called from `setup_fields`).
		const fieldnames = Array.isArray(fieldname) ? fieldname : [fieldname];
		for (let field of fieldnames) {
			this.column_disp_overrides[field] = show ? 0 : 1;
		}

		this._teardown_column_layout();
		this.debounced_refresh();
	}

	set_editable_grid_column_disp(fieldname, show) {
		//Hide columns for editable grids
		if (this.meta.editable_grid && this.grid_rows) {
			this.grid_rows.forEach((row) => {
				row.columns_list.forEach((column) => {
					//Hide the column specified
					if (column.df.fieldname == fieldname) {
						if (show) {
							column.df.hidden = false;

							//Show the static area and hide field area if it is not the editable row
							if (row != frappe.ui.form.editable_row) {
								if (
									row.should_show_button_in_idle_grid_cell &&
									row.should_show_button_in_idle_grid_cell(column)
								) {
									row.make_control(column);
									column.static_area.hide();
									column.field_area && column.field_area.toggle(true);
								} else {
									column.static_area.show();
									column.field_area && column.field_area.toggle(false);
								}
							}
							//Hide the static area and show field area if it is the editable row
							else {
								column.static_area.hide();
								column.field_area && column.field_area.toggle(true);

								//Format the editable column appropriately if it is now visible
								if (column.field) {
									column.field.refresh();
									if (column.field.$input)
										column.field.$input.toggleClass("input-sm", true);
								}
							}
						} else {
							column.df.hidden = true;
							column.static_area.hide();
						}
					}
				});
			});
		}

		this.refresh();
	}

	toggle_reqd(fieldname, reqd) {
		this.update_docfield_property(fieldname, "reqd", reqd);
		this.debounced_refresh();
	}

	toggle_enable(fieldname, enable) {
		this.update_docfield_property(fieldname, "read_only", enable ? 0 : 1);
		this.debounced_refresh();
	}

	toggle_display(fieldname, show) {
		this.update_docfield_property(fieldname, "hidden", show ? 0 : 1);
		this.debounced_refresh();
	}

	toggle_checkboxes(enable) {
		this.wrapper.find(".grid-row-check").prop("disabled", !enable);
	}

	get_docfield(fieldname) {
		return frappe.meta.get_docfield(
			this.doctype,
			fieldname,
			this.frm ? this.frm.docname : null
		);
	}

	get_row(key) {
		if (typeof key == "number") {
			if (key < 0) {
				return this.grid_rows[this.grid_rows.length + key];
			} else {
				return this.grid_rows[key];
			}
		} else {
			return this.grid_rows_by_docname[key];
		}
	}

	get_grid_row(key) {
		return this.get_row(key);
	}

	get_field(fieldname) {
		// Note: workaround for get_query
		if (!this.fieldinfo[fieldname]) this.fieldinfo[fieldname] = {};
		return this.fieldinfo[fieldname];
	}

	set_value(fieldname, value, doc) {
		if (this.display_status !== "None" && doc?.name && this.grid_rows_by_docname?.[doc.name]) {
			let grid_row = this.grid_rows_by_docname[doc.name];
			grid_row.refresh_field(fieldname, value);
			// re-evaluate depends_on of sibling columns that reference this field
			grid_row.refresh_dependency();
		}
	}

	setup_add_row() {
		this.wrapper.find(".grid-add-row").click(() => {
			this.add_new_row(null, null, true, null, true);
			this.set_focus_on_row();

			return false;
		});
	}

	add_new_row(idx, callback, show, copy_doc, go_to_last_page = false, go_to_first_page = false) {
		let cannot_add_rows = this.cannot_add_rows || (this.df && this.df.cannot_add_rows);
		if (this.is_editable() && !cannot_add_rows) {
			if (go_to_last_page) {
				this.grid_pagination.go_to_last_page_to_add_row();
			} else if (go_to_first_page) {
				this.grid_pagination.go_to_page(1);
			}

			if (this.frm) {
				var d = frappe.model.add_child(
					this.frm.doc,
					this.df.options,
					this.df.fieldname,
					idx
				);
				if (copy_doc) {
					d = this.duplicate_row(d, copy_doc);
				}
				d.__unedited = true;
				this.frm.script_manager.trigger(this.df.fieldname + "_add", d.doctype, d.name);
				this.refresh();
			} else {
				if (!this.df.data) {
					this.df.data = this.get_data() || [];
				}
				const defaults = this.docfields.reduce((acc, d) => {
					acc[d.fieldname] = d.default;
					return acc;
				}, {});

				const row_idx = this.df.data.length + 1;
				this.df.data.push({ idx: row_idx, __islocal: true, ...defaults });
				this.df.on_add_row && this.df.on_add_row(row_idx);
				this.refresh();
			}

			if (show) {
				if (idx) {
					// always open inserted rows
					this.wrapper
						.find("[data-idx='" + idx + "']")
						.data("grid_row")
						.toggle_view(true, callback);
				} else {
					if (!this.allow_on_grid_editing()) {
						// open last row only if on-grid-editing is disabled
						this.wrapper
							.find(".grid-row:last")
							.data("grid_row")
							.toggle_view(true, callback);
					}
				}
			}

			return d;
		}
	}

	renumber_based_on_dom() {
		// renumber based on dom
		let $rows = $(this.parent).find(".rows");

		$rows.find(".grid-row").each((i, item) => {
			let $item = $(item);
			let index =
				(this.grid_pagination.page_index - 1) * this.grid_pagination.page_length + i;
			let d = this.grid_rows_by_docname[$item.attr("data-name")].doc;
			d.idx = index + 1;
			$item.attr("data-idx", d.idx);

			if (this.frm) this.frm.doc[this.df.fieldname][index] = d;
			this.data[index] = d;
			this.grid_rows[index] = this.grid_rows_by_docname[d.name];
		});
	}

	duplicate_row(d, copy_doc) {
		const skip = [
			"creation",
			"modified",
			"modified_by",
			"idx",
			"owner",
			"parent",
			"doctype",
			"name",
			"parentfield",
		];
		for (const [key, value] of Object.entries(copy_doc)) {
			if (!skip.includes(key)) d[key] = value;
		}
		return d;
	}

	bulk_edit_rows() {
		if (!this.meta?.allow_bulk_edit) return;

		const selected_children = this.get_selected_children();
		if (!selected_children.length) {
			frappe.show_alert({ message: __("No rows selected"), indicator: "orange" });
			return;
		}

		const is_field_editable = (field_doc) => {
			const parent_docstatus = this.frm?.doc?.docstatus;
			const is_submitted_or_cancelled = [1, 2].includes(parent_docstatus);

			return (
				field_doc.fieldname &&
				frappe.model.is_value_type(field_doc) &&
				field_doc.fieldtype !== "Read Only" &&
				!field_doc.hidden &&
				!field_doc.read_only &&
				!field_doc.is_virtual &&
				(!is_submitted_or_cancelled || field_doc.allow_on_submit)
			);
		};

		const editable_fields = (this.docfields || []).filter((field_doc) =>
			is_field_editable(field_doc)
		);
		if (!editable_fields.length) {
			frappe.msgprint(__("No editable fields available for bulk edit."));
			return;
		}

		const grid = this;

		const field_mappings = {};
		editable_fields.forEach((field_doc) => {
			const field_key = `${field_doc.label}`;
			field_mappings[field_key] = Object.assign({}, field_doc);
		});

		const field_options = Object.keys(field_mappings).sort((a, b) =>
			__(cstr(field_mappings[a].label)).localeCompare(cstr(__(field_mappings[b].label)))
		);
		const field_autocomplete_options = field_options.map((key) => ({
			label: __(cstr(field_mappings[key].label)),
			value: key,
		}));
		const status_regex = /status/i;
		const default_field =
			field_options.find((value) => status_regex.test(value)) ||
			field_options.find((value) => field_mappings[value]?.fieldtype === "Select");

		// One child row drives Link get_query(cb, doc, cdt, cdn) / locals lookups in bulk-edit dialog.
		// Multiple rows selected may diverge — filters follow the first selected row only.
		const bulk_edit_reference_row = selected_children[0];

		const dialog = new frappe.ui.Dialog({
			title: __("Bulk Edit"),
			...(bulk_edit_reference_row && {
				frm: this.frm,
				doc: bulk_edit_reference_row,
				doctype: bulk_edit_reference_row.doctype,
			}),
			fields: [
				{
					fieldtype: "Autocomplete",
					options: field_autocomplete_options,
					max_items: Infinity,
					default: default_field,
					label: __("Field"),
					fieldname: "field",
					reqd: 1,
					onchange: () => {
						set_value_field(dialog);
					},
				},
				{
					fieldtype: "Data",
					label: __("Value"),
					fieldname: "value",
					onchange() {
						show_help_text();
					},
				},
			],
			primary_action: ({ value }) => {
				const selected_field = field_mappings[dialog.get_value("field")];
				const { fieldname } = selected_field;
				dialog.disable_primary_action();

				const update_value = value || null;
				const tasks = selected_children.map((doc) =>
					frappe.model.set_value(doc.doctype, doc.name, fieldname, update_value)
				);

				Promise.all(tasks).then(() => {
					this.frm && this.frm.dirty();
					this.refresh();
					dialog.hide();
					const row_label = selected_children.length === 1 ? __("row") : __("rows");
					frappe.show_alert(
						__("Updated {0} selected {1}. Save the form to keep changes.", [
							selected_children.length,
							row_label,
						])
					);
				});
			},
			primary_action_label: __("Update {0} rows", [selected_children.length]),
		});

		if (default_field) set_value_field(dialog);
		show_help_text();

		function set_value_field(dialogObj) {
			const field_value = dialogObj.get_value("field");
			if (!field_value || !field_mappings[field_value]) return;
			const new_df = Object.assign({}, field_mappings[field_value]);
			if (
				new_df.label?.match(status_regex) &&
				new_df.fieldtype === "Select" &&
				!new_df.default
			) {
				let options = [];
				if (typeof new_df.options === "string") {
					options = new_df.options.split("\n");
				}
				new_df.default = options[0] || options[1];
			}
			new_df.label = __("Value");
			new_df.onchange = show_help_text;
			delete new_df.depends_on;

			const grid_field = grid.get_field(new_df.fieldname);
			if (grid_field?.get_query) {
				new_df.get_query = grid_field.get_query;
			}

			dialogObj.replace_field("value", new_df);
			// replace_field does not re-run attach_doc; Link needs docname + doctype for set_query third arg.
			if (bulk_edit_reference_row) {
				dialogObj.attach_doc_and_docfields(true);
			}
			show_help_text();
		}

		function show_help_text() {
			if (dialog.get_primary_btn().is(":focus, :active")) return;

			let value = dialog.get_value("value");
			if (value == null || value === "") {
				dialog.set_df_property(
					"value",
					"description",
					__("You have not entered a value. The field will be set to empty.")
				);
			} else {
				dialog.set_df_property("value", "description", "");
			}
		}

		dialog.refresh();
		dialog.show();
	}

	set_focus_on_row(idx) {
		if (!idx && idx !== 0) {
			idx = this.grid_rows.length - 1;
		}

		setTimeout(() => {
			this.grid_rows[idx].toggle_editable_row(true);
			this.grid_rows[idx].row
				.find('input[type="Text"],textarea,select')
				.filter(":visible:first")
				.focus();
		}, 100);
	}

	setup_visible_columns() {
		if (this.visible_columns && this.visible_columns.length > 0) return;

		this.user_defined_columns = [];
		this.setup_user_defined_columns();
		const use_user_columns = this.user_defined_columns.length > 0;
		const fields = use_user_columns
			? this.user_defined_columns
			: this.editable_fields || this.docfields;

		this.visible_columns = [];

		for (const _df of fields) {
			// get docfield if from fieldname
			let df = use_user_columns ? _df : this.fields_map[_df.fieldname];

			if (
				df &&
				!df.hidden &&
				(this.editable_fields || df.in_list_view) &&
				((this.frm && this.frm.get_perm(df.permlevel, "read")) || !this.frm) &&
				!frappe.model.layout_fields.includes(df.fieldtype)
			) {
				// attach formatter on refresh
				if (
					df.fieldtype == "Link" &&
					!df.formatter &&
					df.parent &&
					frappe.meta.docfield_map[df.parent]
				) {
					const docfield = frappe.meta.docfield_map[df.parent][df.fieldname];
					if (docfield && docfield.formatter) {
						df.formatter = docfield.formatter;
					}
				}

				this.visible_columns.push([df, this.get_column_width(df)]);
			}
		}

		// Compute sticky left-offsets once from the final column list.
		// 71 = row-check (31px) + row-index (40px) — the two always-visible sticky cols.
		this.sticky_offsets = {};
		let sticky_sum = 71;
		for (let [df, width] of this.visible_columns) {
			if (df.sticky) {
				this.sticky_offsets[df.fieldname] = sticky_sum;
				sticky_sum += width;
			}
		}
	}

	clamp_column_width(width) {
		return Math.max(GRID_MIN_COLUMN_WIDTH, Math.min(GRID_MAX_COLUMN_WIDTH, cint(width)));
	}

	// Precedence: per-user width (px) > docfield `columns` (migrated) > fieldtype default.
	get_column_width(df) {
		const width =
			df.width ||
			LEGACY_COLSIZE_TO_PX[df.columns] ||
			DEFAULT_COLUMN_WIDTHS[df.fieldtype] ||
			140;
		return this.clamp_column_width(width);
	}

	get_sticky_offset(fieldname) {
		return this.sticky_offsets[fieldname] ?? 71;
	}

	setup_user_defined_columns() {
		if (!this.frm) return;

		let user_settings = frappe.get_user_settings(this.frm.doctype, "GridView");
		if (user_settings && user_settings[this.doctype] && user_settings[this.doctype].length) {
			this.user_defined_columns = user_settings[this.doctype]
				.map((row) => {
					let column =
						this.docfields?.find((d) => d.fieldname === row.fieldname) ||
						frappe.meta.get_docfield(this.doctype, row.fieldname);

					if (column) {
						column.in_list_view = 1;
						// migrate legacy `columns` (1-12) to px
						column.width = cint(row.width) || LEGACY_COLSIZE_TO_PX[row.columns];
						column.sticky = row.sticky;
						return column;
					}
				})
				.filter(Boolean);
		}
	}

	is_editable() {
		return this.display_status == "Write" && !this.static_rows;
	}

	is_sortable() {
		return this.sortable_status || this.is_editable();
	}

	only_sortable(status) {
		if (status === undefined ? true : status) {
			this.sortable_status = true;
			this.static_rows = true;
		}
	}

	set_multiple_add(link, qty) {
		if (this.multiple_set) return;

		const link_field = frappe.meta.get_docfield(this.df.options, link);
		const btn = $(this.wrapper).find(".grid-add-multiple-rows");

		// show button
		btn.removeClass("hidden");

		// open link selector on click
		btn.on("click", () => {
			new frappe.ui.form.LinkSelector({
				doctype: link_field.options,
				fieldname: link,
				qty_fieldname: qty,
				get_query: link_field.get_query,
				target: this,
				txt: "",
			});
			this.grid_pagination.go_to_last_page_to_add_row();
			return false;
		});
		this.multiple_set = true;
	}

	setup_allow_bulk_edit() {
		let me = this;
		if (this.frm && this.frm.get_docfield(this.df.fieldname)?.allow_bulk_edit) {
			// download
			this.setup_download();

			const value_formatter_map = {
				Date: (val) => (val ? frappe.datetime.user_to_str(val) : val),
				Int: (val) => cint(val),
				Check: (val) => cint(val),
				Float: (val) => flt(val),
				Currency: (val) => flt(val),
			};

			// upload
			frappe.flags.no_socketio = true;
			$(this.wrapper)
				.find(".grid-upload")
				.removeClass("hidden")
				.on("click", () => {
					new frappe.ui.FileUploader({
						as_dataurl: true,
						allow_multiple: false,
						restrictions: {
							allowed_file_types: [".csv"],
						},
						on_success(file) {
							const data = frappe.utils.csv_to_array(
								frappe.utils.get_decoded_string(file.dataurl)
							);
							if (cint(data.length) - BULK_EDIT_CSV_HEADER_ROWS > 5000) {
								frappe.throw(__("Cannot import table with more than 5000 rows."));
							}
							const fieldnames = data[2];
							me.frm.clear_table(me.df.fieldname);
							data.forEach((row, i) => {
								if (i < BULK_EDIT_CSV_HEADER_ROWS) return;
								if (!row.some((v) => v)) return;
								const d = me.frm.add_child(me.df.fieldname);
								row.forEach((value, ci) => {
									const fieldname = fieldnames[ci];
									const df = frappe.meta.get_docfield(me.df.options, fieldname);
									if (df) {
										d[fieldname] = value_formatter_map[df.fieldtype]
											? value_formatter_map[df.fieldtype](value)
											: value;
									}
								});
							});

							me.frm.refresh_field(me.df.fieldname);
							frappe.msgprint({
								message: __("Table updated"),
								title: __("Success"),
								indicator: "green",
							});
						},
					});
					return false;
				});
		}
	}

	setup_download() {
		let title = this.df.label || frappe.model.unscrub(this.df.fieldname);
		$(this.wrapper)
			.find(".grid-download")
			.removeClass("hidden")
			.on("click", () => {
				const data = [
					[__("Bulk Edit {0}", [title])],
					[],
					[],
					[],
					[__("The CSV format is case sensitive")],
					[__("Do not edit headers which are preset in the template")],
					["------"],
				];
				const docfields = [];
				frappe.get_meta(this.df.options).fields.forEach((df) => {
					if (frappe.model.is_value_type(df.fieldtype)) {
						data[1].push(df.label);
						data[2].push(df.fieldname);
						let description = (df.description || "") + " ";
						if (df.fieldtype === "Date")
							description += frappe.boot.sysdefaults.date_format;
						data[3].push(description);
						docfields.push(df);
					}
				});

				(this.frm.doc[this.df.fieldname] || []).forEach((d) => {
					const row = data[2].map((fieldname, i) => {
						let value = d[fieldname];
						if (docfields[i].fieldtype === "Date" && value) {
							value = frappe.datetime.str_to_user(value);
						}
						return value || "";
					});
					data.push(row);
				});

				frappe.tools.downloadify(data, null, title);
				return false;
			});
	}

	add_custom_button(label, click, position = "bottom") {
		// add / unhide a custom button
		const $wrapper = position === "top" ? this.grid_custom_buttons : this.grid_buttons;
		let $btn = this.custom_buttons[label];
		if (!$btn) {
			$btn = $(`<button type="button" class="btn btn-secondary btn-xs btn-custom">`)
				.html(__(label))
				.prependTo($wrapper)
				.on("click", click);
			this.custom_buttons[label] = $btn;
		} else {
			$btn.removeClass("hidden");
		}
		return $btn;
	}

	clear_custom_buttons() {
		// hide all custom buttons
		this.grid_buttons.find(".btn-custom").addClass("hidden");
	}

	update_docfield_property(fieldname, property, value) {
		// update the docfield of each row
		if (!this.grid_rows) {
			return;
		}

		for (let row of this.grid_rows) {
			if (!row) continue;

			let docfield = row.docfields?.find((d) => d.fieldname === fieldname);
			if (docfield) {
				docfield[property] = value;
			} else {
				throw `field ${fieldname} not found`;
			}
		}

		// update the parent too (for new rows)
		this.docfields.find((d) => d.fieldname === fieldname)[property] = value;

		if (this.user_defined_columns && this.user_defined_columns.length > 0) {
			let field = this.user_defined_columns.find((d) => d.fieldname === fieldname);
			if (field && Object.keys(field).includes(property)) {
				field[property] = value;
			}
		}

		this.debounced_refresh();
	}

	get_current_row(target) {
		let current_row = null;
		for (let i = 0; i < this.grid_rows.length; i++) {
			if (this.grid_rows[i]?.wrapper.get(0).contains(target)) {
				current_row = i;
			}
		}
		return current_row;
	}
}
