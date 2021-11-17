export default class GridRowForm {
	constructor(opts) {
		$.extend(this, opts);
		this.wrapper = $('<div class="form-in-grid"></div>')
			.appendTo(this.row.wrapper);

	}
	render() {
		var me = this;
		this.make_form();
		this.form_area.empty();
		frappe.utils.scroll_to(0, false, 0, this.wrapper.find('.grid-form-body'));

		this.layout = new frappe.ui.form.Layout({
			fields: this.row.docfields,
			body: this.form_area,
			no_submit_on_enter: true,
			frm: this.row.frm,
			grid: this.row.grid,
			grid_row: this.row,
			grid_row_form: this,
		});
		this.layout.make();

		this.fields = this.layout.fields;
		this.fields_dict = this.layout.fields_dict;

		this.layout.refresh(this.row.doc);

		// copy get_query to fields
		for(var fieldname in (this.row.grid.fieldinfo || {})) {
			var fi = this.row.grid.fieldinfo[fieldname];
			$.extend(me.fields_dict[fieldname], fi);
		}

		this.toggle_add_delete_button_display(this.wrapper);

		this.row.grid.open_grid_row = this;

		this.set_focus();
	}
	make_form() {
		if(!this.form_area) {
			let template = `<div class="grid-form-heading">
				<div class="toolbar grid-header-toolbar">
					<span class="panel-title">
						${ __("Editing Row") } #<span class="grid-form-row-index"></span></span>
					<span class="row-actions">
						<button class="btn btn-secondary btn-sm pull-right grid-collapse-row">
							${frappe.utils.icon('down')}
						</button>
						<button class="btn btn-secondary btn-sm pull-right grid-move-row hidden-xs">
							${ __("Move") }</button>
						<button class="btn btn-secondary btn-sm pull-right grid-duplicate-row hidden-xs">
							${frappe.utils.icon('duplicate')}
							${ __("Duplicate") }
						</button>
						<button class="btn btn-secondary btn-sm pull-right grid-insert-row hidden-xs">
							${ __("Insert Above") }</button>
						<button class="btn btn-secondary btn-sm pull-right grid-insert-row-below hidden-xs">
							${ __("Insert Below") }</button>
						<button class="btn btn-danger btn-sm pull-right grid-delete-row">
							${frappe.utils.icon('delete')}
						</button>
					</span>
				</div>
			</div>
			<div class="grid-form-body">
				<div class="form-area"></div>
				<div class="grid-footer-toolbar hidden-xs flex justify-between">
					<div class="grid-shortcuts">
						<span> ${frappe.utils.icon("keyboard", "md")} </span>
						<span class="text-medium"> ${ __("Shortcuts") }: </span>
						<kbd>${ __("Ctrl + Up") }</kbd> . <kbd>${ __("Ctrl + Down") }</kbd> . <kbd>${ __("ESC") }</kbd>
					</div>
					<button class="btn btn-secondary btn-sm pull-right grid-append-row">
						${ __("Insert Below") }
					</button>
				</div>
			</div>`;

			$(template).appendTo(this.wrapper);
			this.form_area = this.wrapper.find(".form-area");
			this.row.set_row_index();
			this.set_form_events();
		}
	}
	set_form_events() {
		var me = this;
		this.wrapper.find(".grid-delete-row")
			.on('click', function() {
				me.row.remove(); return false;
			});
		this.wrapper.find(".grid-insert-row")
			.on('click', function() {
				me.row.insert(true); return false;
			});
		this.wrapper.find(".grid-insert-row-below")
			.on('click', function() {
				me.row.insert(true, true); return false;
			});
		this.wrapper.find(".grid-duplicate-row")
			.on('click', function() {
				me.row.insert(true, true, true); return false;
			});
		this.wrapper.find(".grid-move-row")
			.on('click', function() {
				me.row.move(); return false;
			});
		this.wrapper.find(".grid-append-row")
			.on('click', function() {
				me.row.toggle_view(false);
				me.row.grid.add_new_row(me.row.doc.idx+1, null, true);
				return false;
			});
		this.wrapper.find(".grid-form-heading, .grid-footer-toolbar").on("click", function() {
			me.row.toggle_view();
			return false;
		});
	}
	toggle_add_delete_button_display($parent) {
		$parent.find(".row-actions, .grid-append-row")
			.toggle(this.row.grid.is_editable());
	}
	refresh_field(fieldname) {
		const field = this.fields_dict[fieldname];
		if (!field) return;

		field.docname = this.row.doc.name;
		field.refresh();
		this.layout && this.layout.refresh_dependency();
	}
	set_focus() {
		// wait for animation and then focus on the first row
		var me = this;
		setTimeout(function() {
			if(me.row.frm && me.row.frm.doc.docstatus===0 || !me.row.frm) {
				var first = me.form_area.find("input:first");
				if(first.length && !in_list(["Date", "Datetime", "Time"], first.attr("data-fieldtype"))) {
					try {
						first.get(0).focus();
					} catch(e) {
						//
					}
				}
			}
		}, 500);
	}
}
