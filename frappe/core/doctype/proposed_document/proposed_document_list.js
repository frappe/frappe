frappe.listview_settings["Proposed Document"] = {
	add_fields: ["is_standard"],
	refresh: function (listview) {},
	button: {
		show: function (doc) {
			return doc.document_type;
		},
		get_label: function () {
			return __("Show", null, "Access");
		},
		get_description: function (doc) {
			return __("Show {0}", [`${__(doc.document_type)}: ${doc.document_name}`]);
		},
		action: function (doc) {
			const newdoc = frappe.model.get_new_doc(doc.document_type);
			let doc_json = JSON.parse(doc.document_json);
			for (let key in doc_json) {
				newdoc[key] = doc_json[key];
			}
			frappe.set_route("Form", doc.document_type, doc.document_name);
		},
	},
};
