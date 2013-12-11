// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
wn.provide("wn.ui.form");
wn.ui.form.Layout = Class.extend({
	init: function(opts) {
		this.views = {};
		this.sections = [];
		this.fields_list = [];
		this.fields_dict = {};
		this.labelled_section_count = 0;
		this.ignore_types = ["Section Break", "Column Break"];
								
		$.extend(this, opts);
	},
	make: function() {
		if(!this.parent && this.body) 
			this.parent = this.body;
		this.wrapper = $('<div class="form-layout">').appendTo(this.parent);
		if(!this.fields)
			this.fields = wn.meta.sort_docfields(wn.meta.docfield_map[this.doctype]);
		this.setup_tabbing();
		this.render();
	},
	add_view: function(label) {
		var view = $('<div class="form-add-view">').appendTo(this.parent).toggle(false);
		this.views[label] = view;
	},
	set_view: function(label) {
		if(this.cur_view) this.cur_view.toggle(false);
		if(label) {
			this.wrapper.toggle(false);
			if(!this.views[label])
				this.add_view(label);
			this.cur_view = this.views[label].toggle(true);
		} else {
			this.wrapper.toggle(true);
		}
	},
	refresh: function() {
		var me = this;
		$.each(this.fields_list, function(i, fieldobj) {
			if(me.frm) {
				fieldobj.docname = me.frm.docname;
				fieldobj.df = wn.meta.get_docfield(me.frm.doctype, 
					fieldobj.df.fieldname, me.frm.docname);
				// on form change, permissions can change
				fieldobj.perm = me.frm.perm;
			};
			fieldobj.refresh && fieldobj.refresh();
		});
		if(this.frm)
			$(this.frm.wrapper).trigger("refresh-fields");
	},
	render: function() {
		var me = this;
		
		this.section = null;
		this.column = null;
		if(this.fields[0] && this.fields[0].fieldtype!="Section Break") {
			this.make_section();
		}
		$.each(this.fields, function(i, df) {
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
			</form>\
		</div>').appendTo(this.section.body)
			.find("form")
			.on("submit", function() { return false; })
		
		// distribute all columns equally
		var colspan = cint(12 / this.section.find(".form-column").length);
		this.section.find(".form-column").removeClass()
			.addClass("form-column")
			.addClass("col-md-" + colspan);
	},
	make_field: function(df, colspan) {
		!this.column && this.make_column();
		var fieldobj = make_field(df, this.doctype, this.column.get(0), this.frm);
		fieldobj.layout = this;
		this.fields_list.push(fieldobj);
		this.fields_dict[df.fieldname] = fieldobj;
		if(this.frm) {
			fieldobj.perm = this.frm.perm;
		}
	},
	make_section: function(df) {
		if(this.section) {
			//$("<hr>").appendTo(this.wrapper);
		}
		this.section = $('<div class="row">')
			.appendTo(this.wrapper);
		this.sections.push(this.section);
		
		var section = this.section[0];
		section.df = df;
		if(df) {
			if(df.label) {
				this.labelled_section_count++;
				var head = $('<h4 class="col-md-12 text-muted">' 
					+ (df.options ? (' <i class="icon-in-circle '+df.options+'"></i> ') : "") 
					+ '<span class="section-count-label">' + this.labelled_section_count + "</span>. " 
					+ wn._(df.label)
					+ "</h4>")
					.appendTo(this.section);
					
				if(df && df.idx===1) 
					head.css({"margin-top": "0px"})
				if(this.sections.length > 1)
					this.section.css({
						"margin-top": "15px", 
						"border-top": "1px solid #c7c7c7"
					});
			}
			if(df.description) {
				$('<div class="col-md-12 small text-muted">' + df.description + '</div>')
					.css("padding-left", "40px")
					.appendTo(this.section);
			}
			if(df.label || df.description) {
				// spacer
				$('<div class="col-md-12"></div>')
					.appendTo(this.section)
					.css({"height": "10px"});
			}
			this.fields_dict[df.fieldname] = section;
			this.fields_list.push(section);
		}
		// for bc
		this.section.body = $('<div>').appendTo(this.section);
		// if(this.frm)
		// 	this.section.body.css({"padding":"0px 3%"})
		section.row = {
			wrapper: section
		};
		section.refresh = function() {
			if(!this.df) return;
			$(this).toggle(this.df.hidden || this.df.hidden_due_to_dependency 
				? false : (cur_frm ? !!cur_frm.get_perm(this.df.permlevel, READ) : true))
		}
		this.column = null;
		section.refresh.call(section);
		return this.section;
	},
	refresh_section_count: function() {
		this.wrapper.find(".section-count-label:visible").each(function(i) {
			$(this).html(i+1);
		});
	},
	setup_tabbing: function() {
		var me = this;
		this.wrapper.on("keydown", function(ev) {
			if(ev.which==9) {
				var current = $(ev.target).trigger("change"),
					doctype = current.attr("data-doctype"),
					fieldname = current.attr("data-fieldname");
				if(doctype)
					return me.handle_tab(doctype, fieldname, ev.shiftKey);
			}
		})
	},
	handle_tab: function(doctype, fieldname, shift) {
		var me = this,
			grid_row = null;
			prev = null,
			fields = me.fields,
			in_grid = false;
			
		// in grid
		if(doctype != me.doctype) {
			grid_row =me.get_open_grid_row() 
			fields = grid_row.fields;
		}
								
		for(var i=0, len=fields.length; i < len; i++) {
			if(fields[i].df.fieldname==fieldname) {
				if(shift) {
					if(prev) {
						this.set_focus(prev)
					} else {
						$(this.primary_button).focus();
					}
					break;
				}
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
						$(this.primary_button).focus();
					}
				} else {
					me.focus_on_next_field(i, fields);
				}
				
				break;
			}
			if(fields[i].disp_status==="Write")
				prev = fields[i];
		}
		return false;
	},
	focus_on_next_field: function(start_idx, fields) {
		// loop to find next eligible fields
		for(var i= start_idx + 1, len = fields.length; i < len; i++) {
			if(fields[i].disp_status==="Write" && !in_list(wn.model.no_value_type, fields[i].df.fieldtype)) {
				this.set_focus(fields[i]);
				break;
			}
		}
	},
	set_focus: function(field) {
		// next is table, show the table
		if(field.df.fieldtype=="Table") {
			if(!field.grid.grid_rows.length) {
				field.grid.add_new_row(1);
			} else {
				field.grid.grid_rows[0].toggle_view(true);
			}
		}
		else if(field.editor) {
			field.editor.set_focus();
		}
		else if(field.$input) {
			field.$input.focus();
		}
	},
	get_open_grid_row: function() {
		return $(".grid-row-open").data("grid_row");
	},
	
})