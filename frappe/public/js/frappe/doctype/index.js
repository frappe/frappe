frappe.provide("frappe.model");

/*
	Common class for handling client side interactions that
	apply to both DocType form and customize form.
*/
frappe.model.DocTypeController = class DocTypeController extends frappe.ui.form.Controller {
	setup() {
		// setup formatters for fieldtype
		frappe.meta.docfield_map[
			this.frm.doctype === "DocType" ? "DocField" : "Customize Form Field"
		].fieldtype.formatter = (value) => {
			const prefix = {
				"Tab Break": "--red-600",
				"Section Break": "--blue-600",
				"Column Break": "--yellow-600",
			};
			if (prefix[value]) {
				value = `<span class="bold" style="color: var(${prefix[value]})">${value}</span>`;
			}
			return value;
		};
	}

	refresh() {
		this.show_db_utilization();
	}

	show_db_utilization() {
		const doctype = this.frm.doc.doc_type || this.frm.doc.name;
		frappe
			.xcall("frappe.core.doctype.doctype.doctype.get_row_size_utilization", {
				doctype,
			})
			.then((r) => {
				if (r < 50.0) return;
				this.frm.dashboard.show_progress(
					__("Database Row Size Utilization"),
					r,
					__(
						"Database Table Row Size Utilization: {0}%, this limits number of fields you can add.",
						[r]
					)
				);
			});
	}

	max_attachments() {
		if (!this.frm.doc.max_attachments) {
			return;
		}
		const is_attach_field = (f) => ["Attach", "Attach Image"].includes(f.fieldtype);
		const no_of_attach_fields = this.frm.doc.fields.filter(is_attach_field).length;

		if (no_of_attach_fields > this.frm.doc.max_attachments) {
			this.frm.set_value("max_attachments", no_of_attach_fields);
			const label = this.frm.get_docfield("max_attachments").label;
			frappe.show_alert(
				__("Number of attachment fields are more than {}, limit updated to {}.", [
					label,
					no_of_attach_fields,
				])
			);
		}
	}

	naming_rule() {
		// set the "autoname" property based on naming_rule
		if (this.frm.doc.naming_rule && !this.frm.__from_autoname) {
			// flag to avoid recursion
			this.frm.__from_naming_rule = true;

			const naming_rule_default_autoname_map = {
				Autoincrement: "autoincrement",
				"Set by user": "prompt",
				"By fieldname": "field:",
				'By "Naming Series" field': "naming_series:",
				Expression: "format:",
				"Expression (sld style)": "",
				Random: "hash",
				UUID: "UUID",
				"By script": "",
			};
			this.frm.set_value(
				"autoname",
				naming_rule_default_autoname_map[this.frm.doc.naming_rule] || ""
			);
			setTimeout(() => (this.frm.__from_naming_rule = false), 500);

			this.set_naming_rule_description();
		}
	}

	set_naming_rule_description() {
		let naming_rule_description = {
			"Set by user": "",
			Autoincrement:
				"Uses Auto Increment feature of database.<br><b>WARNING: After using this option, any other naming option will not be accessible.</b>",
			"By fieldname": "Format: <code>field:[fieldname]</code>. Valid fieldname must exist",
			'By "Naming Series" field':
				"Format: <code>naming_series:[fieldname]</code>. Default fieldname is <code>naming_series</code>",
			Expression:
				"Format: <code>format:EXAMPLE-{MM}morewords{fieldname1}-{fieldname2}-{#####}</code> - Replace all braced words (fieldnames, date words (DD, MM, YY), series) with their value. Outside braces, any characters can be used.",
			"Expression (old style)":
				"Format: <code>EXAMPLE-.#####</code> Series by prefix (separated by a dot)",
			Random: "",
			"By script": "",
		};

		if (this.frm.doc.naming_rule) {
			this.frm
				.get_field("autoname")
				.set_description(naming_rule_description[this.frm.doc.naming_rule]);
		}
	}

	autoname() {
		// set naming_rule based on autoname (for old doctypes where its not been set)
		if (this.frm.doc.autoname && !this.frm.doc.naming_rule && !this.frm.__from_naming_rule) {
			// flag to avoid recursion
			this.frm.__from_autoname = true;
			const autoname = this.frm.doc.autoname.toLowerCase();

			if (autoname === "prompt") this.frm.set_value("naming_rule", "Set by user");
			else if (autoname === "autoincrement")
				this.frm.set_value("naming_rule", "Autoincrement");
			else if (autoname.startsWith("field:"))
				this.frm.set_value("naming_rule", "By fieldname");
			else if (autoname.startsWith("naming_series:"))
				this.frm.set_value("naming_rule", 'By "Naming Series" field');
			else if (autoname.startsWith("format:"))
				this.frm.set_value("naming_rule", "Expression");
			else if (autoname === "hash") this.frm.set_value("naming_rule", "Random");
			else this.frm.set_value("naming_rule", "Expression (old style)");

			setTimeout(() => (this.frm.__from_autoname = false), 500);
		}
	}

	setup_fetch_from_fields(doc, doctype, docname) {
		let frm = this.frm;
		// Render two select fields for Fetch From instead of Small Text for better UX
		let field = frm.cur_grid.grid_form.fields_dict.fetch_from;
		$(field.input_area).hide();

		let $doctype_select = $(`<select class="form-control">`);
		let $field_select = $(`<select class="form-control">`);
		let $wrapper = $('<div class="fetch-from-select row"><div>');
		$wrapper.append($doctype_select, $field_select);
		field.$input_wrapper.append($wrapper);
		$doctype_select.wrap('<div class="col"></div>');
		$field_select.wrap('<div class="col"></div>');

		let row = frappe.get_doc(doctype, docname);
		let curr_value = { doctype: null, fieldname: null };
		if (row.fetch_from) {
			let [doctype, fieldname] = row.fetch_from.split(".");
			curr_value.doctype = doctype;
			curr_value.fieldname = fieldname;
		}

		let doctypes = frm.doc.fields
			.filter((df) => df.fieldtype == "Link")
			.filter((df) => df.options && df.fieldname != row.fieldname)
			.sort((a, b) => a.options.localeCompare(b.options))
			.map((df) => ({
				label: `${df.options} (${df.fieldname})`,
				value: df.fieldname,
			}));
		$doctype_select.add_options([
			{ label: __("Select DocType"), value: "", selected: true },
			...doctypes,
		]);

		$doctype_select.on("change", () => {
			row.fetch_from = "";
			frm.dirty();
			update_fieldname_options();
		});

		function update_fieldname_options() {
			$field_select.find("option").remove();

			let link_fieldname = $doctype_select.val();
			if (!link_fieldname) return;
			let link_field = frm.doc.fields.find((df) => df.fieldname === link_fieldname);
			let link_doctype = link_field.options;
			frappe.model.with_doctype(link_doctype, () => {
				let fields = frappe.meta
					.get_docfields(link_doctype, null, {
						fieldtype: ["not in", frappe.model.no_value_type],
					})
					.sort((a, b) => a.label.localeCompare(b.label))
					.map((df) => ({
						label: `${df.label} (${df.fieldtype})`,
						value: df.fieldname,
					}));
				$field_select.add_options([
					{
						label: __("Select Field"),
						value: "",
						selected: true,
						disabled: true,
					},
					...fields,
				]);

				if (curr_value.fieldname) {
					$field_select.val(curr_value.fieldname);
				}
			});
		}

		$field_select.on("change", () => {
			let fetch_from = `${$doctype_select.val()}.${$field_select.val()}`;
			row.fetch_from = fetch_from;
			frm.dirty();
		});

		if (curr_value.doctype) {
			$doctype_select.val(curr_value.doctype);
			update_fieldname_options();
		}
	}
};
