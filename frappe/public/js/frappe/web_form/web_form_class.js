import DataTable from 'frappe-datatable';

frappe.provide("frappe.ui");
frappe.provide('frappe.views');

window.web_form = null;
window.web_form_list = null;

frappe.ui.WebForm = class WebForm extends frappe.ui.FieldGroup {
	constructor(opts) {
		super();
		Object.assign(this, opts);
		window.web_form = this;
	}

	make(opts) {
		super.make();
		this.set_field_values();
		this.setup_secondary_action();
		this.setup_primary_action();
	}

	set_field_values() {
		if (this.doc_name) this.set_values(this.doc);
		else return
	}

	setup_primary_action() {
		const primary_action_button = document.createElement("button");
		primary_action_button.classList.add(
			"btn",
			"btn-primary",
			"primary-action",
			"btn-form-submit",
			"btn-sm",
			"ml-2"
		);
		primary_action_button.innerText = web_form.button_label || "Save";
		primary_action_button.onclick = () => this.save();
		document
			.querySelector(".web-form-actions")
			.appendChild(primary_action_button);
	}

	setup_secondary_action() {
		const secondary_action_button = document.createElement("button");
		secondary_action_button.classList.add(
			"btn",
			"btn-danger",
			"button-delete",
			"btn-sm",
			"ml-2"
		);
		secondary_action_button.innerText = "Delete";
		document
			.querySelector(".web-form-actions")
			.appendChild(secondary_action_button);
	}

	save() {
		// Handle data
		let data = this.get_values();
		if (!data || window.saving) return false;
		data.doctype = this.doc_type;

		// Save
		window.saving = true;
		frappe.form_dirty = false;

		frappe.call({
			type: "POST",
			method: "frappe.website.doctype.web_form.web_form.accept",
			args: {
				data: data,
				web_form: this.name
			},
			callback: response => {
				// Check for any exception in response
				if (!response.exc) {
					// Success
					this.handle_success(response.message);
				}
			},
			always: function() {
				window.saving = false;
			}
		});
		return true;
	}

	handle_success(data) {
		const success_dialog = new frappe.ui.Dialog({
			title: __("Saved Successfully"),
			secondary_action: () => {
				if (this.login_required) {
					if (this.route_to_success_link) {
						window.location.pathname = this.success_url;
					} else {
						window.location.href =
							window.location.pathname + "?name=" + data.name;
					}
				}
			}
		});

		const success_message =
			this.success_message || __("Your information has been submitted");
		success_dialog.set_message(success_message);
		success_dialog.show();
	}
};

frappe.views.WebFormList = class WebFormList {
	constructor(opts) {
		Object.assign(this, opts);
		window.web_form_list = this;

		frappe.run_serially([
			() => this.get_list_view_fields(),
			() => this.get_data(),
			() => this.make_datatable()
		])
	}

	get_list_view_fields() {
		return frappe.call({
			method: 'frappe.website.doctype.web_form.web_form.get_in_list_view_fields',
			args: { doctype: this.doctype }
		}).then((response) => this.fields_list = response.message)
	}

	get_data() {
		frappe.call({
			method: 'frappe.www.list.get_list_data',
			args: {
				doctype: this.doctype,
				fields: this.fields_list.map(df => df.fieldname),
				web_form_name: this.web_form_name
			}
		}).then((response) => console.log(response))
	}

	make_datatable() {
		console.log("All good")
	}


}