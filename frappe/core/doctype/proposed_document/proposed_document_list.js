frappe.listview_settings["Proposed Document"] = {
	add_fields: ["is_standard"],
	refresh(listview) {
		listview.page.btn_primary.remove();
	},

	get_form_link: (doc) => {
		if (doc.status == "Pending" && doc.is_new_doc) {
			let dummy_doc = frappe.model.get_new_doc(doc.document_type);
			let doc_json = JSON.parse(doc.document_json);
			for (let key in doc_json) {
				dummy_doc[key] = doc_json[key];
			}
			dummy_doc.name = "new-" + frappe.scrub(doc.document_type) + "-" + (doc._idx + 1);
			dummy_doc.proposed_doc = doc.name;
			return "/app/" + frappe.router.slug(doc.document_type) + "/" + dummy_doc.name;
		} else if (doc.status == "Approved") {
			return "/app/" + frappe.router.slug(doc.document_type) + "/" + doc.document_name;
		}
	},
};
