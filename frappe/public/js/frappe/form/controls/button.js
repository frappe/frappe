frappe.ui.form.ControlButton = class ControlButton extends frappe.ui.form.ControlData {
	can_write() {
		// should be always true in case of button
		return true;
	}
	make_input() {
		var me = this;
		const btn_type = this.df.primary ? "btn-primary" : "btn-default";
		const btn_size = this.df.btn_size ? `btn-${this.df.btn_size}` : "btn-xs";
		this.$input = $(`<button class="btn ${btn_size} ${btn_type}">`)
			.prependTo(me.input_area)
			.on("click", function () {
				me.onclick();
			});
		this.input = this.$input.get(0);
		this.set_input_attributes();
		this.has_input = true;
		this.toggle_label(false);
	}
	onclick() {
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
	}
	run_server_script() {
		// DEPRECATE
		var me = this;
		if (this.frm && this.frm.docname) {
			frappe.call({
				method: "run_doc_method",
				args: { docs: this.frm.doc, method: this.df.options },
				btn: this.$input,
				callback: function (r) {
					if (!r.exc) {
						me.frm.refresh_fields();
					}
				},
			});
		}
	}
	hide() {
		this.$input.hide();
	}
	set_input_areas() {
		super.set_input_areas();
		$(this.disp_area).removeClass().addClass("hide");
	}
	set_empty_description() {
		this.$wrapper.find(".help-box").empty().toggle(false);
	}
	set_label(label) {
		if (label) {
			this.df.label = label;
		}
		label = (this.df.icon ? frappe.utils.icon(this.df.icon) : "") + __(this.df.label);
		$(this.label_span).html("&nbsp;");
		this.$input && this.$input.html(label);
	}
};
