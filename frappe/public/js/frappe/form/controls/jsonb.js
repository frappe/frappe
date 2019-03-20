frappe.ui.form.ControlJSONB = frappe.ui.form.ControlData.extend({
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
	}
});