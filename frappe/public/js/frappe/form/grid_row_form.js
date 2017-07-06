frappe.ui.form.GridRowForm = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.wrapper = $('<div class="form-in-grid"></div>')
			.appendTo(this.row.wrapper);

	},
	render: function() {
		var me = this;
		this.make_form();
		this.form_area.empty();

		this.layout = new frappe.ui.form.Layout({
			fields: this.row.docfields,
			body: this.form_area,
			no_submit_on_enter: true,
			frm: this.row.frm,
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
	},
	make_form: function() {
		if(!this.form_area) {
			$(frappe.render_template("grid_form", {grid:this})).appendTo(this.wrapper);
			this.form_area = this.wrapper.find(".form-area");
			this.row.set_row_index();
			this.set_form_events();
		}
	},
	set_form_events: function() {
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
	},
	toggle_add_delete_button_display: function($parent) {
		$parent.find(".grid-header-toolbar .btn, .grid-footer-toolbar .btn")
			.toggle(this.row.grid.is_editable());
	},
	refresh_field: function(fieldname) {
		if(this.fields_dict[fieldname]) {
			this.fields_dict[fieldname].refresh();
			this.layout && this.layout.refresh_dependency();
		}
	},
	set_focus: function() {
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
	},
});
