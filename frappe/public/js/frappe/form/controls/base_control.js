frappe.ui.form.Control = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();

		// if developer_mode=1, show fieldname as tooltip
		if(frappe.boot.user && frappe.boot.developer_mode===1 && this.$wrapper) {
			this.$wrapper.attr("title", __(this.df.fieldname));
		}

		if(this.render_input) {
			this.refresh();
		}
	},
	make: function() {
		this.make_wrapper();
		this.$wrapper
			.attr("data-fieldtype", this.df.fieldtype)
			.attr("data-fieldname", this.df.fieldname);
		this.wrapper = this.$wrapper.get(0);
		this.wrapper.fieldobj = this; // reference for event handlers
	},

	make_wrapper: function() {
		this.$wrapper = $("<div class='frappe-control'></div>").appendTo(this.parent);

		// alias
		this.wrapper = this.$wrapper;
	},

	toggle: function(show) {
		this.df.hidden = show ? 0 : 1;
		this.refresh();
	},

	// returns "Read", "Write" or "None"
	// as strings based on permissions
	get_status: function(explain) {
		if (this.df.get_status) {
			return this.df.get_status(this);
		}

		if ((!this.doctype && !this.docname) || this.df.parenttype === 'Web Form' || this.df.is_web_form) {
			// like in case of a dialog box
			if (cint(this.df.hidden)) {
				// eslint-disable-next-line
				if (explain) console.log("By Hidden: None"); // eslint-disable-line no-console
				return "None";

			} else if (cint(this.df.hidden_due_to_dependency)) {
				// eslint-disable-next-line
				if(explain) console.log("By Hidden Dependency: None"); // eslint-disable-line no-console
				return "None";

			} else if (cint(this.df.read_only)) {
				// eslint-disable-next-line
				if (explain) console.log("By Read Only: Read"); // eslint-disable-line no-console
				return "Read";

			} else if ((this.grid &&
						this.grid.display_status == 'Read') ||
						(this.layout &&
						this.layout.grid &&
						this.layout.grid.display_status == 'Read')) {
				// parent grid is read
				if (explain) console.log("By Parent Grid Read-only: Read"); // eslint-disable-line no-console
				return "Read";
			}

			return "Write";
		}

		var status = frappe.perm.get_field_display_status(this.df,
			frappe.model.get_doc(this.doctype, this.docname), this.perm || (this.frm && this.frm.perm), explain);

		// Match parent grid controls read only status
		if (status === 'Write' && (this.grid || (this.layout && this.layout.grid))) {
			var grid = this.grid || this.layout.grid;
			if (grid.display_status == 'Read') {
				status = 'Read';
				if (explain) console.log("By Parent Grid Read-only: Read"); // eslint-disable-line no-console
			}
		}

		// hide if no value
		if (this.doctype && status==="Read" && !this.only_input
			&& is_null(frappe.model.get_value(this.doctype, this.docname, this.df.fieldname))
			&& !in_list(["HTML", "Image", "Button"], this.df.fieldtype)) {

			// eslint-disable-next-line
			if (explain) console.log("By Hide Read-only, null fields: None"); // eslint-disable-line no-console
			status = "None";
		}

		return status;
	},
	refresh: function() {
		this.disp_status = this.get_status();
		this.$wrapper
			&& this.$wrapper.toggleClass("hide-control", this.disp_status=="None")
			&& this.refresh_input
			&& this.refresh_input();

		var value = this.get_value();

		this.show_translatable_button(value);
	},
	show_translatable_button(value) {
		// Disable translation non-string fields or special string fields
		if (!frappe.model
			|| !this.frm
			|| !this.doc
			|| !this.df.translatable
			|| !frappe.model.can_write('Translation')
			|| !value) return;

		// Disable translation in website
		if (!frappe.views || !frappe.views.TranslationManager) return;

		// Already attached button
		if (this.$wrapper.find('.clearfix .btn-translation').length) return;

		const translation_btn =
			`<a class="btn-translation no-decoration text-muted" title="${__('Open Translation')}">
				<i class="fa fa-globe"></i>
			</a>`;

		$(translation_btn)
			.appendTo(this.$wrapper.find('.clearfix'))
			.on('click', () => {
				if (!this.doc.__islocal) {
					new frappe.views.TranslationManager({
						'df': this.df,
						'source_text': value,
						'target_language': this.doc.language,
						'doc': this.doc
					});
				}
			});

	},
	get_doc: function() {
		return this.doctype && this.docname
			&& locals[this.doctype] && locals[this.doctype][this.docname] || {};
	},
	get_model_value: function() {
		if(this.doc) {
			return this.doc[this.df.fieldname];
		}
	},
	set_value: function(value) {
		return this.validate_and_set_in_model(value);
	},
	parse_validate_and_set_in_model: function(value, e) {
		if(this.parse) {
			value = this.parse(value);
		}
		return this.validate_and_set_in_model(value, e);
	},
	validate_and_set_in_model: function(value, e) {
		var me = this;
		if(this.inside_change_event) {
			return Promise.resolve();
		}
		this.inside_change_event = true;
		var set = function(value) {
			me.inside_change_event = false;
			return frappe.run_serially([
				() => me.set_model_value(value),
				() => {
					me.set_mandatory && me.set_mandatory(value);

					if(me.df.change || me.df.onchange) {
						// onchange event specified in df
						let set = (me.df.change || me.df.onchange).apply(me, [e]);
						me.set_invalid && me.set_invalid();
						return set;
					}
					me.set_invalid && me.set_invalid();
				}
			]);
		};

		value = this.validate(value);
		if (value && value.then) {
			// got a promise
			return value.then((value) => set(value));
		} else {
			// all clear
			return set(value);
		}
	},
	get_value: function() {
		if(this.get_status()==='Write') {
			return this.get_input_value ?
				(this.parse ? this.parse(this.get_input_value()) : this.get_input_value()) :
				undefined;
		} else {
			return this.value || undefined;
		}
	},
	set_model_value: function(value) {
		if(this.frm) {
			this.last_value = value;
			return frappe.model.set_value(this.doctype, this.docname, this.df.fieldname,
				value, this.df.fieldtype);
		} else {
			if(this.doc) {
				this.doc[this.df.fieldname] = value;
			}
			this.set_input(value);
			return Promise.resolve();
		}
	},
	set_focus: function() {
		if(this.$input) {
			this.$input.get(0).focus();
			return true;
		}
	}
});
