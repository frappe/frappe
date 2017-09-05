frappe.ui.form.ControlButton = frappe.ui.form.ControlData.extend({
	make_input: function() {
		var me = this;
		this.$input = $('<button class="btn btn-default btn-xs">')
			.prependTo(me.input_area)
			.on("click", function() {
				me.onclick();
			});
		this.input = this.$input.get(0);
		this.set_input_attributes();
		this.has_input = true;
		this.toggle_label(false);
	},
	onclick: function() {
		if(this.frm && this.frm.doc) {
			if(this.frm.script_manager.has_handlers(this.df.fieldname, this.doctype)) {
				this.frm.script_manager.trigger(this.df.fieldname, this.doctype, this.docname);
			} else {
				this.frm.runscript(this.df.options, this);
			}
		}
		else if(this.df.click) {
			this.df.click();
		}
	},
	set_input_areas: function() {
		this._super();
		$(this.disp_area).removeClass().addClass("hide");
	},
	set_empty_description: function() {
		this.$wrapper.find(".help-box").empty().toggle(false);
	},
	set_label: function() {
		$(this.label_span).html("&nbsp;");
		this.$input && this.$input.html((this.df.icon ?
			('<i class="'+this.df.icon+' fa-fw"></i> ') : "") + __(this.df.label));
	}
});
