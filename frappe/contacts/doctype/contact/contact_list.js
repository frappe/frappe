frappe.listview_settings["Contact"] = {
	add_fields: ["image"],
<<<<<<< HEAD
=======
	onload: function (listview) {
		listview.page.add_action_item(__("Download vCards"), function () {
			const contacts = listview.get_checked_items();
			open_url_post("/api/method/frappe.contacts.doctype.contact.contact.download_vcards", {
				contacts: contacts.map((c) => c.name),
			});
		});
	},
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
};
