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
							function body(docnames) {
								const href = "<li><a href='/desk#Form/Deleted Document/%(0)s'>%(0)s</a></li>";
								const html = docnames.map(docname => { return repl(href, {'0': docname}) });
								return "<br><ul>" + html.join("");
							}
							function message(title, docnames) {
								return (docnames.length > 0) ? __(title) + body(docnames) + "</ul>": "";
							}

							let { restored, invalid, failed } = r.message;
							let restored_summary = message("Documents restored successfully", restored);
							let invalid_summary = message("Documents that were already Restored", invalid);
							let failed_summary = message("Documents that Failed to Restore", failed);
							let summary = restored_summary + invalid_summary + failed_summary;

							frappe.msgprint(summary, "Document Restoration Summary", true);

							if (restored.length > 0) {
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
