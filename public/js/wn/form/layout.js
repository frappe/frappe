wn.ui.form.Layout = Class.extend({
	init: function(opts) {
		this.ignore_types = ["Section Break", "Column Break"];
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		this.wrapper = $('<div class="form-layout">').appendTo(this.parent);
		this.fields = wn.meta.docfield_list[this.doctype];
		this.fields.sort(function(a,b) { return a.idx - b.idx});
	},
	refresh: function() {
		this.wrapper.empty();
		this.render();
	},
	render: function() {
		var me = this;
		
		this.section = null;
		this.current_row = null;
		if(this.fields[0] && this.fields[0].fieldtype!="Section Break") {
			this.make_section();
		}
		$.each(this.fields, function(i, std_df) {
			var df = wn.meta.get_docfield(me.frm.doctype, std_df.fieldname, me.frm.docname);
			if(!df.hidden) {
				switch(df.fieldtype) {
					case "Section Break":
						me.make_section(df);
						break;
					case "Column Break":
						break;
					case "Table":
					case "Text Editor":
					case "Code":
					case "Text":
					case "Small Text":
					case "HTML":
						me.current_row_spans > 0 &&
							me.make_row();
						var fieldwrapper = $('<div class="col-span-12">').appendTo(me.current_row);
						me.make_field(df, fieldwrapper);
						break;
					default:
						me.current_row_spans >= 12 &&
							me.make_row();
						me.current_row_spans += 4

						var fieldwrapper = $('<div class="col-span-4">')
							.appendTo(me.current_row);
						me.make_field(df, fieldwrapper);
				}
			}
		});
	},
	make_row: function() {
		this.current_row = $('<div class="row">').appendTo(this.section);
		this.current_row_spans = 0;
	},
	make_field: function(df, parent) {
		var fieldobj = make_field(df, this.doctype, parent.get(0), this.frm);
		this.frm.fields.push(fieldobj);
		this.frm.fields_dict[df.fieldname] = fieldobj;
		fieldobj.perm = this.frm.perm;
		fieldobj.refresh();
	},
	make_section: function(df) {
		if(this.section) {
			$("<hr>").appendTo(this.wrapper);
		}
		this.section = $('<div>').appendTo(this.wrapper);
		this.frm.sections.push(this.section);
		this.section[0].df = df;
		if(df) {
			if(df.label) {
				$('<h3>' + df.label + "</h3>").appendTo(this.section);
			}
			if(df.description) {
				$('<div class="col-span-12 small muted">' + df.description + '</div>').appendTo(this.section);
			}
			this.frm.fields_dict[df.fieldname] = this.section;
		}
		this.make_row();
		return this.section;
	}
})