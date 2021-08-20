frappe.ui.form.ControlCheck = frappe.ui.form.ControlData.extend({
	input_type: "checkbox",
	make_wrapper: function() {
		this.$wrapper = $(`<div class="form-group frappe-control">
			<div class="checkbox">
				<label>
					<span class="input-area"></span>
					<span class="disp-area"></span>
					<span class="label-area"></span>
				</label>
				<p class="help-box small text-muted"></p>
			</div>
		</div>`).appendTo(this.parent);
	},
	set_input_areas: function() {
		this.input_area = this.$wrapper.find(".input-area").get(0);
		if (this.only_input) return;

		this.label_area = this.label_span = this.$wrapper.find(".label-area").get(0);
		this.disp_area = this.$wrapper.find(".disp-area").get(0);
	},
	make_input: function() {
		this._super();
		this.$input.removeClass("form-control");
	},
	get_input_value: function() {
		return this.input && this.input.checked ? 1 : 0;
	},
	validate: function(value) {
		return cint(value);
	},
	set_input: function(value) {
		value = cint(value);
		if(this.input) {
			this.input.checked = (value ? 1 : 0);
		}
		this.last_value = value;
		this.set_mandatory(value);
		this.set_disp_area(value);
	}
});
