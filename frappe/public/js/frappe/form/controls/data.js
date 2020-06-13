frappe.provide('frappe.phone_call');

frappe.ui.form.ControlData = frappe.ui.form.ControlInput.extend({
	html_element: "input",
	input_type: "text",
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

		this.set_input_attributes();
		this.input = this.$input.get(0);
		this.has_input = true;
		this.bind_change_event();
		this.bind_focusout();
		this.setup_autoname_check();
		if (this.df.options == 'Phone') {
			this.setup_phone();
		}
		// somehow this event does not bubble up to document
		// after v7, if you can debug, remove this
	},
	setup_phone() {
		if (frappe.phone_call.handler) {
			this.$wrapper.find('.control-input')
				.append(`
					<span class="phone-btn">
						<a class="btn-open no-decoration" title="${__('Make a call')}">
							<i class="fa fa-phone"></i></a>
					</span>
				`)
				.find('.phone-btn')
				.click(() => {
					frappe.phone_call.handler(this.get_value(), this.frm);
				});
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
								if (val) {
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
		} else {
			return v;
		}
	}
});
