frappe.ui.form.ControlCheck = class ControlCheck extends frappe.ui.form.ControlData {
	static html_element = "input";
	static input_type = "checkbox";
	make_wrapper() {
		this.$wrapper = $(`<div class="form-group frappe-control">
			<div class="checkbox">
				<label>
					<span class="input-area"></span>
					<span class="disp-area"></span>
					<span class="label-area"></span>
					<span class="ml-1 help"></span>
				</label>
				<p class="help-box small text-extra-muted"></p>
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
		this.last_value = this.value;
		value = cint(value);
		this.value = value;
		if (this.input) {
			this.input.checked = value ? 1 : 0;
		}
		this.set_mandatory(value);
		this.set_disp_area(value);
	}
};
