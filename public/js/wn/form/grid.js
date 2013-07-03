wn.ui.form.Grid = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.fieldinfo = {};
		this.doctype = this.df.options;
	},
	make: function() {
		var me = this;
		
		this.wrapper = $('<div>\
		<div class="panel">\
			<div class="panel-heading" style="font-size: 15px;"></div>\
			<div class="rows"></div>\
			<div style="margin-top: 5px; margin-bottom: -5px;">\
				<a href="#" class="grid-add-row">+ '+wn._("Add new row")+'.</a>\
				<span class="text-muted">Click on row to edit.</span></div>\
		</div>\
		</div>').appendTo(this.parent);

		$(this.wrapper).find(".grid-add-row").click(function() {
			wn.model.add_child(me.frm.doc, me.df.options, me.df.fieldname);
			me.refresh();
			me.wrapper.find(".grid-row:last").data("grid_row").toggle_view(true);
			return false;
		})
		
	},
	make_head: function() {
		// labels
		this.header_row = new wn.ui.form.GridRow({
			parent: $(this.parent).find(".panel-heading"),
			parent_df: this.df,
			docfields: this.docfields,
			frm: this.frm,
			grid: this
		});	
	},
	refresh: function() {
		!this.wrapper && this.make();
		var me = this,
			$rows = $(me.parent).find(".rows"),
			data = this.get_data();
		
		this.docfields = wn.meta.get_docfields(this.doctype, this.frm.docname);
		this.display_status = wn.perm.get_field_display_status(this.df, this.frm.doc, 
			this.perm);

		if(this.data_rows_are_same(data)) {
			// soft refresh
			this.header_row.refresh();
			$.each(this.grid_rows, function(i, g) {
				g.refresh();
			});
		} else {
			// redraw
			this.wrapper.find(".grid-row").remove();
			this.make_head();
			this.grid_rows = [];
			this.grid_rows_by_docname = {};
			$.each(data || [], function(ri, d) {
				var grid_row = new wn.ui.form.GridRow({
					parent: $rows,
					parent_df: me.df,
					docfields: me.docfields,
					doc: d,
					frm: me.frm,
					grid: me
				});
				me.grid_rows.push(grid_row)
				me.grid_rows_by_docname[d.name] = grid_row;
			});

			this.wrapper.find(".grid-add-row").toggle(this.display_status=="Write" 
				&& !this.static_rows);
			if(this.display_status=="Write" && !this.static_rows) {
				this.make_sortable($rows);
			}

			this.last_display_status = this.display_status;
			this.last_docname = this.frm.docname;
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
					return g.doc.name==data[i].name ? null : true;
				}).length; 
				
			return same;
		}
	},
	make_sortable: function($rows) {
		var me =this;
		$rows.sortable({
			update: function(event, ui) {
				$rows.find(".grid-row").each(function(i, item) {
					var doc = $(item).data("doc");
					doc.idx = i + 1;
					$(this).find(".row-index").html(i + 1);
					me.frm.dirty();
				})
			}
		});
	},
	get_data: function() {
		var data = wn.model.get(this.df.options, {
			"parenttype": this.frm.doctype, 
			"parentfield": this.df.fieldname,
			"parent": this.frm.docname
		});
		data.sort(function(a, b) { return a.idx > b.idx ? 1 : -1 });
		return data;
	},
	set_column_disp: function(fieldname, show) {
		wn.meta.get_docfield(this.doctype, fieldname, this.frm.docname).hidden = !show;
		this.refresh();
	},
	toggle_reqd: function(fieldname, reqd) {
		wn.meta.get_docfield(this.doctype, fieldname, this.frm.docname).reqd = reqd;
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
		this.grid_rows_by_docname[doc.name].refresh_field(fieldname);
	},
	add_new_row: function(idx, callback) {
		wn.model.add_child(this.frm.doc, this.df.options, this.df.fieldname, idx);
		this.refresh();
		// show
		
		this.wrapper.find("[data-idx='"+idx+"']").data("grid_row")
			.toggle_view(true, callback);
	}
});

wn.ui.form.GridRow = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.show = false;
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper = $('<div class="grid-row">\
			<div class="data-row" style="min-height: 15px;"></div>\
			<div class="panel panel-warning" style="display: none;">\
				<div class="panel-heading">\
					<div class="toolbar" style="height: 36px;">\
						Editing Row #<span class="row-index"></span>\
						<button class="btn btn-success pull-right" \
							title="'+wn._("Close")+'"\
							style="margin-left: 7px;">\
							<i class="icon-ok"></i></button>\
						<button class="btn btn-default pull-right grid-insert-row" \
							title="'+wn._("Insert Row")+'"\
							style="margin-left: 7px;">\
							<i class="icon-plus"></i></button>\
						<button class="btn btn-danger pull-right"\
							title="'+wn._("Delete Row")+'"\
							><i class="icon-trash"></i></button>\
					</div>\
				</div>\
				<div class="form-area"></div>\
			</div>\
			<div class="divider row"></div>\
		</div>')
			.appendTo(this.parent)
			.data("grid_row", this);

		if(this.doc) {
			this.wrapper
				.attr("data-idx", this.doc.idx)
				.find(".row-index").html(this.doc.idx)

			this.wrapper.find(".data-row, .panel-heading")
				.click(function() {
					me.toggle_view();
					return false;
				});
			this.set_button_events();
		}
		this.form_panel = this.wrapper.find(".panel");
		this.row = this.wrapper.find(".data-row");
		this.form_area = this.wrapper.find(".form-area");

		this.make_static_display();
		if(this.doc) {
			this.set_data();
		}
	},
	set_button_events: function() {
		var me = this;
				
		this.wrapper.find(".btn-danger").click(function() {
			me.wrapper.fadeOut(function() {
				wn.model.clear_doc(me.doc.doctype, me.doc.name);
				me.frm.dirty();
				me.grid.refresh();
			});
			return false;
		});
		
		this.wrapper.find(".grid-insert-row").click(function() {
			var idx = me.doc.idx;
			me.toggle_view(false);
			me.grid.add_new_row(idx);
			return false;
		})
	},
	refresh: function() {
		if(this.doc)
			this.doc = locals[this.doc.doctype][this.doc.name];
		
		// re write columns
		this.make_static_display();
		
		// refersh form fields
		if(this.show) {
			$.each(this.fields, function(i, f) {
				f.refresh();
			});
		} 
	},
	make_static_display: function() {
		var me = this,
			total_colsize = 1;
		me.row.empty();
		col = $('<div class="col col-lg-1 row-index">' + (me.doc ? me.doc.idx : "#")+ '</div>')
			.appendTo(me.row)
		$.each(me.docfields, function(ci, df) {
			if(!df.hidden && !df.print_hide && me.grid.frm.perm[df.permlevel][READ]
				&& !in_list(["Section Break", "Column Break"], df.fieldtype)) {
				var colsize = 2,
					txt = me.doc ? 
						wn.format(me.doc[df.fieldname], df, null, me.doc) : 
						df.label;
				switch(df.fieldtype) {
					case "Text":
						colsize = 3;
						break;
					case "Check":
						colsize = 1;
						break;
				}
				total_colsize += colsize
				if(total_colsize > 12) 
					return false;
				$col = $('<div class="col col-lg-'+colsize+'">' 
					+ txt + '</div>')
					.css({
						"overflow": "hidden",
						"text-overflow": "ellipsis",
						"white-space": "nowrap",
						"padding-right": "0px"
					})
					.attr("data-fieldname", df.fieldname)
					.data("df", df)
					.appendTo(me.row)
				if(in_list(["Int", "Currency", "Float"], df.fieldtype))
					$col.css({"text-align": "right"})
			}
		});

		$(this.frm.wrapper).trigger("grid-row-render", [this]);
	},
	toggle_view: function(show, callback) {
		this.doc = locals[this.doc.doctype][this.doc.name];
		// hide other
		var open_row = $(".grid-row-open").data("grid_row"),
			me = this;

		this.fields = [];
		this.fields_dict = {};
				
		this.show = show===undefined ? 
			show = !this.show :
			show

		if(show && open_row) {
			if(open_row==this) {
				// already open, do nothing
				callback();
				return;
			} else {
				// close other views
				open_row.toggle_view(false);
			}
		}

		this.make_static_display();
		this.wrapper.toggleClass("grid-row-open", this.show);

		this.show && this.render_form()
		this.show && this.row.toggle(false);

		this.form_panel.slideToggle(this.show, function() {
			if(me.show) {
				if(me.frm.doc.docstatus===0)
					me.form_area.find(":input:first").focus();
			} else {
				$(me.form_area).empty();
				me.row.toggle(true);
			}
			callback && callback();
		});
	},
	render_form: function() {
		var me = this,
			make_row = function(label) {
				var row = $('<div class="row">').appendTo(me.form_area);
				
				if(label)
					$('<div class="col col-lg-12"><h4>'+ label +'</h4></div>')
						.appendTo(row);
				
				var col1 = $('<div class="col col-lg-6"></div>').appendTo(row),
					col2 = $('<div class="col col-lg-6"></div>').appendTo(row);
				
				return [col1, col2];
			},
			cols = make_row(),
			cnt = 0;
		
		$.each(me.docfields, function(ci, df) {
			if(!df.hidden) {
				if(df.fieldtype=="Section Break") {
					cols = make_row(df.label);
					cnt = 0;
				}
				var fieldwrapper = $('<div>')
					.appendTo(cols[cnt % 2])
				var fieldobj = make_field(df, me.parent_df.options, 
					fieldwrapper.get(0), me.frm);
				fieldobj.docname = me.doc.name;
				fieldobj.refresh();
				fieldobj.input &&
					$(fieldobj.input).css({"max-height": "100px"});
					
				// set field properties
				// used for setting custom get queries in links
				if(me.grid.fieldinfo[df.fieldname])
					$.extend(fieldobj, me.grid.fieldinfo[df.fieldname]);

				me.fields.push(fieldobj);
				me.fields_dict[df.fieldname] = fieldobj;
				cnt++;
			}
		});

		if(this.grid.display_status!="Write" || this.grid.static_rows) {
			this.wrapper.find(".btn-danger, .grid-insert-row").toggle(false);
		}
		
		this.grid.open_grid_row = this;
	},
	set_data: function() {
		this.wrapper.data({
			"doc": this.doc
		})
	},
	refresh_field: function(fieldname) {
		var $col = this.row.find("[data-fieldname='"+fieldname+"']");
		if($col.length) {
			var value = wn.model.get_value(this.doc.doctype, this.doc.name, fieldname);
			$col.html(wn.format(value, $col.data("df"), null, this.doc));
		}

		// in form
		if(this.fields_dict && this.fields_dict[fieldname]) {
			this.fields_dict[fieldname].refresh();
		}
	},	
});