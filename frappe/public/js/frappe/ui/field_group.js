import "../form/layout";

frappe.provide("frappe.ui");

frappe.ui.FieldGroup = class FieldGroup extends frappe.ui.form.Layout {
	constructor(opts) {
		super(opts);
		this.dirty = false;
		this.fetch_dict = {};

		$.each(this.fields || [], function (i, f) {
			if (!f.fieldname && f.label) {
				f.fieldname = f.label.replace(/ /g, "_").toLowerCase();
			}
		});
		if (this.values) {
			this.set_values(this.values);
		}
	}

	make() {
		let me = this;
		if (this.fields) {
			super.make();
			this.refresh();
			// set default
			$.each(this.fields_list, function (i, field) {
				let def_value = field.df["default"];
				// loose equality check matches undefined also
				if (
					def_value == null ||
					(!def_value && !frappe.model.is_numeric_field(field.df.fieldtype))
				)
					return;

				if (def_value == "Today" && field.df["fieldtype"] == "Date") {
					def_value = frappe.datetime.get_today();
				}

				field.set_input(def_value);
				// if default and has depends_on, render its fields.
				me.refresh_dependency();
			});

			if (!this.no_submit_on_enter) {
				this.catch_enter_as_submit();
			}

			$(this.wrapper)
				.find("input, select")
				.on("change awesomplete-selectcomplete", () => {
					this.dirty = true;
					frappe.run_serially([
						() => frappe.timeout(0.1),
						() => me.refresh_dependency(),
					]);
				});
		}
	}

	focus_on_first_input() {
		if (this.no_focus) return;
		$.each(this.fields_list, function (i, f) {
			if (!["Date", "Datetime", "Time", "Check"].includes(f.df.fieldtype) && f.set_focus) {
				f.set_focus();
				return false;
			}
		});
	}

	catch_enter_as_submit() {
		let me = this;
		$(this.body)
			.find('input[type="text"], input[type="password"], select')
			.keypress(function (e) {
				if (e.which == 13) {
					if (me.has_primary_action) {
						e.preventDefault();
						me.get_primary_btn().trigger("click");
					}
				}
			});
	}

	get_input(fieldname) {
		let field = this.fields_dict[fieldname];
		if (!field) return "";
		return $(field.txt ? field.txt : field.input);
	}

	get_field(fieldname) {
		return this.fields_dict[fieldname];
	}

	get_values(ignore_errors, check_invalid) {
		let ret = {};
		let errors = [];
		let invalid = [];

		for (let key in this.fields_dict) {
			let f = this.fields_dict[key];
			if (f.get_value) {
				let v = f.get_value();
				if (f.df.reqd && is_null(typeof v === "string" ? strip_html(v) : v))
					errors.push(__(f.df.label));

				if (f.df.reqd && f.df.fieldtype === "Text Editor" && is_null(strip_html(cstr(v))))
					errors.push(__(f.df.label));

				if (!is_null(v)) ret[f.df.fieldname] = v;
			}

			if (this.is_dialog && f.df.reqd && !f.value) {
				f.refresh_input();
			}

			if (f.df.invalid) {
				invalid.push(__(f.df.label));
			}
		}

		if (errors.length && !ignore_errors) {
			frappe.msgprint({
				title: __("Missing Values Required"),
				message:
					__("Following fields have missing values:") +
					"<br><br><ul><li>" +
					errors.join("<li>") +
					"</ul>",
				indicator: "orange",
			});
			return null;
		}

		if (invalid.length && check_invalid) {
			frappe.msgprint({
				title: __("Invalid Values"),
				message:
					__("Following fields have invalid values:") +
					"<br><br><ul><li>" +
					invalid.join("<li>") +
					"</ul>",
				indicator: "orange",
			});
			return null;
		}
		return ret;
	}

	get_value(key) {
		let f = this.fields_dict[key];
		return f && (f.get_value ? f.get_value() : null);
	}

	set_value(key, val) {
		return new Promise((resolve) => {
			let f = this.fields_dict[key];
			if (f) {
				f.set_value(val).then(() => {
					f.set_input?.(val);
					this.refresh_dependency();
					resolve();
				});
			} else {
				resolve();
			}
		});
	}

	has_field(fieldname) {
		return !!this.fields_dict[fieldname];
	}

	set_input(key, val) {
		return this.set_value(key, val);
	}

	set_values(dict) {
		let promises = [];
		for (let key in dict) {
			if (this.fields_dict[key]) {
				promises.push(this.set_value(key, dict[key]));
			}
		}

		return Promise.all(promises);
	}

	clear() {
		for (let key in this.fields_dict) {
			let f = this.fields_dict[key];
			if (f && f.set_input) {
				f.set_input(f.df["default"] || "");
			}
		}
	}

	set_df_property(fieldname, prop, value) {
		if (!fieldname) {
			return;
		}
		const field = this.get_field(fieldname);
		field.df[prop] = value;
		field.refresh();
	}

	set_query(fieldname, opt1, opt2) {
		if (opt2) {
			// on child table
			// set_query(fieldname, parent fieldname, query)
			if (this.fields_dict[opt1])
				this.fields_dict[opt1].grid.get_field(fieldname).get_query = opt2;
		} else {
			// on parent table
			// set_query(fieldname, query)
			if (this.fields_dict[fieldname]) {
				this.fields_dict[fieldname].get_query = opt1;
			}
		}
	}

	// UTILITIES
	add_fetch(link_field, source_field, target_field, target_doctype) {
		/*
		Example fetch dict to get sender_email from email_id field in sender:
			{
				"Notification": {
					"sender": {
						"sender_email": "email_id"
					}
				}
			}
		*/

		if (!target_doctype) target_doctype = "*";

		// Target field kept as key because source field could be non-unique
		this.fetch_dict.setDefault(target_doctype, {}).setDefault(link_field, {})[target_field] =
			source_field;
	}

	is_new() {
		return this.doc.__islocal;
	}
};
