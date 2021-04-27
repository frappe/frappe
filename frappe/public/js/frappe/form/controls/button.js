frappe.ui.form.ControlButton = frappe.ui.form.ControlData.extend({
	can_write() {
		// should be always true in case of button
		return true;
	},
	make_input: function() {
		var me = this;
		const btn_type = this.df.primary ? 'btn-primary': 'btn-default';
		const btn_size = this.df.btn_size
			? `btn-${this.df.btn_size}`
			: "btn-xs";
		this.$input = $(`<button class="btn ${btn_size} ${btn_type}">`)
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
		if (this.frm && this.frm.doc) {
			if (this.frm.script_manager.has_handlers(this.df.fieldname, this.doctype)) {
				this.frm.script_manager.trigger(this.df.fieldname, this.doctype, this.docname);
			} else {
				if (this.df.options) {
					this.run_server_script();
				}
			}
		} else if (this.df.click) {
			this.df.click();
		}
	},
	run_server_script: function() {
		// DEPRECATE
		var me = this;
		if(this.frm && this.frm.docname) {
			frappe.call({
				method: "run_doc_method",
				args: {'docs': this.frm.doc, 'method': this.df.options },
				btn: this.$input,
				callback: function(r) {
					if(!r.exc) {
						me.frm.refresh_fields();
					}
				}
			});
		}
	},
	hide() {
		this.$input.hide();
	},
	set_input_areas: function() {
		this._super();
		$(this.disp_area).removeClass().addClass("hide");
	},
	set_empty_description: function() {
		this.$wrapper.find(".help-box").empty().toggle(false);
	},
	set_label: function(label) {
		if (label) {
			this.df.label = label;
		}
		label = (this.df.icon ? frappe.utils.icon(this.df.icon) : "") + __(this.df.label);
		$(this.label_span).html("&nbsp;");
		this.$input && this.$input.html(label);
	}
});
