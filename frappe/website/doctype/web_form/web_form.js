frappe.ui.form.on("Web Form", {
	refresh: function(frm) {
		// show is-standard only if developer mode
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);
		if (frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.set_read_only();
			frm.disable_save();
		}

		set_fields(frm);
		frm.events.add_get_fields_button();
	},

	add_get_fields_button(frm) {
		frm.add_custom_button(__("Get Fields"), () => {
			let webform_fieldtypes = frappe.meta
				.get_field("Web Form Field", "fieldtype")
				.options.split("\n");

			let added_fields = (frm.doc.fields || []).map(d => d.fieldname);

			get_fields_for_doctype(frm.doc.doc_type).then(fields => {
				for (let df of fields) {
					if (
						webform_fieldtypes.includes(df.fieldtype) &&
						!added_fields.includes(df.fieldname)
					) {
						frm.add_child("web_form_fields", {
							fieldname: df.fieldname,
							label: df.label,
							fieldtype: df.fieldtype,
							options: df.options,
							reqd: df.reqd,
							default: df.default,
							read_only: df.read_only,
							depends_on: df.depends_on,
							mandatory_depends_on: df.mandatory_depends_on,
							read_only_depends_on: df.read_only_depends_on,
							hidden: df.hidden,
							description: df.description
						});
					}
				}
				frm.refresh();
			});
		});
	},

	title: function(frm) {
		if (frm.doc.__islocal) {
			var page_name = frm.doc.title.toLowerCase().replace(/ /g, "-");
			frm.set_value("route", page_name);
			frm.set_value("success_url", "/" + page_name);
		}
	},

	doc_type: function(frm) {
		set_fields(frm);
	}
});

frappe.ui.form.on("Web Form Field", {
	fieldtype: function(frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);
		if (
			["Section Break", "Column Break", "Page Break"].includes(
				doc.fieldtype
			)
		) {
			doc.fieldname = "";
			doc.options = "";
			frm.refresh_field("web_form_fields");
		}
	},
	fieldname: function(frm, doctype, name) {
		let doc = frappe.get_doc(doctype, name);
		let df = frappe.meta.get_docfield(frm.doc.doc_type, doc.fieldname);
		if (!df) return;

		doc.label = df.label;
		doc.fieldtype = df.fieldtype;
		doc.options = df.options;
		doc.reqd = df.reqd;
		doc.default = df.default;
		doc.read_only = df.read_only;
		doc.depends_on = df.depends_on;
		doc.mandatory_depends_on = df.mandatory_depends_on;
		doc.read_only_depends_on = df.read_only_depends_on;
		doc.hidden = df.hidden;
		doc.description = df.description;

		frm.refresh_field("web_form_fields");
	}
});

function set_fields(frm) {
	let doc = frm.doc;
	let fields_grid = frm.fields_dict.web_form_fields.grid;

	if (!doc.doc_type) {
		fields_grid.update_docfield_property("fieldname", "options", []);
		frm.set_df_property("amount_field", "options", []);
		return;
	}

	fields_grid.update_docfield_property("fieldname", "options", [
		`Fetching fields from ${doc.doc_type}...`
	]);

	get_fields_for_doctype(doc.doc_type).then(fields => {
		let as_select_option = df => ({
			label: df.label + " (" + df.fieldtype + ")",
			value: df.fieldname
		});
		fields_grid.update_docfield_property(
			"fieldname",
			"options",
			fields.map(as_select_option)
		);

		let currency_fields = fields
			.filter(df => ["Currency", "Float"].includes(df.fieldtype))
			.map(as_select_option);
		if (!currency_fields.length) {
			currency_fields = [
				{
					label: `No currency fields in ${doc.doc_type}`,
					value: "",
					disabled: true
				}
			];
		}
		frm.set_df_property("amount_field", "options", currency_fields);
	});
}

function get_fields_for_doctype(doctype) {
	return new Promise(resolve =>
		frappe.model.with_doctype(doctype, resolve)
	).then(() => {
		return frappe.meta.get_docfields(doctype).filter(df => {
			return (
				frappe.model.is_value_type(df.fieldtype) ||
				["Table", "Table Multiselect"].includes(df.fieldtype)
			);
		});
	});
}
