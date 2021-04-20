frappe.ui.form.ControlSelect = frappe.ui.form.ControlData.extend({
	html_element: 'select',
	make_input: function() {
		this._super();

		const is_xs_input = this.df.input_class
			&& this.df.input_class.includes('input-xs');
		this.set_icon(is_xs_input);
		this.df.placeholder && this.set_placeholder(is_xs_input);

		this.$input.addClass('ellipsis');
		this.set_options();
	},
	set_icon: function(is_xs_input) {
		const select_icon_html =
			`<div class="select-icon ${is_xs_input ? 'xs' : ''}">
				${frappe.utils.icon('select', is_xs_input ? 'xs' : 'sm')}
			</div>`;
		if (this.only_input) {
			this.$wrapper.append(select_icon_html);
		} else {
			this.$wrapper.find('.control-input')
				.addClass('flex align-center')
				.append(select_icon_html);
		}
	},
	set_placeholder: function(is_xs_input) {
		const placeholder_html =
			`<div class="placeholder ellipsis text-extra-muted ${is_xs_input ? 'xs' : ''}">
				<span>${this.df.placeholder}</span>
			</div>`;
		if (this.only_input) {
			this.$wrapper.append(placeholder_html);
		} else {
			this.$wrapper.find('.control-input').append(placeholder_html);
		}
		this.toggle_placeholder();
		this.$input && this.$input.on('select-change', () => this.toggle_placeholder());
	},
	set_formatted_input: function(value) {
		// refresh options first - (new ones??)
		if(value==null) value = '';
		this.set_options(value);

		// set in the input element
		this._super(value);

		// check if the value to be set is selected
		var input_value = '';
		if(this.$input) {
			input_value = this.$input.val();
		}

		if(value && input_value && value !== input_value) {
			// trying to set a non-existant value
			// model value must be same as whatever the input is
			this.set_model_value(input_value);
		}
	},
	set_options: function(value) {
		// reset options, if something new is set
		var options = this.df.options || [];

		if(typeof this.df.options==="string") {
			options = this.df.options.split("\n");
		}

		// nothing changed
		if (JSON.stringify(options) === this.last_options) {
			return;
		}
		this.last_options = JSON.stringify(options);

		if(this.$input) {
			var selected = this.$input.find(":selected").val();
			this.$input.empty().add_options(options || []);

			if(value===undefined && selected) {
				this.$input.val(selected);
			}
		}
	},
	get_file_attachment_list: function() {
		if(!this.frm) return;
		var fl = frappe.model.docinfo[this.frm.doctype][this.frm.docname];
		if(fl && fl.attachments) {
			this.set_description("");
			var options = [""];
			$.each(fl.attachments, function(i, f) {
				options.push(f.file_url);
			});
			return options;
		} else {
			this.set_description(__("Please attach a file first."));
			return [""];
		}
	},
	toggle_placeholder: function() {
		const input_set = Boolean(this.$input.find('option:selected').text());
		this.$wrapper.find('.placeholder').toggle(!input_set);
	}
});

// add <option> list to <select>
(function($) {
	$.fn.add_options = function(options_list) {
		// create options
		for(var i=0, j=options_list.length; i<j; i++) {
			var v = options_list[i];
			var value = null;
			var label = null;
			if (!is_null(v)) {
				var is_value_null = is_null(v.value);
				var is_label_null = is_null(v.label);
				var is_disabled = Boolean(v.disabled);

				if (is_value_null && is_label_null) {
					value = v;
					label = __(v);
				} else {
					value = is_value_null ? "" : v.value;
					label = is_label_null ? __(value) : __(v.label);
				}
			}

			$('<option>').html(cstr(label))
				.attr('value', value)
				.prop('disabled', is_disabled)
				.appendTo(this);
		}
		// select the first option
		this.selectedIndex = 0;
		$(this).trigger('select-change');
		return $(this);
	};
	$.fn.set_working = function() {
		this.prop('disabled', true);
	};
	$.fn.done_working = function() {
		this.prop('disabled', false);
	};

	let original_val = $.fn.val;
	$.fn.val = function() {
		let result = original_val.apply(this, arguments);
		if (arguments.length > 0) $(this).trigger('select-change');
		return result;
	};
})(jQuery);
