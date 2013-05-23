wn.ui.form.Layout = Class.extend({
	init: function(opts) {
		this.ignore_types = ["Section Break", "Column Break"];
		$.extend(this, opts);
		this.make();
		this.render();
	},
	make: function() {
		this.wrapper = $('<div class="form-layout">').appendTo(this.parent);
		this.fields = wn.meta.docfield_list[this.doctype];
		this.fields.sort(function(a,b) { return a.idx > b.idx ? 1 : -1 });
		this.setup_tabbing();
	},
	refresh: function() {
		var me = this;
		$.each(this.frm.fields, function(i, fieldobj) {
			fieldobj.docname = me.frm.docname;
			fieldobj.df = wn.meta.get_docfield(me.frm.doctype, 
				fieldobj.df.fieldname, me.frm.docname);
			fieldobj.refresh && fieldobj.refresh();
		})
	},
	render: function() {
		var me = this;
		
		this.section = null;
		this.column = null;
		if(this.fields[0] && this.fields[0].fieldtype!="Section Break") {
			this.make_section();
		}
		$.each(this.fields, function(i, std_df) {
			var df = wn.meta.get_docfield(me.frm.doctype, std_df.fieldname, me.frm.docname);
			switch(df.fieldtype) {
				case "Section Break":
					me.make_section(df);
					break;
				case "Column Break":
					me.make_column(df);
					break;
				default:
					me.make_field(df);
			}
		});
	},
	make_column: function(df) {
		this.column = $('<div class="form-column">\
			<form>\
				<fieldset></fieldset>\
			</form>\
		</div>').appendTo(this.section)
			.find("form")
			.on("submit", function() { return false; })
			.find("fieldset");
		
		// distribute all columns equally
		var colspan = cint(12 / this.section.find(".form-column").length);
		this.section.find(".form-column").removeClass()
			.addClass("form-column")
			.addClass("col col-lg-" + colspan);
	},
	make_field: function(df, colspan) {
		!this.column && this.make_column();
		var fieldobj = make_field(df, this.doctype, this.column.get(0), this.frm);
		this.frm.fields.push(fieldobj);
		this.frm.fields_dict[df.fieldname] = fieldobj;
		fieldobj.perm = this.frm.perm;
	},
	make_section: function(df) {
		if(this.section) {
			//$("<hr>").appendTo(this.wrapper);
		}
		this.section = $('<div class="row">').appendTo(this.wrapper);
		this.frm.sections.push(this.section);
		this.section[0].df = df;
		if(df) {
			if(df.label) {
				$('<h3 class="col col-lg-12">' + df.label + "</h3>").appendTo(this.section);
			}
			if(df.description) {
				$('<div class="col col-lg-12 small text-muted">' + df.description + '</div>').appendTo(this.section);
			}
			this.frm.fields_dict[df.fieldname] = this.section;
		}
		// for bc
		this.section.row = {wrapper: this.section};
		this.column = null;
		return this.section;
	},
	setup_tabbing: function() {
		var me = this;
		this.wrapper.on("keydown", function(ev) {
			if(ev.which==9) {
				var current = $(ev.target),
					doctype = current.attr("data-doctype"),
					fieldname = current.attr("data-fieldname");
				if(doctype)
					return me.handle_tab(doctype, fieldname);
			}
		})
	},
	handle_tab: function(doctype, fieldname) {
		var me = this,
			grid_row = null;
			next = null,
			fields = me.frm.fields,
			in_grid = false;
			
		// in grid
		if(doctype != me.frm.doctype) {
			grid_row =me.get_open_grid_row() 
			fields = grid_row.fields;
		}
								
		for(var i=0, len=fields.length; i < len; i++) {
			if(fields[i].df.fieldname==fieldname) {
				if(i==len-1) {
					// last field in this group
					if(grid_row) {
						// in grid
						if(grid_row.doc.idx==grid_row.grid.grid_rows.length) {
							// last row, close it and find next field
							grid_row.toggle_view(false, function() {
								me.handle_tab(grid_row.grid.df.parent, grid_row.grid.df.fieldname);
							})
						} else {
							// next row
							grid_row.grid.grid_rows[grid_row.doc.idx].toggle_view(true);
						}
					} else {
						// last field - to title buttons
					}
				} else {
					me.focus_on_next_field(i, fields);
				}
				
				break;
			}
		}
		return false;
	},
	focus_on_next_field: function(start_idx, fields) {
		// loop to find next eligible fields
		for(var ii= start_idx + 1, len = fields.length; ii < len; ii++) {
			if(fields[ii].disp_status=="Write") {
				var next = fields[ii];

				// next is table, show the table
				if(next.df.fieldtype=="Table") {
					if(!next.grid.grid_rows.length) {
						next.grid.add_new_row(1);
					} else {
						next.grid.grid_rows[0].toggle_view(true);
					}
				}
				else if(next.editor) {
					next.editor.set_focus();
				}
				else if(next.$input) {
					next.$input.focus();
				}
				break;
			}
		}
	},
	get_open_grid_row: function() {
		return $(".grid-row-open").data("grid_row");
	},
})