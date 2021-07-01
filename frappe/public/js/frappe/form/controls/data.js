frappe.provide('frappe.phone_call');

frappe.ui.form.ControlData = frappe.ui.form.ControlInput.extend({
	html_element: "input",
	input_type: "text",
	trigger_change_on_input_event: true,
	make_input: function() {
		if(this.$input) return;

		this.$input = $("<"+ this.html_element +">")
			.attr("type", this.input_type)
			.attr("autocomplete", "off")
			.addClass("input-with-feedback form-control")
			.prependTo(this.input_area);

		if (in_list(['Data', 'Link', 'Dynamic Link', 'Password', 'Select', 'Read Only', 'Attach', 'Attach Image'],
			this.df.fieldtype)) {
			this.$input.attr("maxlength", this.df.length || 140);
		}

		this.$input.on('paste', (e) => {
			let pasted_data = frappe.utils.get_clipboard_data(e);
			let maxlength = this.$input.attr('maxlength');
			if (maxlength && pasted_data.length > maxlength) {
				let warning_message = __('The value you pasted was {0} characters long. Max allowed characters is {1}.', [
					cstr(pasted_data.length).bold(),
					cstr(maxlength).bold()
				]);

				// Only show edit link to users who can update the doctype
				if (this.frm && frappe.model.can_write(this.frm.doctype)) {
					let doctype_edit_link = null;
					if (this.frm.meta.custom) {
						doctype_edit_link = frappe.utils.get_form_link(
							'DocType', 
							this.frm.doctype, true,
							__('this form')
						);
					} else {
						doctype_edit_link = frappe.utils.get_form_link('Customize Form', 'Customize Form', true, null, {
							doc_type: this.frm.doctype
						});
					}
					let edit_note = __('{0}: You can increase the limit for the field if required via {1}', [
						__('Note').bold(),
						doctype_edit_link
					]);
					warning_message += `<br><br><span class="text-muted text-small">${edit_note}</span>`;
				}

				frappe.msgprint({
					message: warning_message,
					indicator: 'orange',
					title: __('Data Clipped')
				});
			}
		});

		this.set_input_attributes();
		this.input = this.$input.get(0);
		this.has_input = true;
		this.bind_change_event();
		this.setup_autoname_check();

		if (this.df.options == 'URL') {
			this.setup_url_field();
		}
	},
	setup_url_field: function() {
		this.$wrapper.find('.control-input').append(
			`<span class="link-btn">
				<a class="btn-open no-decoration" title="${__("Open Link")}" target="_blank">
					${frappe.utils.icon('link-url', 'sm')}
				</a>
			</span>`
		);
		
		this.$link = this.$wrapper.find('.link-btn');
		this.$link_open = this.$link.find('.btn-open');
		this.$input[0].style.paddingRight = "24px"; // To prevent text-icon mixup

		this.$input.on("focus", () => {
			setTimeout(() => {
				let inputValue = this.get_input_value();
				
				if (inputValue && validate_url(inputValue)) {
					this.$link.toggle(true);
					this.$link_open.attr('href', this.get_input_value());
				}
			}, 500);
		});


		this.$input.bind("input", () => {
			let inputValue = this.get_input_value();

			if (inputValue && validate_url(inputValue)) {
				this.$link.toggle(true);
				this.$link_open.attr('href', this.get_input_value());
			} else {
				this.$link.toggle(false);
			}
		});
		
		this.$input.on("blur", () => {
			// if this disappears immediately, the user's click
			// does not register, hence timeout
			setTimeout(() => {
				this.$link.toggle(false);
			}, 500);
		});
	},
	bind_change_event: function() {
		const change_handler = e => {
			if (this.change) this.change(e);
			else {
				let value = this.get_input_value();
				this.parse_validate_and_set_in_model(value, e);
			}
		};
		this.$input.on("change", change_handler);
		if (this.trigger_change_on_input_event) {
			// debounce to avoid repeated validations on value change
			this.$input.on("input", frappe.utils.debounce(change_handler, 500));
		}
	},
	setup_autoname_check: function() {
		if (!this.df.parent) return;
		this.meta = frappe.get_meta(this.df.parent);
		if (this.meta && ((this.meta.autoname
			&& this.meta.autoname.substr(0, 6)==='field:'
			&& this.meta.autoname.substr(6) === this.df.fieldname) || this.df.fieldname==='__newname') ) {
			this.$input.on('keyup', () => {
				this.set_description('');
				if (this.doc && this.doc.__islocal) {
					// check after 1 sec
					let timeout = setTimeout(() => {
						// clear any pending calls
						if (this.last_check) clearTimeout(this.last_check);

						// check if name exists
						frappe.db.get_value(this.doctype, this.$input.val(),
							'name', (val) => {
								if (val && val.name) {
									this.set_description(__('{0} already exists. Select another name', [val.name]));
								}
							},
							this.doc.parenttype
						);
						this.last_check = null;
					}, 1000);
					this.last_check = timeout;
				}
			});
		}
	},
	set_input_attributes: function() {
		this.$input
			.attr("data-fieldtype", this.df.fieldtype)
			.attr("data-fieldname", this.df.fieldname)
			.attr("placeholder", this.df.placeholder || "");
		if(this.doctype) {
			this.$input.attr("data-doctype", this.doctype);
		}
		if(this.df.input_css) {
			this.$input.css(this.df.input_css);
		}
		if(this.df.input_class) {
			this.$input.addClass(this.df.input_class);
		}
	},
	set_input: function(value) {
		this.last_value = this.value;
		this.value = value;
		this.set_formatted_input(value);
		this.set_disp_area(value);
		this.set_mandatory && this.set_mandatory(value);
	},
	set_formatted_input: function(value) {
		this.$input && this.$input.val(this.format_for_input(value));
	},
	get_input_value: function() {
		return this.$input ? this.$input.val() : undefined;
	},
	format_for_input: function(val) {
		return val==null ? "" : val;
	},
	validate: function(v) {
		if (!v) {
			return '';
		}
		if(this.df.is_filter) {
			return v;
		}
		if(this.df.options == 'Phone') {
			this.df.invalid = !validate_phone(v);
			return v;
		} else if (this.df.options == 'Name') {
			this.df.invalid = !validate_name(v);
			return v;
		} else if(this.df.options == 'Email') {
			var email_list = frappe.utils.split_emails(v);
			if (!email_list) {
				return '';
			} else {
				let email_invalid = false;
				email_list.forEach(function(email) {
					if (!validate_email(email)) {
						email_invalid = true;
					}
				});
				this.df.invalid = email_invalid;
				return v;
			}
		} else if (this.df.options == 'URL') {
			this.df.invalid = !validate_url(v);
			return v;
		} else {
			return v;
		}
	},
	toggle_container_scroll: function(el_class, scroll_class, add=false) {
		let el = this.$input.parents(el_class)[0];
		if (el) $(el).toggleClass(scroll_class, add);
	}
});
