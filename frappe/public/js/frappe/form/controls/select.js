frappe.ui.form.ControlSelect = frappe.ui.form.ControlData.extend({
	html_element: 'select',
	make_input: function() {
		this._super();
		this.$wrapper.find('.control-input')
			.addClass('flex align-center')
			.append('<i class="octicon octicon-chevron-down text-muted"></i>');
		this.set_options();
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
		return $(this);
	};
	$.fn.set_working = function() {
		this.prop('disabled', true);
	};
	$.fn.done_working = function() {
		this.prop('disabled', false);
	};
})(jQuery);
