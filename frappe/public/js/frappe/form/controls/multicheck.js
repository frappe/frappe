frappe.ui.form.ControlMultiCheck = frappe.ui.form.ControlData.extend({
	set_input_areas() {
		this._super();
		const load_state = $('<div class="load-state text-muted small">' + __("Loading") + '...</div>');
		this.$input_wrapper.append(load_state);

		this.options = this.df.options.split(',');
		this.check_field_attr = 'data-' + this.df.fieldname.slice(0, -1);
		this.options.forEach(option => {
			this.get_checkbox_element(option).appendTo(this.input_area);
		});
		this.bind_checkboxes();
	},

	refresh_input() {
		this._super();
		this.selected_options = this.value.split(',').filter(option => option.length > 0);
		this.selected_options.forEach(option => {
			$(this.input_area)
				.find(`:checkbox[${this.check_field_attr}=${option}]`)
				.prop("checked", true);
		});
	},

	bind_checkboxes() {
		$(this.input_area).on('change', ':checkbox', e => {
			const $checkbox = $(e.target);
			const option = $checkbox.attr(this.check_field_attr);
			if($checkbox.is(':checked')) {
				this.selected_options.push(option);
			} else {
				let index = this.selected_options.indexOf(option);
				this.selected_options.splice(index, 1);
			}
			this.set_value(this.selected_options.join(','));
			//trigger
		});
	},

	get_checkbox_element: function(option) {
		return $(`
			<div class="checkbox" ${this.check_field_attr}="${option}">
				<label>
				<input type="checkbox" ${this.check_field_attr}="${option}"></input>
				<span class="label-area small">${option}</span>
				</label>
			</div>
		`);
	},
});
