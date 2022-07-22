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
		this.current_section = 0;
	}

	prepare(web_form_doc, doc) {
		Object.assign(this, web_form_doc);
		this.fields = web_form_doc.web_form_fields;
		this.doc = doc;
	}

	make() {
		super.make();
		this.set_sections();
		this.set_field_values();
		this.setup_listeners();

		if (this.is_new || this.is_form_editable) {
			this.setup_primary_action();
		}

		this.setup_footer_actions();
		this.setup_previous_next_button();
		this.toggle_section();

		// webform client script
		frappe.init_client_script && frappe.init_client_script();
		frappe.web_form.events.trigger('after_load');
		this.after_load && this.after_load();
	}

	on(fieldname, handler) {
		let field = this.fields_dict[fieldname];
		field.df.change = () => {
			handler(field, field.value);
		};
	}

	setup_listeners() {
		// Event listener for triggering Save/Next button for Multi Step Forms
		// Do not use `on` event here since that can be used by user which will render this function useless
		// setTimeout has 200ms delay so that all the base_control triggers for the fields have been run
		let me = this;

		if (!me.is_multi_step_form) {
			return;
		}

		for (let field of $(".input-with-feedback")) {
			$(field).change((e) => {
				setTimeout(() => {
					e.stopPropagation();
					me.toggle_buttons();
				}, 200);
			});
		}
	}

	set_sections() {
		if (this.sections.length) return;

		this.sections = $(`.form-section`);
	}

	setup_footer_actions() {
		if (this.is_multi_step_form) return;

		if ($('.web-form-container').height() > 600) {
			$(".web-form-footer").removeClass("hide");
		}
	}

	setup_previous_next_button() {
		let me = this;

		if (!me.is_multi_step_form) {
			return;
		}

		$('.web-form-footer').after(`
			<div id="form-step-footer" class="text-right">
				<button class="btn btn-default btn-previous btn-sm ml-2">${__("Previous")}</button>
				<button class="btn btn-default btn-next btn-sm ml-2">${__("Next")}</button>
			</div>
		`);

		$('.btn-previous').on('click', function () {
			let is_validated = me.validate_section();

			if (!is_validated) return false;

			/**
				The eslint utility cannot figure out if this is an infinite loop in backwards and
				throws an error. Disabling for-direction just for this section.
				for-direction doesnt throw an error if the values are hardcoded in the
				reverse for-loop, but in this case its a dynamic loop.
				https://eslint.org/docs/rules/for-direction
			*/
			/* eslint-disable for-direction */
			for (let idx = me.current_section; idx < me.sections.length; idx--) {
				let is_empty = me.is_previous_section_empty(idx);
				me.current_section = me.current_section > 0 ? me.current_section - 1 : me.current_section;

				if (!is_empty) {
					break;
				}
			}
			/* eslint-enable for-direction */
			me.toggle_section();
			return false;
		});

		$('.btn-next').on('click', function () {
			let is_validated = me.validate_section();

			if (!is_validated) return false;

			for (let idx = me.current_section; idx < me.sections.length; idx++) {
				let is_empty = me.is_next_section_empty(idx);
				me.current_section = me.current_section < me.sections.length ? me.current_section + 1 : me.current_section;

				if (!is_empty) {
					break;
				}
			}
			me.toggle_section();
			return false;
		});
	}

	set_field_values() {
		if (this.doc.name) this.set_values(this.doc);
		else return;
	}

	set_default_values() {
		let defaults = {};
		for (let df of this.fields) {
			if (df.default) {
				defaults[df.fieldname] = df.default;
			}
		}
		let values = frappe.utils.get_query_params();
		delete values.new;
		Object.assign(defaults, values);
		this.set_values(values);
	}

	setup_primary_action() {
		$(".web-form-container").on("submit", () => this.save());
	}

	validate_section() {
		if (this.allow_incomplete) return true;

		let fields = $(`.form-section:eq(${this.current_section}) .form-control`);
		let errors = [];
		let invalid_values = [];

		for (let field of fields) {
			let fieldname = $(field).attr("data-fieldname");
			if (!fieldname) continue;

			field = this.fields_dict[fieldname];

			if (field.get_value) {
				let value = field.get_value();
				if (field.df.reqd && is_null(typeof value === 'string' ? strip_html(value) : value)) errors.push(__(field.df.label));

				if (field.df.reqd && field.df.fieldtype === 'Text Editor' && is_null(strip_html(cstr(value)))) errors.push(__(field.df.label));

				if (field.df.invalid) invalid_values.push(__(field.df.label));
			}
		}

		let message = '';
		if (invalid_values.length) {
			message += __('Invalid values for fields:', null, 'Error message in web form');
			message += '<br><br><ul><li>' + invalid_values.join('<li>') + '</ul>';
		}

		if (errors.length) {
			message += __('Mandatory fields required:', null, 'Error message in web form');
			message += '<br><br><ul><li>' + errors.join('<li>') + '</ul>';
		}

		if (invalid_values.length || errors.length) {
			frappe.msgprint({
				title: __('Error', null, 'Title of error message in web form'),
				message: message,
				indicator: 'orange'
			});
		}

		return !(errors.length || invalid_values.length);
	}

	toggle_section() {
		if (!this.is_multi_step_form) return;

		this.toggle_previous_button();
		this.hide_sections();
		this.show_section();
		this.toggle_buttons();
	}

	toggle_buttons() {
		for (let idx = this.current_section; idx < this.sections.length; idx++) {
			if (this.is_next_section_empty(idx)) {
				this.show_save_and_hide_next_button();
			} else {
				this.show_next_and_hide_save_button();
				break;
			}
		}
	}

	is_next_section_empty(section) {
		if (section + 1 > this.sections.length) return true;

		let _section = $(`.form-section:eq(${section + 1})`);
		let visible_controls = _section.find(".frappe-control:not(.hide-control)");

		return !visible_controls.length ? true : false;
	}

	is_previous_section_empty(section) {
		if (section - 1 > this.sections.length) return true;

		let _section = $(`.form-section:eq(${section - 1})`);
		let visible_controls = _section.find(".frappe-control:not(.hide-control)");

		return !visible_controls.length ? true : false;
	}

	show_save_and_hide_next_button() {
		$('.btn-next').hide();
		$('.web-form-footer').show();
	}

	show_next_and_hide_save_button() {
		$('.btn-next').show();
		$('.web-form-footer').hide();
	}

	toggle_previous_button() {
		this.current_section == 0 ? $('.btn-previous').hide() : $('.btn-previous').show();
	}

	show_section() {
		$(`.form-section:eq(${this.current_section})`).show();
	}

	hide_sections() {
		for (let idx=0; idx < this.sections.length; idx++) {
			if (idx !== this.current_section) {
				$(`.form-section:eq(${idx})`).hide();
			}
		}
	}

	save() {
		let is_new = this.is_new;
		if (this.validate && !this.validate()) {
			frappe.throw(__("Couldn't save, please check the data you have entered"), __("Validation Error"));
		}

		// validation hack: get_values will check for missing data
		let doc_values = super.get_values(this.allow_incomplete);

		if (!doc_values) return;

		if (window.saving) return;
		let for_payment = Boolean(this.accept_payment && !this.doc.paid);

		Object.assign(this.doc, doc_values);
		this.doc.doctype = this.doc_type;
		this.doc.web_form_name = this.name;

		// Save
		window.saving = true;
		frappe.form_dirty = false;

		frappe.call({
			type: "POST",
			method: "frappe.website.doctype.web_form.web_form.accept",
			args: {
				data: this.doc,
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
					this.after_save && this.after_save();
					// args doctype and docname added to link doctype in file manager
					if (is_new && (response.message.attachment || response.message.file)) {
						frappe.call({
							type: 'POST',
							method: "frappe.handler.upload_file",
							args: {
								file_url: response.message.attachment || response.message.file,
								doctype: response.message.doctype,
								docname: response.message.name
							}
						});
					}
				}
			},
			always: function() {
				window.saving = false;
			}
		});
		return false;
	}

	edit() {
		window.location.href = window.location.pathname + "/edit";
	}

	cancel() {
		let path = window.location.pathname;
		if (this.is_new) {
			path = path.replace('/new', '');
		} else {
			path = path.replace('/edit', '');
		}
		window.location.href = path;
	}

	handle_success(data) {
		if (this.accept_payment && !this.doc.paid) {
			window.location.href = data;
		}

		const success_message =
			this.success_message || __("Submitted");

		frappe.toast({message: success_message, indicator:'green'});

		// redirect
		setTimeout(() => {
			let path = window.location.pathname;

			if (this.success_url) {
				path = this.success_url;
			} else if (this.login_required) {
				if (this.is_new && data.name) {
					path = path.replace("/new", "");
					path = path + "/" + data.name;
				} else if (this.is_form_editable) {
					path =  path.replace("/edit", "");
				}
			}
			window.location.href = path;
		}, 1000);
	}
}
