frappe.ui.form.ControlJSON = frappe.ui.form.ControlData.extend({
	html_element: "textarea",
	horizontal: false,
	make_wrapper: function() {
		this._super();
		this.$wrapper.find(".like-disabled-input").addClass("for-description");
	},
	make_input: function() {
		this._super();
		this.$input.css({'height': '300px'});
	},
	validate: function(value) {
		if(value){
			try {
				JSON.parse(value);
				return value;
			} catch (e) {
				frappe.msgprint(__("Invalid JSON"));
				return '';
			}
		}
	},
	set_input: function(value) {
		this.last_value = JSON.stringify(this.value, null, '\t');
		this.value = JSON.stringify(value, null, '\t');
		this.set_formatted_input(this.value);
		this.set_mandatory && this.set_mandatory(this.value);
	}
});
