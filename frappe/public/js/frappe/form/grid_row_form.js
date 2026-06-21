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
		this.wrapper.find(".grid-sidebar-body").scrollTop(0);
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
				<div class="grid-sidebar-header-actions">
					<button class="btn btn-xs btn-default grid-delete-row" title="${__("Delete row")}">
						${frappe.utils.icon("trash-2", "sm")}
					</button>
					<button class="btn btn-xs btn-default grid-sidebar-close" title="${__("Close")}">
						${frappe.utils.icon("x", "sm")}
					</button>
				</div>
			</div>
			<div class="grid-sidebar-title">
				<span class="grid-sidebar-docname"></span>
			</div>
			<div class="grid-sidebar-actions">
				<button class="btn btn-secondary btn-xs grid-insert-row hidden-xs">
					${__("Insert above")}
				</button>
				<button class="btn btn-secondary btn-xs grid-insert-row-below hidden-xs">
					${__("Insert below")}
				</button>
				<button class="btn btn-secondary btn-xs grid-duplicate-row hidden-xs">
					${__("Duplicate")}
				</button>
				<button class="btn btn-secondary btn-xs grid-move-row hidden-xs">
					${__("Move")}
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

		$(document).on("mousedown.grid-sidebar", (e) => {
			const $target = $(e.target);
			if ($target.closest(".grid-row-sidebar").length) return;
			// Don't close when interacting with floating UI (dropdowns, pickers, dialogs).
			if (
				$target.closest(
					".dropdown-menu, .modal, .awesomplete, .picker-container, .datepicker"
				).length
			)
				return;
			this.row.toggle_view(false);
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
		const cannot_add = this.row.grid.cannot_add_rows || this.row.grid.df?.cannot_add_rows;
		const cannot_delete = this.row.grid.df?.cannot_delete_rows;

		$parent.find(".grid-sidebar-actions").toggle(editable && !cannot_add);
		$parent.find(".grid-delete-row").toggle(editable && !cannot_delete);
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
	navigate_to(new_row) {
		// Transfer sidebar ownership to new_row without closing/reopening it.
		// The slide-in transition only fires on initial open; switching rows is instant + content fade.
		this.row.wrapper.removeClass("grid-row-open");
		this.row.grid_form = null;

		this.row = new_row;
		new_row.grid_form = this;
		new_row.wrapper.addClass("grid-row-open");
		if (cur_frm) cur_frm.cur_grid = new_row;

		if (
			!frappe.dom.is_element_in_viewport(new_row.wrapper) &&
			!frappe.dom.is_element_in_modal(new_row.wrapper)
		) {
			frappe.utils.scroll_to(new_row.wrapper, true, -15);
		}

		const $content = this.wrapper.find(".grid-sidebar-title, .grid-sidebar-body");
		$content.css("opacity", 0);
		this.render();
		$content.animate({ opacity: 1 }, 120);

		if (new_row.frm) {
			new_row.frm.script_manager.trigger(new_row.doc.parentfield + "_on_form_rendered");
			new_row.frm.script_manager.trigger(
				"form_render",
				new_row.doc.doctype,
				new_row.doc.name
			);
		}
	}
	destroy() {
		$(document).off(".grid-sidebar");
		this.wrapper.remove();
	}
}
