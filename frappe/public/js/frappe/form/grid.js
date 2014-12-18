// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Grid = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.fieldinfo = {};
		this.doctype = this.df.options;
		this.template = null;
		if(this.frm.meta.__form_grid_templates
			&& this.frm.meta.__form_grid_templates[this.df.fieldname]) {
				this.template = this.frm.meta.__form_grid_templates[this.df.fieldname];
		}
		this.is_grid = true;
	},
	make: function() {
		var me = this;

		this.wrapper = $('<div>\
		<div class="form-grid">\
			<div class="grid-heading-row"></div>\
			<div class="grid-body">\
				<div class="rows"></div>\
				<div class="grid-empty text-center hide">'+__("No Data")+'</div>\
				<div class="small grid-footer text-center">\
					<a href="#" class="grid-add-row" style="margin-left: 10px;">+ '
						+__("Add new row")+'.</a>\
					<a href="#" class="grid-add-multiple-rows hide" style="margin-left: 10px;">+ '
						+__("Add multiple rows")+'.</a>\
					<div class="clearfix"></div>\
				</div>\
			</div>\
		</div>\
		</div>')
			.appendTo(this.parent)
			.attr("data-fieldname", this.df.fieldname);

		$(this.wrapper).find(".grid-add-row").click(function() {
			me.add_new_row(null, null, true);
			return false;
		})

	},
	make_head: function() {
		// labels
		this.header_row = new frappe.ui.form.GridRow({
			parent: $(this.parent).find(".grid-heading-row"),
			parent_df: this.df,
			docfields: this.docfields,
			frm: this.frm,
			grid: this
		});
	},
	refresh: function(force) {
		!this.wrapper && this.make();
		var me = this,
			$rows = $(me.parent).find(".rows"),
			data = this.get_data();

		this.docfields = frappe.meta.get_docfields(this.doctype, this.frm.docname);
		this.display_status = frappe.perm.get_field_display_status(this.df, this.frm.doc,
			this.perm);

		if(this.display_status==="None") return;

		if(!force && this.data_rows_are_same(data)) {
			// soft refresh
			this.header_row && this.header_row.refresh();
			for(var i in this.grid_rows) {
				this.grid_rows[i].refresh();
			}
		} else {
			// redraw
			var _scroll_y = window.scrollY;
			this.wrapper.find(".grid-row").remove();
			this.make_head();
			this.grid_rows = [];
			this.grid_rows_by_docname = {};
			for(var ri in data) {
				var d = data[ri];
				var grid_row = new frappe.ui.form.GridRow({
					parent: $rows,
					parent_df: this.df,
					docfields: this.docfields,
					doc: d,
					frm: this.frm,
					grid: this
				});
				this.grid_rows.push(grid_row)
				this.grid_rows_by_docname[d.name] = grid_row;
			}

			this.wrapper.find(".grid-empty").toggleClass("hide", !!data.length);

			if(this.is_editable()) {
				this.wrapper.find(".grid-footer").toggle(true);
				this.wrapper.find(".grid-add-row, .grid-add-multiple-rows").toggle(!this.cannot_add_rows);
				this.make_sortable($rows);
			} else {
				this.wrapper.find(".grid-footer").toggle(false);
			}

			this.last_display_status = this.display_status;
			this.last_docname = this.frm.docname;
			scroll(0, _scroll_y);
		}
	},
	refresh_row: function(docname) {
		this.grid_rows_by_docname[docname] &&
			this.grid_rows_by_docname[docname].refresh();
	},
	data_rows_are_same: function(data) {
		if(this.grid_rows) {
			var same = data.length==this.grid_rows.length
				&& this.display_status==this.last_display_status
				&& this.frm.docname==this.last_docname
				&& !$.map(this.grid_rows, function(g, i) {
					return (g.doc && g.doc.name==data[i].name) ? null : true;
				}).length;

			return same;
		}
	},
	make_sortable: function($rows) {
		var me =this;
		$rows.sortable({
			handle: ".data-row, .grid-form-heading",
			helper: 'clone',
			update: function(event, ui) {
				me.frm.doc[me.df.fieldname] = [];
				$rows.find(".grid-row").each(function(i, item) {
					var doc = $(item).data("doc");
					doc.idx = i + 1;
					$(this).find(".row-index").html(i + 1);
					me.frm.doc[me.df.fieldname].push(doc);
				});
				me.frm.dirty();
			}
		});
	},
	get_data: function() {
		var data = this.frm.doc[this.df.fieldname] || [];
		data.sort(function(a, b) { return a.idx - b.idx});
		return data;
	},
	set_column_disp: function(fieldname, show) {
		if($.isArray(fieldname)) {
			var me = this;
			$.each(fieldname, function(i, fname) {
				frappe.meta.get_docfield(me.doctype, fname, me.frm.docname).hidden = show ? 0 : 1;
			});
		} else {
			frappe.meta.get_docfield(this.doctype, fieldname, this.frm.docname).hidden = show ? 0 : 1;
		}

		this.refresh(true);
	},
	toggle_reqd: function(fieldname, reqd) {
		frappe.meta.get_docfield(this.doctype, fieldname, this.frm.docname).reqd = reqd;
		this.refresh();
	},
	get_field: function(fieldname) {
		// Note: workaround for get_query
		if(!this.fieldinfo[fieldname])
			this.fieldinfo[fieldname] = {
			}
		return this.fieldinfo[fieldname];
	},
	set_value: function(fieldname, value, doc) {
		if(this.display_status!=="None")
			this.grid_rows_by_docname[doc.name].refresh_field(fieldname);
	},
	add_new_row: function(idx, callback, show) {
		if(this.is_editable()) {
			var d = frappe.model.add_child(this.frm.doc, this.df.options, this.df.fieldname, idx);
			this.frm.script_manager.trigger(this.df.fieldname + "_add", d.doctype, d.name);
			this.refresh();

			if(show) {
				if(idx) {
					this.wrapper.find("[data-idx='"+idx+"']").data("grid_row")
						.toggle_view(true, callback);
				} else {
					this.wrapper.find(".grid-row:last").data("grid_row").toggle_view(true, callback);
				}
			}

			return d;
		}
	},
	is_editable: function() {
		return this.display_status=="Write" && !this.static_rows
	},
	set_multiple_add: function(link, qty) {
		if(this.multiple_set) return;
		var me = this;
		var link_field = frappe.meta.get_docfield(this.df.options, link);
		$(this.wrapper).find(".grid-add-multiple-rows")
			.removeClass("hide")
			.on("click", function() {
				new frappe.ui.form.LinkSelector({
					doctype: link_field.options,
					fieldname: link,
					qty_fieldname: qty,
					target: me,
					txt: ""
				});
				return false;
			});
		this.multiple_set = true;
	}
});

frappe.ui.form.GridRow = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper = $('<div class="grid-row"></div>').appendTo(this.parent).data("grid_row", this);
		this.row = $('<div class="data-row row"></div>').appendTo(this.wrapper)
			.on("click", function() {
				me.toggle_view();
				return false;
			});

		this.set_row_index();
		this.make_static_display();
		if(this.doc) {
			this.set_data();
		}
	},
	set_row_index: function() {
		if(this.doc) {
			this.wrapper
				.attr("data-idx", this.doc.idx)
				.find(".row-index, .grid-form-row-index").html(this.doc.idx)
		}
	},
	remove: function() {
		if(this.grid.is_editable()) {
			if(this.get_open_form()) {
				this.hide_form();
			}
			this.wrapper.toggle(false);
			frappe.model.clear_doc(this.doc.doctype, this.doc.name);
			this.frm.script_manager.trigger(this.grid.df.fieldname + "_remove", this.doc.doctype, this.doc.name);
			this.frm.dirty();
			this.grid.refresh();
		}
	},
	insert: function(show) {
		var idx = this.doc.idx;
		this.toggle_view(false);
		this.grid.add_new_row(idx, null, show);
	},
	refresh: function() {
		if(this.doc)
			this.doc = locals[this.doc.doctype][this.doc.name];

		// re write columns
		this.grid.static_display_template = null;
		this.make_static_display();

		// refersh form fields
		if(this.get_open_form()) {
			this.layout.refresh(this.doc);
		}
	},
	make_static_display: function() {
		var me = this;
		this.row.empty();
		$('<div class="row-index small">' + (this.doc ? this.doc.idx : "&nbsp;")+ '</div>')
			.appendTo(this.row);

		if(this.grid.template) {
			$('<div class="row-data">').appendTo(this.row)
				.html(frappe.render(this.grid.template, {
					doc: this.doc ? frappe.get_format_helper(this.doc) : null,
					frm: this.frm,
					row: this
				}));
		} else {
			this.add_visible_columns();
		}

		$(this.frm.wrapper).trigger("grid-row-render", [this]);
	},

	add_visible_columns: function() {
		this.make_static_display_template();
		for(var ci in this.static_display_template) {
			var df = this.static_display_template[ci][0];
			var colsize = this.static_display_template[ci][1];
			var txt = this.doc ?
				frappe.format(this.doc[df.fieldname], df, null, this.doc) :
				__(df.label);
			if(this.doc && df.fieldtype === "Select") {
				txt = __(txt);
			}
			var add_class = (["Text", "Small Text"].indexOf(df.fieldtype)===-1) ?
				" grid-overflow-ellipsis" : " grid-overflow-no-ellipsis";
			add_class += (["Int", "Currency", "Float"].indexOf(df.fieldtype)!==-1) ?
				" text-right": "";

			$col = $('<div class="col col-xs-'+colsize+add_class+' grid-static-col"></div>')
				.html(txt)
				.attr("data-fieldname", df.fieldname)
				.data("df", df)
				.appendTo(this.row)
			if(!this.doc) $col.css({"font-weight":"bold"})
		}

	},

	make_static_display_template: function() {
		if(this.static_display_template) return;

		var total_colsize = 1;
		this.static_display_template = [];
		for(var ci in this.docfields) {
			var df = this.docfields[ci];
			if(!df.hidden && df.in_list_view && this.grid.frm.get_perm(df.permlevel, "read")
				&& !in_list(frappe.model.layout_fields, df.fieldtype)) {
					var colsize = 2;
					switch(df.fieldtype) {
						case "Text":
						case "Small Text":
							colsize = 3;
							break;
						case "Check":
							colsize = 1;
							break;
					}
					total_colsize += colsize
					if(total_colsize > 12)
						return false;
					this.static_display_template.push([df, colsize]);
				}
		}

		// redistribute if total-col size is less than 12
		var passes = 0;
		while(total_colsize < 12 && passes < 12) {
			for(var i in this.static_display_template) {
				var df = this.static_display_template[i][0];
				var colsize = this.static_display_template[i][1];
				if(colsize > 1 && colsize < 12 && ["Int", "Currency", "Float",
					"Check", "Percent"].indexOf(df.fieldtype)===-1
					&& !in_list(frappe.model.std_fields_list, df.fieldname)) {
					this.static_display_template[i][1] += 1;
					total_colsize++;
				}

				if(total_colsize >= 12)
					break;
			}
			passes++;
		}
	},
	get_open_form: function() {
		return $(".grid-row-open").data("grid_row");
	},
	toggle_view: function(show, callback) {
		if(!this.doc) return this;

		this.doc = locals[this.doc.doctype][this.doc.name];
		// hide other
		var open_row = this.get_open_form();
		this.fields = [];
		this.fields_dict = {};

		if (show===undefined) show = !!!open_row;

		// call blur
		document.activeElement && document.activeElement.blur()

		if(show && open_row) {
			if(open_row==this) {
				// already open, do nothing
				callback && callback();
				return;
			} else {
				// close other views
				open_row.toggle_view(false);
			}
		}

		this.wrapper.toggleClass("grid-row-open", show);

		if(show) {
			this.show_form();
		} else {
			this.hide_form();
		}
		callback && callback();

		return this;
	},
	show_form: function() {
		if(!this.form_panel) {
			this.form_panel = $('<div class="form-in-grid" style="display: none;"></div>')
				.appendTo(this.wrapper);
		}
		this.render_form();
		this.row.toggle(false);
		this.form_panel.toggle(true);
		frappe.dom.freeze();
		if(this.frm.doc.docstatus===0) {
			var first = this.form_area.find(":input:first");
			if(first.length && first.attr("data-fieldtype")!="Date") {
				try {
					first.get(0).focus();
				} catch(e) {
					console.log("Dialog: unable to focus on first input: " + e);
				}
			}
		}
		cur_frm.cur_grid = this;
	},
	hide_form: function() {
		if(this.form_panel)
			this.form_panel.toggle(false);
		frappe.dom.unfreeze();
		this.row.toggle(true);
		this.make_static_display();
		cur_frm.cur_grid = null;
	},
	open_prev: function() {
		if(this.grid.grid_rows[this.doc.idx-2]) {
			this.grid.grid_rows[this.doc.idx-2].toggle_view(true);
		}
	},
	open_next: function() {
		if(this.grid.grid_rows[this.doc.idx]) {
			this.grid.grid_rows[this.doc.idx].toggle_view(true);
		} else {
			this.grid.add_new_row(null, null, true);
		}
	},
	toggle_add_delete_button_display: function($parent) {
		$parent.find(".grid-delete-row, .grid-insert-row, .grid-append-row")
			.toggle(this.grid.is_editable());
	},
	render_form: function() {
		var me = this;
		this.make_form();
		this.form_area.empty();

		this.layout = new frappe.ui.form.Layout({
			fields: this.docfields,
			body: this.form_area,
			no_submit_on_enter: true,
			frm: this.frm,
		});
		this.layout.make();

		this.fields = this.layout.fields;
		this.fields_dict = this.layout.fields_dict;

		this.layout.refresh(this.doc);

		// copy get_query to fields
		$.each(this.grid.fieldinfo || {}, function(fieldname, fi) {
			$.extend(me.fields_dict[fieldname], fi);
		})

		this.toggle_add_delete_button_display(this.wrapper.find(".panel:first"));

		this.grid.open_grid_row = this;
		this.frm.script_manager.trigger(this.doc.parentfield + "_on_form_rendered", this);
	},
	make_form: function() {
		if(!this.form_area) {
			$(frappe.render(frappe.templates.grid_form, {grid:this})).appendTo(this.form_panel);
			this.form_area = this.wrapper.find(".form-area");
			this.set_row_index();
			this.set_form_events();
		}
	},
	set_form_events: function() {
		var me = this;
		this.form_panel.find(".grid-delete-row")
			.click(function() { me.remove(); return false; })
		this.form_panel.find(".grid-insert-row")
			.click(function() { me.insert(true); return false; })
		this.form_panel.find(".grid-append-row")
			.click(function() {
				me.toggle_view(false);
				me.grid.add_new_row(me.doc.idx+1, null, true);
				return false;
		})
		this.form_panel.find(".grid-form-heading, .grid-footer-toolbar").on("click", function() {
				me.toggle_view();
				return false;
			});
	},
	set_data: function() {
		this.wrapper.data({
			"doc": this.doc
		})
	},
	refresh_field: function(fieldname) {
		var $col = this.row.find("[data-fieldname='"+fieldname+"']");
		if($col.length) {
			$col.html(frappe.format(this.doc[fieldname],
				frappe.meta.get_docfield(this.doc.doctype, fieldname, this.frm.docname), null, this.frm.doc));
		}

		// in form
		if(this.fields_dict && this.fields_dict[fieldname]) {
			this.fields_dict[fieldname].refresh();
			this.layout.refresh_dependency();
		}
	},
	get_visible_columns: function(blacklist) {
		var me = this;
		var visible_columns = $.map(this.docfields, function(df) {
			var visible = !df.hidden && df.in_list_view && me.grid.frm.get_perm(df.permlevel, "read")
				&& !in_list(frappe.model.layout_fields, df.fieldtype) && !in_list(blacklist, df.fieldname);

			return visible ? df : null;
		});
		return visible_columns;
	}
});
