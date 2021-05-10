frappe.provide("frappe.ui");
frappe.provide("frappe.web_form");
import EventEmitterMixin from "../../frappe/event_emitter";

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
		if (this.allow_print && !this.is_new) this.setup_print_button();
		if (this.allow_delete && !this.is_new) this.setup_delete_button();
		if (this.is_new) this.setup_cancel_button();
		this.setup_primary_action();
		// $(".link-btn").remove();

		// webform client script
		frappe.init_client_script && frappe.init_client_script();
		frappe.web_form.events.trigger("after_load");
		this.after_load && this.after_load();
	}

	on(fieldname, handler) {
		let field = this.fields_dict[fieldname];
		field.df.change = () => {
			handler(field, field.value);
		};
	}

	set_field_values() {
		if (this.doc.name) this.set_values(this.doc);
		else return;
	}

	set_default_values() {
		let values = frappe.utils.get_query_params();
		delete values.new;
		this.set_values(values);
	}

	add_button(name, type, action, wrapper_class = ".web-form-actions") {
		return $("<button>")
			.addClass(`btn btn-${type} btn-sm`)
			.html(name)
			.on("click", action)
			.appendTo(wrapper_class);
	}

	add_button_to_footer(name, type, action) {
		return this.add_button(name, type, action, ".web-form-footer");
	}

	add_button_to_header(name, type, action) {
		return this.add_button(name, type, action, ".web-form-actions");
	}

	setup_primary_action() {
		// this.add_button_to_header(this.button_label || "Save", "primary", () =>
		// 	this.save()
		// );

		this.$btn_primary = this.add_button_to_footer(
			this.button_label || "Save",
			"primary",
			() => this.submit()
		);
	}

	setup_cancel_button() {
		// this.add_button_to_header(__("Cancel"), "light", () => this.cancel());
	}

	setup_delete_button() {
		this.add_button_to_header(frappe.utils.icon("delete"), "danger", () =>
			this.delete()
		);
	}

	setup_print_button() {
		this.add_button_to_header(frappe.utils.icon("print"), "light", () =>
			this.print()
		);
	}

	submit() {
		let is_new = this.is_new;
		if (this.validate && !this.validate()) {
			frappe.throw(
				__("Couldn't save, please check the data you have entered"),
				__("Validation Error")
			);
		}

		// validation hack: get_values will check for missing data
		let doc_values = super.get_values(this.allow_incomplete);
		if (!doc_values) return;

		Object.assign(this.doc, doc_values);
		this.doc.doctype = this.doc_type;
		frappe.form_dirty = false;

		let method = is_new
			? "frappe.website.doctype.web_form.web_form.new"
			: "frappe.website.doctype.web_form.web_form.update";
		let args = {
			web_form: this.name,
			doc: this.doc
		};
		return frappe.call({ method, args, btn: this.$btn_primary }).then(r => {
			// Check for any exception in response
			if (r.exc) return;

			let data = r.message;
			// Success

			this.handle_success(data);
			frappe.web_form.events.trigger("after_save");
			this.after_save && this.after_save();
			// args doctype and docname added to link doctype in file manager
			// if (is_new) {
			// 	frappe.call({
			// 		type: "POST",
			// 		method: "frappe.handler.upload_file",
			// 		args: {
			// 			file_url: data.attachment,
			// 			doctype: data.doctype,
			// 			docname: data.name
			// 		}
			// 	});
			// }
		});
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
		window.open(
			`/printview?
			doctype=${this.doc_type}
			&name=${this.doc.name}
			&format=${this.print_format || "Standard"}`,
			"_blank"
		);
	}

	cancel() {
		window.location.href = window.location.pathname;
	}

	handle_success(data) {
		let redirect_url = data.payment_url || this.success_url;
		if (!redirect_url && this.login_required) {
			redirect_url = window.location.pathname + "?name=" + data.name;
		}
		if (redirect_url) {
			this.show_success_message(
				__("Your information has been submitted. Redirecting...")
			);
			setTimeout(() => {
				window.location.href = redirect_url;
			}, 2000);
			return;
		}
		this.show_success_message(
			this.success_message || __("Your information has been submitted.")
		);
	}

	show_success_message(message) {
		$(".web-form-container form").hide();
		$(".web-form-success-message").text(message);
	}
}
