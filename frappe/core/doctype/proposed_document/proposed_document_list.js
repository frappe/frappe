frappe.listview_settings["Proposed Document"] = {
	add_fields: ["is_standard"],
	refresh(listview) {
		listview.page.btn_primary.remove();
		let dummy_doc = null;
		let doc_json = null;
		listview["dummy_docs"] = {};

		listview.data.forEach((doc) => {
			if (doc.status == "Pending") {
				dummy_doc = frappe.model.get_new_doc(doc.document_type);
				doc_json = JSON.parse(doc.document_json);
				for (let key in doc_json) {
					dummy_doc[key] = doc_json[key];
				}
				dummy_doc.name = "new-" + frappe.scrub(doc.document_type) + "-" + (doc._idx + 1);
				dummy_doc.proposed_doc = doc.name;
				listview["dummy_docs"][doc.name] = dummy_doc;
			}
		});
	},

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
			if (doc.status == "Pending" && doc.is_new_doc) {
				frappe.set_route("Form", doc.document_type, cur_list.dummy_docs[doc.name]["name"]);
			} else if (doc.status == "Approved") {
				frappe.set_route("Form", doc.document_type, doc.document_name);
			}
		},
	},
};
