frappe.web_form = {
	set_fieldname_select: function(frm) {
		var me = this,
			doc = frm.doc;
		if(doc.doc_type) {
			frappe.model.with_doctype(doc.doc_type, function() {
				var fields = $.map(frappe.get_doc("DocType", frm.doc.doc_type).fields, function(d) {
					return frappe.model.no_value_type.indexOf(d.fieldtype)===-1 ?
						 d.fieldname : null;
				})
				frappe.meta.get_docfield("Web Form Field", "fieldname", frm.doc.name).options
					= [""].concat(fields);
			});
		}
	}
}

frappe.ui.form.on("Web Form", {
	refresh: function(frm) {
		// show is-standard only if developer mode
		frm.get_field("is_standard").toggle(frappe.boot.developer_mode);

		frappe.web_form.set_fieldname_select(frm);

		if(frm.doc.is_standard && !frappe.boot.developer_mode) {
			frm.set_read_only();
			frm.disable_save();
		}
	},
	title: function(frm) {
		if(frm.doc.__islocal) {
			var page_name = frm.doc.title.toLowerCase().replace(/ /g, "-");
			frm.set_value("page_name", page_name);
			frm.set_value("success_url", "/" + page_name);
		}
	},
	doc_type: function(frm) {
		frappe.web_form.set_fieldname_select(frm);
	}
});


frappe.ui.form.on("Web Form Field", "fieldname", function(frm, doctype, name) {
	var doc = frappe.get_doc(doctype, name);
	var df = $.map(frappe.get_doc("DocType", frm.doc.doc_type).fields, function(d) {
			return doc.fieldname==d.fieldname ? d : null; })[0];

	doc.label = df.label;
	doc.reqd = df.reqd;
	doc.options = df.options;
	doc.fieldtype = frappe.meta.get_docfield("Web Form Field", "fieldtype")
		.options.split("\n").indexOf(df.fieldtype)===-1 ? "Data" : df.fieldtype;
	doc.description = df.description;
	doc["default"] = df["default"];

	frm.refresh_field("web_form_fields");
});
