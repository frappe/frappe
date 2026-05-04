frappe.ui.form.on("Version", {
	refresh: function (frm) {
		frm.add_custom_button(__("Show all Versions"), function () {
			frappe.set_route("List", "Version", {
				ref_doctype: frm.doc.ref_doctype,
				docname: frm.doc.docname,
			});
		});

		frm.trigger("render_version_view");
	},

	render_version_view: async function (frm) {
		await frappe.model.with_doctype(frm.doc.ref_doctype);

		$(
			frappe.render_template("version_view", {
				doc: frm.doc,
				data: JSON.parse(frm.doc.data),
			})
		).appendTo(frm.fields_dict.table_html.$wrapper.empty());
	},
});
