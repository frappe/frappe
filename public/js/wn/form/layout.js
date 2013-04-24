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
		this.fields.sort(function(a,b) { return a.idx - b.idx});
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
			<form class="form-horizontal">\
			</form>\
		</div>').appendTo(this.section)
			.find("form")
			.on("submit", function() { return false; });
		
		// distribute all columns equally
		var colspan = cint(12 / this.section.find(".form-column").length);
		this.section.find(".form-column").removeClass()
			.addClass("form-column")
			.addClass("col-span-" + colspan);
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
			$("<hr>").appendTo(this.wrapper);
		}
		this.section = $('<div class="row">').appendTo(this.wrapper);
		this.frm.sections.push(this.section);
		this.section[0].df = df;
		if(df) {
			if(df.label) {
				$('<h3 class="col-span-12">' + df.label + "</h3>").appendTo(this.section);
			}
			if(df.description) {
				$('<div class="col-span-12 small muted">' + df.description + '</div>').appendTo(this.section);
			}
			this.frm.fields_dict[df.fieldname] = this.section;
		}
		this.column = null;
		return this.section;
	}
})