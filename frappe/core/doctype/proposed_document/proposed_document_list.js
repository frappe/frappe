frappe.listview_settings["Proposed Document"] = {
	add_fields: ["is_standard"],
	refresh(listview) {
		listview.page.btn_primary.remove();
	},

	get_form_link: (doc) => {
		if (doc.status == "Approved") {
			return "/app/" + frappe.router.slug(doc.document_type) + "/" + doc.document_name;
		} else {
			let form_name = "proposed-" + frappe.scrub(doc.document_type) + "-" + doc.name;
			return "/app/" + frappe.router.slug(doc.document_type) + "/" + form_name;
		}
	},
};
