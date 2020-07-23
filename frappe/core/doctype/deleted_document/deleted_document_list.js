frappe.listview_settings["Deleted Document"] = {
	onload: function (doclist) {
		const action = () => {
			const selected_docs = doclist.get_checked_items();
			if (selected_docs.length > 0) {
				let docnames = selected_docs.map((doc) => {
					return doc.name;
				});
				frappe.call({
					method: "frappe.core.doctype.deleted_document.deleted_document.bulk_restore",
					args: { "docnames": docnames },
					callback: function (r) {
						if (r.message) {
							let num = r.message.length;
							frappe.msgprint(
								__("{0} Document{1} {2} Restored", [
									num,
									num == 1 ? "" : "s",
									num == 1 ? "was" : "were",
								])
							);
							if (num > 0) {
								doclist.refresh();
							}
						}
					},
				});
			}
		};
		doclist.page.add_actions_menu_item(__("Restore"), action, false);
	},
};
