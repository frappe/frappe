frappe.ui.form.ControlInput = class ControlInput extends frappe.ui.form.Control {
	static horizontal = true;
	make() {
		// parent element
		super.make();
		this.set_input_areas();

		// set description
		this.set_max_width();
	}
	make_wrapper() {
		if (this.only_input) {
			this.$wrapper = $('<div class="form-group frappe-control">').appendTo(this.parent);
		} else {
			this.$wrapper = $(
				`<div class="frappe-control">
				<div class="form-group">
					<div class="clearfix">
						<label class="control-label" style="padding-right: 0px;"></label>
						<span class="help"></span>
					</div>
					<div class="control-input-wrapper">
						<div class="control-input"></div>
						<div class="control-value like-disabled-input" style="display: none;"></div>
						<p class="help-box small text-muted"></p>
					</div>
				</div>
			</div>`
			).appendTo(this.parent);
		}
	}
	toggle_label(show) {
		this.$wrapper.find(".control-label").toggleClass("hide", !show);
	}
	toggle_description(show) {
		this.$wrapper.find(".help-box").toggleClass("hide", !show);
	}
	set_input_areas() {
		if (this.only_input) {
			this.input_area = this.wrapper;
		} else {
			this.label_area = this.label_span = this.$wrapper.find("label").get(0);
			this.input_area = this.$wrapper.find(".control-input").get(0);
			this.$input_wrapper = this.$wrapper.find(".control-input-wrapper");
			// keep a separate display area to rendered formatted values
			// like links, currencies, HTMLs etc.
			this.disp_area = this.$wrapper.find(".control-value").get(0);
		}
	}
	set_max_width() {
		if (this.constructor.horizontal) {
			this.$wrapper.addClass("input-max-width");
		}
	}

	read_only_because_of_fetch_from() {
		return (
			this.df.fetch_from &&
			!this.df.fetch_if_empty &&
			this.frm?.doc?.[this.df.fetch_from.split(".")[0]]
		);
	}

	// update input value, label, description
	// display (show/hide/read-only),
	// mandatory style on refresh
	refresh_input() {
		var me = this;
		var make_input = function () {
			if (!me.has_input) {
				me.make_input();
				if (me.df.on_make) {
					me.df.on_make(me);
				}
			}
		};

		var update_input = function () {
			if (me.doctype && me.docname) {
				me.set_input(me.value);
			} else {
				me.set_input(me.value || null);
			}
		};

		if (me.disp_status != "None") {
			// refresh value
			if (me.frm) {
				me.value = frappe.model.get_value(me.doctype, me.docname, me.df.fieldname);
			} else if (me.doc) {
				me.value = me.doc[me.df.fieldname] || "";
			}

			let is_fetch_from_read_only = me.read_only_because_of_fetch_from();

			if (me.can_write() && !is_fetch_from_read_only) {
				me.disp_area && $(me.disp_area).toggle(false);
				$(me.input_area).toggle(true);
				me.$input && me.$input.prop("disabled", false);
				make_input();
				update_input();
			} else {
				if (me.only_input) {
					make_input();
					update_input();
				} else {
					$(me.input_area).toggle(false);
					if (me.disp_area) {
						me.set_disp_area(me.value);
						$(me.disp_area).toggle(true);
					}
				}
				me.$input && me.$input.prop("disabled", true);

				if (is_fetch_from_read_only) {
					$(me.disp_area).attr(
						"title",
						__(
							"This value is fetched from {0}'s {1} field",
							me.df.fetch_from.split(".").map((value) => __(frappe.unscrub(value)))
						)
					);
				}
			}

			me.set_description();
			me.set_label();
			me.set_doc_url();
			me.set_mandatory(me.value);
			me.set_bold();
			me.set_required();
		}
	}

	can_write() {
		return this.disp_status == "Write";
	}

	set_disp_area(value) {
		if (
			in_list(["Currency", "Int", "Float"], this.df.fieldtype) &&
			(this.value === 0 || value === 0)
		) {
			// to set the 0 value in readonly for currency, int, float field
			value = 0;
		} else {
			value = this.value || value;
		}
		if (this.df.fieldtype === "Data") {
			value = frappe.utils.escape_html(value);
		}
		let doc = this.doc || (this.frm && this.frm.doc);
		let display_value = frappe.format(value, this.df, { no_icon: true, inline: true }, doc);
		this.disp_area && $(this.disp_area).html(display_value);
	}
	set_label(label) {
		if (label) this.df.label = label;

		if (this.only_input || this.df.label == this._label) return;

		var icon = "";
		this.label_span.innerHTML =
			(icon ? '<i class="' + icon + '"></i> ' : "") + __(this.df.label) || "&nbsp;";
		this._label = this.df.label;
	}

	set_doc_url() {
		let unsupported_fieldtypes = frappe.model.no_value_type.filter(
			(x) => frappe.model.table_fields.indexOf(x) === -1
		);

		if (
			!this.df.label ||
			!this.df?.documentation_url ||
			in_list(unsupported_fieldtypes, this.df.fieldtype)
		)
			return;

		let $help = this.$wrapper.find("span.help");
		$help.empty();
		$(`<a href="${this.df.documentation_url}" target="_blank">
			${frappe.utils.icon("help", "sm")}
		</a>`).appendTo($help);
	}

	set_description(description) {
		if (description !== undefined) {
			this.df.description = description;
		}
		if (this.only_input || this.df.description === this._description) {
			return;
		}
		if (this.df.description) {
			this.$wrapper.find(".help-box").html(__(this.df.description));
		} else {
			this.set_empty_description();
		}
		this._description = this.df.description;
	}
	set_new_description(description) {
		this.$wrapper.find(".help-box").html(description);
	}
	set_empty_description() {
		this.$wrapper.find(".help-box").html("");
	}
	set_mandatory(value) {
		// do not set has-error class on form load
		if (this.frm && this.frm.cscript && this.frm.cscript.is_onload) return;

		// do not set has-error class while dialog is rendered
		// set has-error if dialog primary button is clicked
		if (this.layout && this.layout.is_dialog && !this.layout.primary_action_fulfilled) return;

		this.$wrapper.toggleClass("has-error", Boolean(this.df.reqd && is_null(value)));
	}
	set_invalid() {
		let invalid = !!this.df.invalid;
		if (this.grid) {
			this.$wrapper.parents(".grid-static-col").toggleClass("invalid", invalid);
			this.$input.toggleClass("invalid", invalid);
			this.grid_row.columns[this.df.fieldname].is_invalid = invalid;
		} else {
			this.$wrapper.toggleClass("has-error", invalid);
		}
	}
	set_required() {
		this.label_area && $(this.label_area).toggleClass("reqd", Boolean(this.df.reqd));
	}
	set_bold() {
		if (this.$input) {
			this.$input.toggleClass("bold", !!(this.df.bold || this.df.reqd));
		}
		if (this.disp_area) {
			$(this.disp_area).toggleClass("bold", !!(this.df.bold || this.df.reqd));
		}
	}
};
