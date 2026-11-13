frappe.listview_settings["Contact"] = {
	add_fields: ["image"],
	onload: function (listview) {
		const download_vcards = () => {
			const contacts = listview.get_checked_items();
			open_url_post("/api/method/frappe.contacts.doctype.contact.contact.download_vcards", {
				contacts: contacts.map((c) => c.name),
			});
		};
		listview.page.add_action_item(__("Download vCards"), download_vcards, false, "id-card");
	},
};
