frappe.ui.form.ControlMultiCheck = frappe.ui.form.ControlData.extend({
	// UI: multiple checkboxes
	// Value: comma-separated string of options

	make_input() {
		this._super();
		this.$input.hide();
		this.$load_state = $('<div class="load-state text-muted small">' + __("Loading") + '...</div>');
		this.$select_buttons = this.get_select_buttons().prependTo(this.$input_wrapper);
		this.$input_wrapper.append(this.$load_state);

		this.check_field_attr = 'data-' + this.df.fieldname.slice(0, -1);
		this.$checkbox_area = $('<div class="checkbox-options"></div>').appendTo(this.input_area);
		this.set_options();
		this.bind_checkboxes();
	},

	refresh_input_area() {
		this.set_options();
		this.refresh_input();
	},

	set_options() {
		this.$load_state.show();
		this.$select_buttons.hide();
		this.parse_df_options();

		if(this.get_data) {
			if(typeof this.get_data().then == 'function') {
				this.get_data().then(results => {
					this.options = results;
					this.make_checkboxes();
				})
			} else {
				this.options = this.get_data();
				this.make_checkboxes();
			}
		} else {
			this.make_checkboxes();
		}
	},

	refresh_input() {
		this._super();
		this.selected_options = this.split(this.value);
		this.options.forEach(option => {
			$(this.input_area)
				.find(`:checkbox[${this.check_field_attr}=${option}]`)
				.prop("checked", this.selected_options.includes(option));
		});
	},

	parse_df_options() {
		if(frappe.utils.is_json_string(this.df.options)) {
			let args = JSON.parse(this.df.options);
			this.options = this.split(args.options || "");
			if(args.select_all) {
				this.select_all = true;
			}
		} else {
			this.options = this.split(this.df.options);
		}
	},

	make_checkboxes() {
		this.$load_state.hide();
		this.$checkbox_area.empty();
		this.options.forEach(option => {
			this.get_checkbox_element(option).appendTo(this.$checkbox_area);
		});
		if(this.select_all) {
			this.setup_select_all();
		}
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
		});
	},

	setup_select_all() {
		this.$select_buttons.show();
		let select_all = (deselect=false) => {
			$(this.input_area).find(`:checkbox`).prop("checked", deselect).trigger('click');
		}
		this.$select_buttons.find('.select-all').on('click', () => {
			select_all();
		});
		this.$select_buttons.find('.deselect-all').on('click', () => {
			select_all(true);
		});
	},

	get_checkbox_element(option) {
		return $(`
			<div class="checkbox">
				<label>
				<input type="checkbox" ${this.check_field_attr}="${option}"></input>
				<span class="label-area small">${option}</span>
				</label>
			</div>
		`);
	},

	get_select_buttons() {
		return $(`<div><button class="btn btn-xs btn-default select-all"
			style="margin-right: 5px;">${__("Select All")}</button>
			<button class="btn btn-xs btn-default deselect-all">
		${__("Unselect All")}</button></div>`);
	},

	split(str) {
		return str.split(',').filter(option => option.length > 0);
	}
});
