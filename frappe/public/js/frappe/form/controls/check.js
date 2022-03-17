frappe.ui.form.ControlCheck = class ControlCheck extends frappe.ui.form.ControlData {
	static html_element = "input"
	static input_type = "checkbox"
	make_wrapper() {
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
	}
	set_input_areas() {
		this.input_area = this.$wrapper.find(".input-area").get(0);
		if (this.only_input) return;

		this.label_area = this.label_span = this.$wrapper.find(".label-area").get(0);
		this.disp_area = this.$wrapper.find(".disp-area").get(0);
	}
	make_input() {
		super.make_input();
		this.$input.removeClass("form-control");
	}
	get_input_value() {
		return this.input && this.input.checked ? 1 : 0;
	}
	validate(value) {
		return cint(value);
	}
	set_input(value) {
		value = cint(value);
		if(this.input) {
			this.input.checked = (value ? 1 : 0);
		}
		this.last_value = value;
		this.set_mandatory(value);
		this.set_disp_area(value);
	}
};
