frappe.provide("frappe.ui");
frappe.provide("frappe.web_form");
import EventEmitterMixin from '../../frappe/event_emitter';

export default class WebForm extends frappe.ui.FieldGroup {
	constructor(opts) {
		super();
		Object.assign(this, opts);
		frappe.web_form = this;
		frappe.web_form.events = {};
		Object.assign(frappe.web_form.events, EventEmitterMixin);
	}

	prepare(web_form_doc, doc) {
		Object.assign(this, web_form_doc);
		this.fields = web_form_doc.web_form_fields;
		this.doc = doc;
	}

	make() {
		super.make();
		this.set_field_values();
		if (this.introduction_text) this.set_form_description(this.introduction_text);
		if (this.allow_print && !this.is_new) this.setup_print_button();
		if (this.allow_delete && !this.is_new) this.setup_delete_button();
		if (this.is_new) this.setup_cancel_button();
		this.setup_primary_action();
		$(".link-btn").remove();

		// webform client script
		frappe.init_client_script && frappe.init_client_script();
		frappe.web_form.events.trigger('after_load');
	}

	on(fieldname, handler) {
		let field = this.fields_dict[fieldname];
		field.df.change = () => {
			handler(field, field.value);
		};
	}

	set_field_values() {
		if (this.doc_name) this.set_values(this.doc);
		else return;
	}

	set_default_values() {
		let values = frappe.utils.get_query_params();
		delete values.new;
		this.set_values(values);
	}

	set_form_description(intro) {
		let intro_wrapper = document.getElementById('introduction');
		intro_wrapper.innerHTML = intro;
	}

	add_button(name, type, action, wrapper_class=".web-form-actions") {
		const button = document.createElement("button");
		button.classList.add("btn", "btn-" + type, "btn-sm", "ml-2");
		button.innerHTML = name;
		button.onclick = action;
		document.querySelector(wrapper_class).appendChild(button);
	}

	add_button_to_footer(name, type, action) {
		this.add_button(name, type, action, '.web-form-footer');
	}

	add_button_to_header(name, type, action) {
		this.add_button(name, type, action, '.web-form-actions');
	}

	setup_primary_action() {
		this.add_button_to_header(this.button_label || "Save", "primary", () =>
			this.save()
		);

		this.add_button_to_footer(this.button_label || "Save", "primary", () =>
			this.save()
		);
	}

	setup_cancel_button() {
		this.add_button_to_header("Cancel", "light", () => this.cancel());
	}

	setup_delete_button() {
		this.add_button_to_header("Delete", "danger", () => this.delete());
	}

	setup_print_button() {
		this.add_button_to_header(
			'<i class="fa fa-print" aria-hidden="true"></i>',
			"light",
			() => this.print()
		);
	}

	get_values(ignore_errors) {
		let values = super.get_values(ignore_errors);
		values.doctype = this.doc_type;
		values.name = this.doc_name;
		values.web_form_name = this.name;
		return values;
	}

	save() {
		this.validate && this.validate();

		let for_payment = Boolean(this.accept_payment && !this.doc.paid);
		let data = this.get_values(this.allow_incomplete);
		if (!data || window.saving) return;

		// Save
		window.saving = true;
		frappe.form_dirty = false;

		frappe.call({
			type: "POST",
			method: "frappe.website.doctype.web_form.web_form.accept",
			args: {
				data: data,
				web_form: this.name,
				docname: this.doc.name,
				for_payment
			},
			callback: response => {
				// Check for any exception in response
				if (!response.exc) {
					// Success
					this.handle_success(response.message);
					frappe.web_form.events.trigger('after_save');
				}
			},
			always: function() {
				window.saving = false;
			}
		});
		return true;
	}

	delete() {
		frappe.call({
			type: "POST",
			method: "frappe.website.doctype.web_form.web_form.delete",
			args: {
				web_form_name: this.name,
				docname: this.doc.name
			}
		});
	}

	print() {
		window.location.href = `/printview?
			doctype=${this.doc_type}
			&name=${this.doc.name}
			&format=${this.print_format || "Standard"}`;
	}

	cancel() {
		window.location.href = window.location.pathname;
	}

	handle_success(data) {
		if (this.accept_payment && !this.doc.paid) {
			window.location.href = data;
		}

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

		success_dialog.show();
		const success_message =
			this.success_message || __("Your information has been submitted");
		success_dialog.set_message(success_message);
	}
}