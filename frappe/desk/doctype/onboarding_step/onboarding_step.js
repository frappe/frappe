// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Onboarding Step", {
	setup: function (frm) {
		frm.set_query("form_tour", function () {
			return {
				filters: {
					reference_doctype: frm.doc.reference_document,
				},
			};
		});
	},

	refresh: function (frm) {
		frappe.boot.developer_mode &&
			frm.set_intro(
				__(
					"To export this step as JSON, link it in a Onboarding document and save the document."
				),
				true
			);
		if (frm.doc.reference_document && frm.doc.action == "Update Settings") {
			setup_fields(frm);
		}

		if (!frappe.boot.developer_mode) {
			frm.trigger("disable_form");
		}
	},

	reference_document: function (frm) {
		if (frm.doc.reference_document && frm.doc.action == "Update Settings") {
			setup_fields(frm);
		}
	},

	action: function (frm) {
		if (frm.doc.action == "Show Form Tour") {
			frm.fields_dict.reference_document
				.set_description(`You need to add the steps in the contoller JS file. For example: <code>note.js</code>
<pre class="small text-muted"><code>
frappe.tour['Note'] = [
	{
		fieldname: "title",
		title: "Title of the Note",
		description: "...",
	}
];
</code></pre>
				`);
		} else {
			frm.fields_dict.reference_document.set_description(null);
		}
	},

	disable_form: function (frm) {
		frm.set_read_only();
		frm.fields
			.filter((field) => field.has_input)
			.forEach((field) => {
				frm.set_df_property(field.df.fieldname, "read_only", "1");
			});
		frm.disable_save();
	},
});

function setup_fields(frm) {
	if (frm.doc.reference_document && frm.doc.action == "Update Settings") {
		frappe.model.with_doctype(frm.doc.reference_document, () => {
			let fields = frappe
				.get_meta(frm.doc.reference_document)
				.fields.filter((df) => {
					return ["Data", "Check", "Int", "Link", "Select"].includes(df.fieldtype);
				})
				.map((df) => {
					return {
						label: `${__(df.label, null, df.parent)} (${df.fieldname})`,
						value: df.fieldname,
					};
				});

			frm.set_df_property("field", "options", fields);
		});
	}
}
