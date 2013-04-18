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
		this.render();
	},
	render: function() {
		var me = this;
		this.section = null;
		if(this.fields[0] && this.fields[0].fieldtype!="Section Break") {
			this.make_section();
		}
		$.each(this.fields, function(i, df) {
			switch(df.fieldtype) {
				case "Section Break":
					me.make_section(df);
					break;
				case "Column Break":
					break;
				case "Table":
				case "Text Editor":
				case "Code":
					var fieldwrapper = $('<div class="col-span-12">').appendTo(me.section);
					me.make_field(df, fieldwrapper);
					break;
				case "Text":
					var fieldwrapper = $('<div class="col-span-8">').appendTo(me.section);
					me.make_field(df, fieldwrapper);
					break;
				default:
					var fieldwrapper = $('<div class="col-span-4" \
						style="height: 60px; overflow: hidden;">')
						.appendTo(me.section);
					me.make_field(df, fieldwrapper);
			}
		});
	},
	make_field: function(df, parent) {
		var fieldobj = make_field(df, this.doctype, parent.get(0), this.frm);
		this.frm.fields.push(fieldobj);
		this.frm.fields_dict[df.fieldname] = fieldobj;
	},
	make_section: function(df) {
		if(this.section) {
			$("<hr>").appendTo(this.wrapper);
		}
		this.section = $('<div class="row">').appendTo(this.wrapper);
		this.frm.sections.push(this.section);
		if(df) {
			if(df.label) {
				$('<div class="col-span-12"><h4>' + df.label + "</h4></div>").appendTo(this.section);
			}
			if(df.description) {
				$('<div class="col-span-12 small muted">' + df.description + '</div>').appendTo(this.section);
			}
			this.frm.fields_dict[df.fieldname] = this.section;
		}
		return this.section;
	},
	refresh: function() {

	}
})