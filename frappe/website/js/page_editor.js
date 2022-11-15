/*

Make the page editable

TODO:
- [ ] Setup editable page
- [ ] Close editing
- [x] Add Section (select type)
- [x] Edit Section properties
- [x] Add item (duplicate last row)
- [x] Remove Section
- [x] Edit links, images
- [ ] Groups for page / section
- [ ] Edit page properties (title, description, preview)
- [ ] Create new page
- [ ] Edit navbar (?)
- [ ] Edit footer (?)
*/

import Sortable from "sortablejs";

class EditablePage {
	constructor() {}
	setup() {
		this.setup_floater();
		this.setup_add_section();
		this.setup_remove_section();
		this.setup_add_item();
		this.setup_edit_section();
		this.setup_editable_properties();
		this.setup_sortable_sections();
		return this;
	}

	setup_floater() {
		this.floater = $(`
			<style>
				.section:hover {
					background-color: rgba(0, 0, 0, 0.02);
				}
				.section-editor {
					position: fixed;
					right: 20px; top: 20px;
					width: 200px; min-height: 30px;
					border: 1px solid var(--border-color);
					background-color: var(--white);
					border-radius: var(--border-radius);
					box-shadow: var(--shadow-md)
				}
				.section-editor .part {
					font-size: var(--text-sm);
					padding: 0.5rem;
					border-bottom: 1px solid var(--border-color);
				}
				.pointer {
					cursor: pointer;
				}
			</style>
			<div class="section-editor">
				<div class="part section-head pointer">
					<b>Section Details</b>
				</div>
				<div class="part section-name">
					Select Section
				</div>
				<div class="actions hide">
					<div class="part">
						<div><b>Spacer</b></div>
						<div class="d-flex justify-content-between">
							<div class="d-flex justify-content-start align-items-center">
								<input type="checkbox" class="check-spacer-top"
									data-fieldname="add_top_padding"
									data-class="section-padding-top">
								<span>Top</span>
							</div>
							<div class="d-flex justify-content-start align-items-center">
								<input type="checkbox" class="check-spacer-bottom"
									data-fieldname="add_bottom_padding"
									data-class="section-padding-bottom">
								<span>Bottom</span>
							</div>
						</div>
					</div>
					<div class="part">
						<div><b>Border</b></div>
						<div class="d-flex justify-content-between">
							<div class="d-flex justify-content-start align-items-center">
								<input type="checkbox" class="check-border-top"
									data-fieldname="add_border_at_top"
									data-class="border-top">
								<span>Top</span>
							</div>
							<div class="d-flex justify-content-start align-items-center">
								<input type="checkbox" class="check-border-bottom"
									data-fieldname="add_border_at_bottom"
									data-class="border-bottom">
							<span>Bottom</span>
							</div>
						</div>
					</div>
					<div class="part">
						<button class="btn btn-xs btn-default btn-edit-section">Edit Section</button>
						<button class="btn btn-xs btn-default btn-add-item ml-2 hide">Add Item</button>
					</div>
					<div class="part">
						<a href="#" class="action-remove">Remove</a>
					</div>
				</div>
				<div class="part" style="margin-bottom: -1px">

					<a class="btn-add-section pointer">
						<svg class="icon icon-sm">
							<use href="#icon-add"></use>
						</svg>
						<span>Add Section</span>
					</a>
				</div>
			</div>
		`).appendTo("body");

		// select section
		$("section.section").on("click", (e) => {
			let section = $(e.target).closest("section");

			// set checkbox info
			$(".section-editor .section-name").html(
				`${section.data("section-idx")}: ${section.data("section-template")}`
			);
			$(".section-editor .check-spacer-top").prop(
				"checked",
				section.hasClass("section-padding-top")
			);
			$(".section-editor .check-spacer-bottom").prop(
				"checked",
				section.hasClass("section-padding-bottom")
			);
			$(".section-editor .check-border-top").prop("checked", section.hasClass("border-top"));
			$(".section-editor .check-border-bottom").prop(
				"checked",
				section.hasClass("border-bottom")
			);

			$(".section-editor .btn-add-item").toggleClass(
				"hide",
				!section.has("[wt-table-fieldname]").length
			);
			this.setup_actions();
			this.section = section;
		});
	}

	setup_actions() {
		if (this.actions_set) return;
		$(".section-editor .actions").removeClass("hide");

		// checkbox actions
		$('.section-editor .actions input[type="checkbox"]').on("click", (e) => {
			let css_class = $(e.target).data("class");
			this.section.toggleClass(css_class, $(e.target).is(":checked"));
			frappe.call("frappe.website.doctype.web_page.page_editor.set_section_property", {
				page: this.get_page(),
				section_id: this.get_section_id(),
				property: $(e.target).data("fieldname"),
				value: $(e.target).is(":checked") ? 1 : 0,
			});
		});

		$(".section-head").on("click", () => {
			$(".section-editor .actions").toggleClass("hide");
		});

		this.actions_set = true;
	}

	setup_remove_section() {
		$(".action-remove").on("click", () => {
			frappe
				.call("frappe.website.doctype.web_page.page_editor.remove_section", {
					page: this.get_page(),
					section_id: this.get_section_id(),
				})
				.then((r) => {
					this.section.remove();
				});
			return false;
		});
	}

	setup_add_item() {
		$(".section-editor .btn-add-item").on("click", () => {
			frappe
				.call("frappe.website.doctype.web_page.page_editor.add_item", {
					page: this.get_page(),
					section_id: this.get_section_id(),
					table: this.section.find("[wt-type='Table']").attr("wt-table-fieldname"),
				})
				.then((r) => {
					this.replace_section(r.message);
				});
		});
	}

	setup_edit_section() {
		$(".section-editor .btn-edit-section").on("click", (e) => {
			$(e.target).prop("disabled", true);
			frappe
				.call("frappe.website.doctype.web_page.page_editor.get_values", {
					page: this.get_page(),
					section_id: this.get_section_id(),
				})
				.then((r) => {
					$(e.target).prop("disabled", false);
					frappe
						.open_web_template_values_editor(
							this.section.data("section-template"),
							r.message
						)
						.then((values) => {
							frappe
								.call("frappe.website.doctype.web_page.page_editor.set_values", {
									page: this.get_page(),
									section_id: this.get_section_id(),
									web_template_values: values,
								})
								.then((r) => {
									this.replace_section(r.message);
								});
						});
				});
		});
	}

	setup_add_section() {
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
						page: this.get_page(),
						section_type: d.get_value("section_type"),
					})
					.then((r) => {
						let new_section = $(r.message).appendTo(".web-page-content");
						this.setup_editable_properties(
							`[data-section-idx="${new_section.data("section-idx")}"] `
						);
						d.hide();
					});
			},
		});
		d.show();
	}

	setup_editable_properties(parent_element = "") {
		$(parent_element + "[wt-fieldname]")
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
							page: this.get_page(),
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

				frappe
					.call("frappe.website.doctype.web_page.page_editor.update_section_idx", {
						page: this.get_page(),
						new_order: new_order,
					})
					.then(() => {
						frappe.toast("Updated");
					});
			},
		});
	}

	replace_section(html) {
		this.section = this.section.replaceWith($(html));

		// re-configure properties
		this.setup_editable_properties(`[data-section-idx="${this.get_section_id()}"] `);
	}

	get_page() {
		return $(".web-page-content").attr("id");
	}

	get_section_id() {
		return this.section.data("section-idx");
	}
}

frappe.EditablePage = EditablePage;
