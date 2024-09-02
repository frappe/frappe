// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Workspace Settings", {
	setup(frm) {
		frm.hide_full_form_button = true;
		frm.docfields = [];
		frm.workspace_map = {};
		let workspace_visibilty = JSON.parse(frm.doc.workspace_visibility_json || "{}");

		// build fields from workspaces
		let cnt = 0,
			column_added = false;
		for (let page of frappe.boot.allowed_workspaces) {
			if (page.public) {
				frm.workspace_map[page.name] = page;
				cnt++;
				frm.docfields.push({
					fieldtype: "Check",
					fieldname: page.name,
					label: page.title + (page.parent_page ? ` (${page.parent_page})` : ""),
					initial_value: workspace_visibilty[page.name] !== 0, // not set is also visible
				});
			}
		}

		frappe.temp = frm;
	},
	validate(frm) {
		frm.doc.workspace_visibility_json = JSON.stringify(frm.dialog.get_values());
		frm.doc.workspace_sequence = JSON.stringify(
			frm.wrapper
				.find(".frappe-control")
				.get()
				.map((e) => e.fieldobj.df.fieldname)
		);
		frm.doc.workspace_setup_completed = 1;
	},
	after_save(frm) {
		// reload page to show latest sidebar
		window.location.reload();
	},
	refresh(frm) {
		let get_page = (e) => frm.workspace_map[e.fieldobj.df.fieldname];

		frm.dialog.set_alert(__("Select, sort modules you want to see in the sidebar"));
		if (!frm.workspace_sortable) {
			frm.wrapper.find(".frappe-control").css({ "margin-bottom": "0.5rem" });

			let forms = frm.wrapper.find("form");
			frm.workspace_sortable = Sortable.create(forms.get(0), {
				group: "workspace_settings",
				animation: 150,
				onEnd: (o) => {
					// re-order so that child items are below parent items
					for (let e of frm.wrapper.find(".frappe-control").get()) {
						let page = get_page(e);
						if (page.parent_page) {
							// insert as the last child of the parent element
							let parent_element = frm.wrapper
								.find(`[data-fieldname="${page.parent_page}"`)
								.closest(".frappe-control");
							let parent_page = page.parent_page;

							// find the last child
							while (parent_element) {
								let next_element = parent_element.next(".frappe-control");

								if (!next_element.length) {
									// end of list
									$(e).insertAfter(parent_element);
									break;
								} else {
									let page = get_page(next_element.get(0));
									if (page.parent_page != parent_page) {
										// different parent, last child found
										$(e).insertAfter(parent_element);
										break;
									}
								}

								parent_element = next_element;
							}
						}
					}
				},
			});
		}
	},
});
