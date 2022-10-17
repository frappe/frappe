/*

Make the page editable

TODO:
- [x] Add Section (select type)
- [ ] Edit markdown as markdown
- [ ] Edit Section properties
- [ ] Add Row (duplicate last row)
- [ ] Remove Section
- [ ] Link Editing
- [ ] Image Editing
*/

import Sortable from "sortablejs";

class EditablePage {
	constructor() {}
	setup() {
		this.setup_add_section();
		this.setup_editable_properties();
		this.setup_sortable_sections();
		return this;
	}

	setup_add_section() {
		$(".add-section-container").removeClass("hidden");
		$(".btn-add-section").on("click", () => {
			this.show_add_section();
		});
	}

	show_add_section() {
		let d = new frappe.ui.Dialog({
			title: "Add a new section",
			scrollable: false,
			fields: [
				{
					fieldtype: "Link",
					options: "Web Template",
					label: "Section Type",
					fieldname: "section_type",
				},
			],
			primary_action_label: "Add",
			primary_action: () => {
				frappe
					.call("frappe.website.doctype.web_page.page_editor.get_section", {
						page: $(".web-page-content").attr("id"),
						section_type: d.get_value("section_type"),
					})
					.then((r) => {
						$(r.message).appendTo(".web-page-content");
					});
			},
		});
		d.show();
	}

	setup_editable_properties() {
		$("[wt-fieldname]")
			.attr("contenteditable", "true")
			.on("keypress", (e) => {
				e.target.dirty = true;
			})
			.on("blur", (e) => {
				if (!e.target.dirty) return;
				let element = $(e.target);
				let table_element = element.parents("[wt-type='Table']");

				frappe
					.call(
						"frappe.website.doctype.web_page.page_editor.update_web_block_property",
						{
							page: $(".web-page-content").attr("id"),
							section: element.parents("section").attr("data-section-idx"),
							table: table_element.attr("wt-table-fieldname"),
							rowid: table_element.attr("wt-row-idx"),
							type: element.attr("wt-type") || "text",
							key: element.attr("wt-fieldname"),
							value: e.target.innerHTML,
						}
					)
					.then(() => {
						e.target.dirty = false;
					});
			});

		// remove stretched link to edit
		$(".stretched-link").removeClass("stretched-link");
	}

	setup_sortable_sections() {
		this.section_sortable = new Sortable($(".web-page-content").get(0), {
			draggable: "section",
			onEnd: (e) => {
				let new_order = [];

				$(".web-page-content section").each((i, e) => {
					new_order.push(e.getAttribute("data-section-name"));
				});
				console.log(new_order);

				frappe
					.call("frappe.website.doctype.web_page.page_editor.update_section_idx", {
						page: $(".web-page-content").attr("id"),
						new_order: new_order,
					})
					.then(() => {
						frappe.toast("Updated");
					});
			},
		});
	}
}

frappe.EditablePage = EditablePage;
