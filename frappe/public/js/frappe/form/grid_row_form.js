export default class GridRowForm {
	constructor(opts) {
		$.extend(this, opts);
		this.wrapper = $('<div class="grid-row-sidebar"></div>').appendTo(
			$(this.row.grid.wrapper).closest(".form-page, .frappe-client, body").first()
		);
	}
	render() {
		this.make_form();
		this.form_area.empty();

		this.layout = new frappe.ui.form.Layout({
			fields: this.row.docfields,
			body: this.form_area,
			no_submit_on_enter: true,
			frm: this.row.frm,
			grid: this.row.grid,
			grid_row: this.row,
			grid_row_form: this,
			is_child_table: true,
			doctype: this.row.grid.doctype,
		});
		this.layout.make();

		this.fields = this.layout.fields;
		this.fields_dict = this.layout.fields_dict;

		this.layout.refresh(this.row.doc);

		for (const fieldname in this.row.grid.fieldinfo || {}) {
			const fi = this.row.grid.fieldinfo[fieldname];
			$.extend(this.fields_dict[fieldname], fi);
		}

		this.toggle_add_delete_button_display(this.wrapper);
		this.update_nav_state();
		this.row.grid.open_grid_row = this;
		this.set_focus();
	}
	make_form() {
		if (this.form_area) return;

		const template = `
			<div class="grid-sidebar-header">
				<div class="grid-sidebar-row-nav">
					<span class="grid-sidebar-row-label">
						${__("ROW")}
					</span>
					<button class="btn btn-xs btn-default grid-sidebar-prev" title="${__("Previous row")}">
						${frappe.utils.icon("up-arrow", "xs")}
					</button>
					<span class="grid-sidebar-row-index"></span>
					<button class="btn btn-xs btn-default grid-sidebar-next" title="${__("Next row")}">
						${frappe.utils.icon("down-arrow", "xs")}
					</button>
				</div>
				<button class="btn btn-xs btn-default grid-sidebar-close" title="${__("Close")}">
					${frappe.utils.icon("close", "sm")}
				</button>
			</div>
			<div class="grid-sidebar-title">
				<span class="grid-sidebar-docname"></span>
			</div>
			<div class="grid-sidebar-actions">
				<button class="btn btn-secondary btn-sm grid-insert-row hidden-xs">
					${frappe.utils.icon("arrow-up", "xs")} ${__("Insert above")}
				</button>
				<button class="btn btn-secondary btn-sm grid-insert-row-below hidden-xs">
					${frappe.utils.icon("arrow-down", "xs")} ${__("Insert below")}
				</button>
				<button class="btn btn-secondary btn-sm grid-duplicate-row hidden-xs">
					${frappe.utils.icon("duplicate", "xs")} ${__("Duplicate")}
				</button>
				<button class="btn btn-secondary btn-sm grid-move-row hidden-xs">
					${__("Move")}
				</button>
				<button class="btn btn-danger btn-sm grid-delete-row">
					${frappe.utils.icon("delete", "xs")} ${__("Delete")}
				</button>
			</div>
			<div class="grid-sidebar-body">
				<div class="form-area"></div>
			</div>`;

		$(template).appendTo(this.wrapper);
		this.form_area = this.wrapper.find(".form-area");
		this.row.set_row_index();
		this.set_form_events();
	}
	set_form_events() {
		this.wrapper.find(".grid-sidebar-close").on("click", () => {
			this.row.toggle_view(false);
		});
		this.wrapper.find(".grid-sidebar-prev").on("click", () => {
			this.row.open_prev();
		});
		this.wrapper.find(".grid-sidebar-next").on("click", () => {
			this.row.open_next();
		});
		this.wrapper.find(".grid-delete-row").on("click", () => {
			this.row.remove();
		});
		this.wrapper.find(".grid-insert-row").on("click", () => {
			this.row.insert(true);
		});
		this.wrapper.find(".grid-insert-row-below").on("click", () => {
			this.row.insert(true, true);
		});
		this.wrapper.find(".grid-duplicate-row").on("click", () => {
			this.row.insert(true, true, true);
		});
		this.wrapper.find(".grid-move-row").on("click", () => {
			this.row.move();
		});

		$(document).on("keydown.grid-sidebar", (e) => {
			if (e.key === "Escape") this.row.toggle_view(false);
		});
	}
	update_nav_state() {
		const idx = this.row.doc.idx;
		const total = this.row.grid.data.length;

		this.wrapper.find(".grid-sidebar-row-index").text(`${idx} / ${total}`);
		this.wrapper.find(".grid-sidebar-prev").toggleClass("disabled", !this.row.has_prev());
		this.wrapper.find(".grid-sidebar-next").toggleClass("disabled", !this.row.has_next());

		// update title from first visible column value
		const first_col = this.row.grid.visible_columns?.[0]?.[0];
		const title = first_col && this.row.doc[first_col.fieldname];
		this.wrapper.find(".grid-sidebar-docname").text(title || "");
		this.wrapper.find(".grid-sidebar-title").toggle(!!title);
	}
	toggle_add_delete_button_display($parent) {
		const editable = this.row.grid.is_editable();
		$parent.find(".grid-sidebar-actions").toggle(editable);
		const cannot_add = this.row.grid.cannot_add_rows || this.row.grid.df?.cannot_add_rows;
		$parent
			.find(".grid-insert-row, .grid-insert-row-below, .grid-duplicate-row")
			.toggle(!cannot_add);
		$parent.find(".grid-delete-row").toggle(!this.row.grid.df?.cannot_delete_rows);
	}
	refresh_field(fieldname) {
		const field = this.fields_dict[fieldname];
		if (!field) return;
		field.docname = this.row.doc.name;
		field.refresh();
		this.layout && this.layout.refresh_dependency();
	}
	set_active_tab(tab) {
		this.active_tab = tab;
		let in_tab = false;
		for (const df of this.layout.fields) {
			const field = this.fields_dict[df.fieldname];
			if (df?.fieldtype === "Tab Break") {
				in_tab = df === tab?.df;
			} else if (typeof field?.on_section_collapse === "function") {
				field.on_section_collapse(!in_tab);
			}
		}
	}
	set_focus() {
		setTimeout(() => {
			if ((this.row.frm && this.row.frm.doc.docstatus === 0) || !this.row.frm) {
				const first = this.form_area.find("input:first");
				if (
					first.length &&
					!["Date", "Datetime", "Time"].includes(first.attr("data-fieldtype"))
				) {
					try {
						first.get(0).focus();
					} catch (e) {
						// ignore
					}
				}
			}
		}, 200);
	}
	destroy() {
		$(document).off("keydown.grid-sidebar");
		this.wrapper.remove();
	}
}
