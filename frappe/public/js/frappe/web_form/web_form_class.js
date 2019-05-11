frappe.provide('frappe.ui')

window.web_form = null;

frappe.ui.WebForm = class WebForm extends frappe.ui.FieldGroup {
	constructor(opts) {
		super();
		Object.assign(this, opts)
		window.web_form = this
	}
	make(opts) {
		super.make();

		this.setup_primary_action();
	}
	setup_primary_action() {
		const primary_action_button = document.createElement('button');
		primary_action_button.classList.add('btn', 'btn-primary');
		primary_action_button.innerText = 'Save'
		document.querySelector('.web-form-actions').appendChild(primary_action_button);
	}
};
