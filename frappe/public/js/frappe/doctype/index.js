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

		this.frm.set_df_property("fields", "reqd", this.frm.doc.autoname !== "Prompt");
	}
};
